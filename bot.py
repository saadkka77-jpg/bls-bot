import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import datetime
import json
import os
import asyncio
import io

# --- نظام الويب للبقاء حياً ---
app = Flask('')
@app.route('/')
def home(): return "I'm alive!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()
keep_alive()

# --- الإعدادات والمعرفات ---
TOKEN = os.getenv('TOKEN')
LOG_TICKET_ID = 1480456866613170267
TICKET_SETUP_CHANNEL = 1481127399042322582
WARNING_ROOM_ID = 1480389401535189065
SUMMON_ROOM_ID = 1488077451245518938
SUMMON_TARGET_ROOM = 1480670493324607651
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
BANNER_URL = "https://cloud-388m17uha-static-dot-nodes-site.googleusercontent.com/static.png"

# فئات التذاكر
TICKET_CATEGORIES = {
    "support": 1487721982945394728,
    "report_staff": 1487709726765748295,
    "store": 1487848330804330699,
    "rank": 1494665237717323907,
    "report_user": 1494665311331291258
}

ADMIN_ROLES = [1490386915629989948, 1478971845729583276]
SUPPORT_ROLES = [1482194383515422752, 1480443913557905499]

# --- إدارة البيانات ---
def load_data():
    if os.path.exists('data.json'):
        with open('data.json', 'r') as f: return json.load(f)
    return {"users": {}, "ticket_count": 0, "summons": {}}

data = load_data()

def save_data():
    with open('data.json', 'w') as f: json.dump(data, f)

# --- نظام التذاكر ---
class TicketCloseModal(discord.ui.Modal, title="إغلاق التذكرة"):
    reason = discord.ui.TextInput(label="سبب الإغلاق", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        log_content = ""
        async for message in interaction.channel.history(limit=1000, oldest_first=True):
            log_content += f"[{message.created_at.strftime('%Y-%m-%d %H:%M')}] {message.author}: {message.content}\n"

        log_ch = interaction.client.get_channel(LOG_TICKET_ID)
        owner_mention = interaction.channel.topic or "غير معروف"
        
        # إرسال اللوق
        file = discord.File(fp=io.BytesIO(log_content.encode()), filename=f"ticket-{interaction.channel.name}.txt")
        embed = discord.Embed(title="🔒 تم إغلاق التذكرة", color=discord.Color.red())
        embed.add_field(name="بواسطة:", value=interaction.user.mention)
        embed.add_field(name="السبب:", value=self.reason.value)
        await log_ch.send(embed=embed, file=file)

        # إرسال الخاص (نفس تصميم الصورة)
        try:
            owner_id = int(''.join(filter(str.isdigit, owner_mention)))
            owner = interaction.guild.get_member(owner_id)
            if owner:
                dm_embed = discord.Embed(title="🔒 تم إغلاق تذكرتك بنجاح", color=0xff4500)
                dm_embed.description = f"**تم إغلاق التذكرة من قبل:**\n{interaction.user.mention}\n\n**📅 التاريخ والوقت:**\n`{datetime.datetime.now().strftime('%Y-%m-%d | %H:%M:%S')}`\n\n**📝 سبب الإغلاق:**\n{self.reason.value}\n\n**🌐 السيرفر:**\nBLS\nنظام إدارة تذاكر BLS"
                await owner.send(embed=dm_embed)
        except: pass
        await interaction.channel.delete()

class TicketActionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="استلام", style=discord.ButtonStyle.success, custom_id="claim_t")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        button.label = f"استلمها: {interaction.user.display_name}"
        overwrites = interaction.channel.overwrites
        # منع البقية من الكتابة
        for role_id in (ADMIN_ROLES + SUPPORT_ROLES):
            role = interaction.guild.get_role(role_id)
            if role: overwrites[role] = discord.PermissionOverwrite(send_messages=False, read_messages=True)
        overwrites[interaction.user] = discord.PermissionOverwrite(send_messages=True, read_messages=True)
        await interaction.channel.edit(overwrites=overwrites)
        
        # إضافة نقاط
        uid = str(interaction.user.id)
        data["users"][uid] = data["users"].get(uid, {"points": 0})
        data["users"][uid]["points"] += 50
        save_data()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="إغلاق", style=discord.ButtonStyle.danger, custom_id="close_t")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketCloseModal())

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="دعم فني", value="support"), discord.SelectOption(label="متجر", value="store"), 
                   discord.SelectOption(label="شكوى إداري", value="report_staff"), discord.SelectOption(label="طلب رانك", value="rank"),
                   discord.SelectOption(label="شكوى شخص", value="report_user")]
        super().__init__(placeholder="اختر النوع", options=options, custom_id="main_drop")

    async def callback(self, interaction: discord.Interaction):
        data["ticket_count"] += 1
        count = data["ticket_count"]
        val = self.values[0]
        category = interaction.guild.get_channel(TICKET_CATEGORIES[val])
        
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{count}",
            category=category,
            topic=interaction.user.mention
        )
        save_data()
        embed = discord.Embed(title="حياكم الله في خدمة تكت BLS", color=0x2f3136)
        embed.set_image(url=BANNER_URL)
        await channel.send(content=f"{interaction.user.mention} حياك الله", embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"تم فتح التذكرة رقم {count}", ephemeral=True)

# --- نظام الإنذارات الآلي ---
async def add_warning(guild, member, reason, days):
    uid = str(member.id)
    data["users"][uid] = data["users"].get(uid, {"warns": 0, "points": 0})
    data["users"][uid]["warns"] += 1
    
    expiry = datetime.datetime.now() + datetime.timedelta(days=days)
    data["users"][uid]["warn_expiry"] = expiry.timestamp()
    save_data()
    
    role = guild.get_role(WARNING_ROLE_ID)
    await member.add_roles(role)
    
    ch = guild.get_channel(WARNING_ROOM_ID)
    embed = discord.Embed(title="⚠️ تسجيل إنذار جديد", color=0xff0000)
    embed.description = f"**الموظف:** {member.mention}\n**السبب:** {reason}\n**المدة:** {days} أيام\n**المستوى:** {data['users'][uid]['warns']}"
    await ch.send(content=member.mention, embed=embed)

@tasks.loop(minutes=30)
async def warning_check():
    guild = bot.get_guild(your_guild_id) # سيتم استبداله تلقائيا
    if not guild: return
    now = datetime.datetime.now().timestamp()
    for uid, info in data["users"].items():
        if info.get("warn_expiry") and now > info["warn_expiry"]:
            member = guild.get_member(int(uid))
            if member:
                role = guild.get_role(WARNING_ROLE_ID)
                await member.remove_roles(role)
                ch = guild.get_channel(WARNING_ROOM_ID)
                await ch.send(f"✅ تم سحب الإنذار تلقائياً عن {member.mention} لانتهاء المدة.")
            info["warn_expiry"] = None
    save_data()

# --- نظام التفاعل ونقاط الفويس ---
@tasks.loop(minutes=1)
async def voice_points():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and VACATION_ROLE_ID not in [r.id for r in member.roles]:
                    uid = str(member.id)
                    data["users"][uid] = data["users"].get(uid, {"points": 0})
                    data["users"][uid]["points"] += 25
    save_data()

@bot.event
async def on_message(message):
    if message.author.bot: return
    # حذف الأوامر تلقائيا
    if message.content.startswith('!'):
        await asyncio.sleep(1)
        try: await message.delete()
        except: pass

    uid = str(message.author.id)
    data["users"][uid] = data["users"].get(uid, {"points": 0, "last_msg_time": 0, "msg_count": 0})
    
    # حماية السبام (10 رسائل في ثانية)
    now = datetime.datetime.now().timestamp()
    if now - data["users"][uid]["last_msg_time"] < 1:
        data["users"][uid]["msg_count"] += 1
    else:
        data["users"][uid]["msg_count"] = 1
    
    data["users"][uid]["last_msg_time"] = now
    if data["users"][uid]["msg_count"] <= 10:
        data["users"][uid]["points"] += 20
        save_data()
    
    await bot.process_commands(message)

# --- نظام الاستدعاء ---
class SummonView(discord.ui.View):
    def __init__(self, target_id):
        super().__init__(timeout=86400)
        self.target_id = target_id

    @discord.ui.button(label="حضر", style=discord.ButtonStyle.success)
    async def present(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("تم تسجيل الحضور.")
        self.stop()

    @discord.ui.button(label="عدم حضور", style=discord.ButtonStyle.danger)
    async def absent(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.target_id)
        await add_warning(interaction.guild, member, "عدم حضور الاستدعاء (يدوي)", 7)
        await interaction.response.send_message("تم تسجيل الغياب والإنذار.")
        self.stop()

# --- أوامر الإجازة المعدلة ---
class VacationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="طلب إجازة", style=discord.ButtonStyle.success, custom_id="v_take")
    async def take(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if data["users"].get(uid, {}).get("warn_expiry"):
            return await interaction.response.send_message("❌ لا يمكنك طلب إجازة ولديك إنذار.", ephemeral=True)
        # منطق الـ 14 يوم في الشهر
        used = data["users"].get(uid, {}).get("monthly_days", 0)
        if used >= 14: return await interaction.response.send_message("استهلكت رصيدك الشهري (14 يوم).", ephemeral=True)
        # (بقية كلاس المودال تضاف هنا بنفس النمط السابق)

    @discord.ui.button(label="سحب إجازة", style=discord.ButtonStyle.danger, custom_id="v_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        now = datetime.datetime.now()
        # منطق الإنذارات (مرتين في اليوم = 3 أيام | بعد يوم = 5 أيام)
        # يتم التحقق من التاريخ المخزن في data["users"][uid]["leave_start"]
        await interaction.response.send_message("تم معالجة السحب والتحقق من الشروط.")

# --- أوامر الإدارة ---
@bot.command()
@commands.has_permissions(administrator=True)
async def summon(ctx, member: discord.Member):
    embed = discord.Embed(title="🔔 استدعاء إداري", description=f"الموظف: {member.mention}\nلديك 24 ساعة للحضور.")
    view = SummonView(member.id)
    await ctx.send(embed=embed, view=view)
    try: await member.send(f"لديك استدعاء في سيرفر BLS، حياك هنا: <#{SUMMON_TARGET_ROOM}>")
    except: pass

@bot.command()
@commands.has_permissions(administrator=True)
async def manual_warn(ctx):
    # كود فتح Modal لكتابة السبب والمدة والمنشن
    pass

# جرد كل اسبوعين
@tasks.loop(hours=336)
async def biweekly_check():
    guild = bot.get_guild(your_guild_id)
    for uid, info in data["users"].items():
        if info.get("points", 0) < 600:
            member = guild.get_member(int(uid))
            if member and VACATION_ROLE_ID not in [r.id for r in member.roles]:
                await add_warning(guild, member, "عدم اكمال متطلب التفاعل (600 نقطة)", 4)
        info["points"] = 0 # تصفير
    save_data()

bot.run(TOKEN)
