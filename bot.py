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

# --- الإعدادات والمعرفات (تأكد من صحتها) ---
TOKEN = os.getenv('TOKEN')
GUILD_ID = 1206680459523297311 # استبدل هذا بآيدي سيرفرك الحقيقي
LOG_TICKET_ID = 1480456866613170267
TICKET_SETUP_CHANNEL = 1481127399042322582
WARNING_ROOM_ID = 1480389401535189065
SUMMON_TARGET_ROOM = 1480670493324607651
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
BANNER_URL = "https://cloud-388m17uha-static-dot-nodes-site.googleusercontent.com/static.png"

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
        try:
            with open('data.json', 'r') as f: return json.load(f)
        except: return {"users": {}, "ticket_count": 0}
    return {"users": {}, "ticket_count": 0}

data = load_data()

def save_data():
    with open('data.json', 'w') as f: json.dump(data, f)

# --- نظام الإنذارات الآلي ---
async def add_warning(guild, member, reason, days):
    uid = str(member.id)
    data["users"][uid] = data["users"].get(uid, {"warns": 0, "points": 0})
    data["users"][uid]["warns"] += 1
    
    expiry = datetime.datetime.now() + datetime.timedelta(days=days)
    data["users"][uid]["warn_expiry"] = expiry.timestamp()
    save_data()
    
    role = guild.get_role(WARNING_ROLE_ID)
    if role: await member.add_roles(role)
    
    ch = guild.get_channel(WARNING_ROOM_ID)
    if ch:
        embed = discord.Embed(title="⚠️ تسجيل إنذار جديد", color=0xff0000)
        embed.description = f"**الموظف:** {member.mention}\n**السبب:** {reason}\n**المدة:** {days} أيام\n**المستوى:** {data['users'][uid]['warns']}"
        await ch.send(content=member.mention, embed=embed)

# --- نظام التذاكر (Views & Modals) ---
class TicketCloseModal(discord.ui.Modal, title="إغلاق التذكرة"):
    reason = discord.ui.TextInput(label="سبب الإغلاق", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        log_content = ""
        async for message in interaction.channel.history(limit=500, oldest_first=True):
            log_content += f"[{message.created_at.strftime('%Y-%m-%d %H:%M')}] {message.author}: {message.content}\n"

        log_ch = interaction.client.get_channel(LOG_TICKET_ID)
        owner_mention = interaction.channel.topic or "غير معروف"
        
        file = discord.File(fp=io.BytesIO(log_content.encode()), filename=f"ticket-{interaction.channel.name}.txt")
        embed = discord.Embed(title="🔒 تم إغلاق التذكرة", color=discord.Color.red())
        embed.add_field(name="بواسطة:", value=interaction.user.mention)
        embed.add_field(name="السبب:", value=self.reason.value)
        if log_ch: await log_ch.send(embed=embed, file=file)

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
        if not any(r.id in ADMIN_ROLES + SUPPORT_ROLES for r in interaction.user.roles):
            return await interaction.response.send_message("لا تملك صلاحية الاستلام", ephemeral=True)
        button.disabled = True
        button.label = f"استلمها: {interaction.user.display_name}"
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
        options = [
            discord.SelectOption(label="دعم فني", value="support", emoji="🛠️"),
            discord.SelectOption(label="متجر", value="store", emoji="🛒"),
            discord.SelectOption(label="شكوى إداري", value="report_staff", emoji="👔"),
            discord.SelectOption(label="طلب رانك", value="rank", emoji="🎖️"),
            discord.SelectOption(label="شكوى شخص", value="report_user", emoji="👤")
        ]
        super().__init__(placeholder="اختر قسم التذكرة...", options=options, custom_id="main_drop")

    async def callback(self, interaction: discord.Interaction):
        data["ticket_count"] = data.get("ticket_count", 0) + 1
        count = data["ticket_count"]
        val = self.values[0]
        cat_id = TICKET_CATEGORIES.get(val)
        category = interaction.guild.get_channel(cat_id)
        
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{count}",
            category=category,
            topic=interaction.user.mention
        )
        save_data()
        embed = discord.Embed(title="حياكم الله في خدمة تكت BLS", description="سيتم الرد عليك قريباً من قبل الفريق المختص.", color=0x2f3136)
        embed.set_image(url=BANNER_URL)
        await channel.send(content=f"{interaction.user.mention} | إدارة القسم", embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True)

class PersistentTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- نظام الإجازات ---
class LeaveModal(discord.ui.Modal, title="طلب إجازة (الحد 14 يوم)"):
    days = discord.ui.TextInput(label="المدة بالأيام", min_length=1, max_length=2)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = int(self.days.value)
            if d > 14: return await interaction.response.send_message("الحد الأقصى 14 يوم", ephemeral=True)
            uid = str(interaction.user.id)
            data["users"][uid] = data["users"].get(uid, {})
            data["users"][uid].update({"on_leave": True, "leave_start": datetime.datetime.now().timestamp()})
            save_data()
            role = interaction.guild.get_role(VACATION_ROLE_ID)
            if role: await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ تم تسجيل إجازتك لمدة {d} يوم", ephemeral=True)
        except: await interaction.response.send_message("يرجى إدخال رقم صحيح", ephemeral=True)

class VacationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="طلب إجازة", style=discord.ButtonStyle.success, emoji="📝", custom_id="v_take")
    async def take(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if data["users"].get(uid, {}).get("warn_expiry"):
            return await interaction.response.send_message("❌ لا يمكنك طلب إجازة ولديك إنذار نشط.", ephemeral=True)
        await interaction.response.send_modal(LeaveModal())

    @discord.ui.button(label="سحب إجازة", style=discord.ButtonStyle.danger, emoji="🔙", custom_id="v_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if not data["users"].get(uid, {}).get("on_leave"):
            return await interaction.response.send_message("❌ لست في حالة إجازة حالياً.", ephemeral=True)
        
        now = datetime.datetime.now()
        start_ts = data["users"][uid].get("leave_start", now.timestamp())
        diff = now.timestamp() - start_ts
        
        # منطق الإنذار: سحب بعد يوم (86400 ثانية)
        if diff > 86400:
            await add_warning(interaction.guild, interaction.user, "سحب إجازة بعد مرور 24 ساعة", 5)
        
        role = interaction.guild.get_role(VACATION_ROLE_ID)
        if role: await interaction.user.remove_roles(role)
        data["users"][uid]["on_leave"] = False
        save_data()
        await interaction.response.send_message("⚠️ تم سحب الإجازة بنجاح.", ephemeral=True)

# --- نظام الاستدعاء ---
class SummonView(discord.ui.View):
    def __init__(self, target_id):
        super().__init__(timeout=86400)
        self.target_id = target_id
    
    @discord.ui.button(label="حضر", style=discord.ButtonStyle.success, emoji="✅")
    async def present(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("تم تسجيل حضور الموظف.")
        self.stop()

    @discord.ui.button(label="عدم حضور", style=discord.ButtonStyle.danger, emoji="❌")
    async def absent(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.guild.get_member(self.target_id)
        if member: await add_warning(interaction.guild, member, "عدم حضور الاستدعاء الإداري", 7)
        await interaction.response.send_message("تم تسجيل الغياب وإصدار إنذار 7 أيام.")
        self.stop()

# --- كلاس البوت الرئيسي ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.all())

    async def setup_hook(self):
        self.add_view(TicketActionView())
        self.add_view(VacationPanel())
        self.add_view(PersistentTicketView())
        self.warning_check.start()
        self.voice_points.start()
        self.biweekly_check.start()

    @tasks.loop(minutes=30)
    async def warning_check(self):
        guild = self.get_guild(GUILD_ID)
        if not guild: return
        now = datetime.datetime.now().timestamp()
        for uid, info in list(data["users"].items()):
            if info.get("warn_expiry") and now > info["warn_expiry"]:
                member = guild.get_member(int(uid))
                if member:
                    role = guild.get_role(WARNING_ROLE_ID)
                    if role: await member.remove_roles(role)
                    ch = guild.get_channel(WARNING_ROOM_ID)
                    if ch: await ch.send(f"✅ تم سحب الإنذار تلقائياً عن {member.mention}")
                info["warn_expiry"] = None
        save_data()

    @tasks.loop(minutes=1)
    async def voice_points(self):
        for guild in self.guilds:
            for vc in guild.voice_channels:
                for m in vc.members:
                    if not m.bot and VACATION_ROLE_ID not in [r.id for r in m.roles]:
                        uid = str(m.id)
                        data["users"][uid] = data["users"].get(uid, {"points": 0})
                        data["users"][uid]["points"] += 25
        save_data()

    @tasks.loop(hours=336)
    async def biweekly_check(self):
        guild = self.get_guild(GUILD_ID)
        if not guild: return
        for uid, info in list(data["users"].items()):
            if info.get("points", 0) < 600:
                member = guild.get_member(int(uid))
                if member and VACATION_ROLE_ID not in [r.id for r in member.roles]:
                    await add_warning(guild, member, "عدم اكمال متطلب التفاعل (600 نقطة)", 4)
            info["points"] = 0
        save_data()

bot = MyBot()

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.content.startswith('!'):
        await asyncio.sleep(0.5)
        try: await message.delete()
        except: pass
    
    uid = str(message.author.id)
    data["users"][uid] = data["users"].get(uid, {"points": 0})
    data["users"][uid]["points"] += 20 # نقاط الشات
    save_data()
    await bot.process_commands(message)

# --- الأوامر ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    if ctx.channel.id != TICKET_SETUP_CHANNEL: return
    embed = discord.Embed(title="مركز تذاكر BLS", description="اختر القسم المناسب أدناه.", color=0x2f3136)
    embed.set_image(url=BANNER_URL)
    await ctx.send(embed=embed, view=PersistentTicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_vacation(ctx):
    embed = discord.Embed(title="📦 نظام إجازات الموظفين", description="الحد الأقصى للإجازة 14 يوم شهرياً.\nسحب الإجازة بعد 24 ساعة يعرضك لإنذار.", color=0x0000ff)
    await ctx.send(embed=embed, view=VacationPanel())

@bot.command()
@commands.has_permissions(administrator=True)
async def summon(ctx, member: discord.Member):
    embed = discord.Embed(title="🔔 است
