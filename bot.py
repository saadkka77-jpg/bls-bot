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
def home(): return "BLS System is Fully Active!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()
keep_alive()

# --- الإعدادات والمعرفات الأساسية ---
TOKEN = os.getenv('TOKEN')
GUILD_ID = 1206680459523297311 
LOG_TICKET_ID = 1480456866613170267
TICKET_SETUP_CHANNEL = 1481127399042322582
WARNING_ROOM_ID = 1480389401535189065
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

# --- 1. إدارة البيانات (قاعدة البيانات) ---
def load_data():
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f: return json.load(f)
        except: return {"users": {}, "ticket_count": 0}
    return {"users": {}, "ticket_count": 0}

data = load_data()

def save_data():
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 2. نظام الإنذارات الآلي ---
async def add_warning(guild, member, reason, days):
    uid = str(member.id)
    if uid not in data["users"]: data["users"][uid] = {"warns": 0, "points": 0}
    data["users"][uid]["warns"] += 1
    expiry = datetime.datetime.now() + datetime.timedelta(days=days)
    data["users"][uid]["warn_expiry"] = expiry.timestamp()
    save_data()
    
    role = guild.get_role(WARNING_ROLE_ID)
    if role: await member.add_roles(role)
    
    ch = guild.get_channel(WARNING_ROOM_ID)
    if ch:
        embed = discord.Embed(title="⚠️ تسجيل إنذار جديد", color=0xff0000)
        embed.description = f"**الموظف:** {member.mention}\n**السبب:** {reason}\n**المدة:** {days} أيام\n**عدد إنذاراته:** {data['users'][uid]['warns']}"
        await ch.send(content=member.mention, embed=embed)

# --- 3. نظام التذاكر المتطور ---
class TicketCloseModal(discord.ui.Modal, title="إغلاق التذكرة"):
    reason = discord.ui.TextInput(label="سبب الإغلاق", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        log_content = f"Ticket Log for {interaction.channel.name}\n"
        async for message in interaction.channel.history(limit=500, oldest_first=True):
            log_content += f"[{message.created_at.strftime('%Y-%m-%d %H:%M')}] {message.author}: {message.content}\n"
        
        # إرسال اللوق
        log_ch = interaction.client.get_channel(LOG_TICKET_ID)
        if log_ch:
            file = discord.File(fp=io.BytesIO(log_content.encode()), filename=f"{interaction.channel.name}.txt")
            await log_ch.send(f"تم إغلاق التذكرة بواسطة {interaction.user.mention}", file=file)

        # رسالة الخاص (نفس الصورة المطلوبة)
        try:
            owner_mention = interaction.channel.topic
            owner_id = int(''.join(filter(str.isdigit, owner_mention)))
            owner = interaction.guild.get_member(owner_id)
            if owner:
                dm_emb = discord.Embed(title="🔒 تم إغلاق تذكرتك بنجاح", color=0xff4500)
                dm_emb.description = f"**تم إغلاق التذكرة من قبل:**\n{interaction.user.mention}\n\n**📅 التاريخ والوقت:**\n`{datetime.datetime.now().strftime('%Y-%m-%d | %H:%M:%S')}`\n\n**📝 سبب الإغلاق:**\n{self.reason.value}\n\n**🌐 السيرفر:**\nBLS\nنظام إدارة تذاكر BLS"
                await owner.send(embed=dm_emb)
        except: pass
        await interaction.channel.delete()

class TicketActionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="استلام", style=discord.ButtonStyle.success, custom_id="claim_t")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(r.id in ADMIN_ROLES + SUPPORT_ROLES for r in interaction.user.roles):
            return await interaction.response.send_message("للإدارة فقط!", ephemeral=True)
        button.disabled = True; button.label = f"استلمها: {interaction.user.display_name}"
        uid = str(interaction.user.id)
        data["users"][uid] = data["users"].get(uid, {"points": 0})
        data["users"][uid]["points"] += 50 # محرك النقاط: 50 للاستلام
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
            discord.SelectOption(label="شكوى إداري", value="report_staff", emoji="👔")
        ]
        super().__init__(placeholder="اختر القسم المناسب...", options=options, custom_id="main_drop")
    async def callback(self, interaction: discord.Interaction):
        data["ticket_count"] += 1
        ch = await interaction.guild.create_text_channel(
            name=f"ticket-{data['ticket_count']}",
            category=interaction.guild.get_channel(TICKET_CATEGORIES.get(self.values[0])),
            topic=interaction.user.mention
        )
        save_data()
        emb = discord.Embed(title="نظام تذاكر BLS", description="سيتم الرد عليك قريباً.", color=0x2f3136)
        emb.set_image(url=BANNER_URL)
        await ch.send(content=f"{interaction.user.mention}", embed=emb, view=TicketActionView())
        await interaction.response.send_message(f"✅ تم فتح التذكرة: {ch.mention}", ephemeral=True)

# --- 4. نظام الإجازات ---
class LeaveModal(discord.ui.Modal, title="طلب إجازة"):
    days = discord.ui.TextInput(label="المدة بالأيام (الحد 14)", min_length=1, max_length=2)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = int(self.days.value)
            if d > 14: return await interaction.response.send_message("الحد الأقصى 14 يوم!", ephemeral=True)
            uid = str(interaction.user.id)
            data["users"][uid] = data["users"].get(uid, {"points": 0})
            data["users"][uid].update({"on_leave": True, "leave_start": datetime.datetime.now().timestamp()})
            save_data()
            role = interaction.guild.get_role(VACATION_ROLE_ID)
            if role: await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ تم تسجيل إجازتك لمدة {d} يوم.", ephemeral=True)
        except: await interaction.response.send_message("أدخل رقم صحيح!", ephemeral=True)

class VacationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="طلب إجازة", style=discord.ButtonStyle.success, custom_id="v_take")
    async def take(self, interaction: discord.Interaction, b: discord.ui.Button):
        uid = str(interaction.user.id)
        if data["users"].get(uid, {}).get("warn_expiry"):
            return await interaction.response.send_message("❌ لا يمكنك طلب إجازة ولديك إنذار!", ephemeral=True)
        await interaction.response.send_modal(LeaveModal())
    @discord.ui.button(label="سحب إجازة", style=discord.ButtonStyle.danger, custom_id="v_cancel")
    async def cancel(self, interaction: discord.Interaction, b: discord.ui.Button):
        uid = str(interaction.user.id)
        if not data["users"].get(uid, {}).get("on_leave"): return
        diff = datetime.datetime.now().timestamp() - data["users"][uid]["leave_start"]
        if diff > 86400: # عقوبة سحب بعد 24 ساعة
            await add_warning(interaction.guild, interaction.user, "سحب إجازة متأخر", 5)
        role = interaction.guild.get_role(VACATION_ROLE_ID)
        if role: await interaction.user.remove_roles(role)
        data["users"][uid]["on_leave"] = False; save_data()
        await interaction.response.send_message("تم سحب الإجازة.", ephemeral=True)

# --- 5. نظام الاستدعاء الإداري ---
class SummonView(discord.ui.View):
    def __init__(self, target_id):
        super().__init__(timeout=86400)
        self.target_id = target_id
    @discord.ui.button(label="حضر", style=discord.ButtonStyle.success, emoji="✅")
    async def present(self, interaction: discord.Interaction, b: discord.ui.Button):
        await interaction.response.send_message("تم تسجيل الحضور."); self.stop()
    @discord.ui.button(label="عدم حضور", style=discord.ButtonStyle.danger, emoji="❌")
    async def absent(self, interaction: discord.Interaction, b: discord.ui.Button):
        m = interaction.guild.get_member(self.target_id)
        if m: await add_warning(interaction.guild, m, "عدم حضور استدعاء", 7)
        await interaction.response.send_message("تم تسجيل غياب وإنذار 7 أيام."); self.stop()

# --- 6. كلاس البوت الرئيسي (محرك النقاط + الجرد) ---
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix='!', intents=discord.Intents.all())
    async def setup_hook(self):
        self.add_view(TicketActionView()); self.add_view(VacationPanel())
        self.add_view(discord.ui.View().add_item(TicketDropdown()))
        self.warning_check.start(); self.voice_points.start(); self.biweekly_check.start()

    @tasks.loop(minutes=30)
    async def warning_check(self): # نظام سحب الإنذارات الآلي
        guild = self.get_guild(GUILD_ID)
        if not guild: return
        now = datetime.datetime.now().timestamp()
        for uid, info in list(data["users"].items()):
            if info.get("warn_expiry") and now > info["warn_expiry"]:
                m = guild.get_member(int(uid))
                if m:
                    r = guild.get_role(WARNING_ROLE_ID)
                    if r: await m.remove_roles(r)
                info["warn_expiry"] = None; save_data()

    @tasks.loop(minutes=1)
    async def voice_points(self): # محرك نقاط الفويس
        for guild in self.guilds:
            for vc in guild.voice_channels:
                for m in vc.members:
                    if not m.bot and VACATION_ROLE_ID not in [r.id for r in m.roles]:
                        uid = str(m.id)
                        data["users"][uid] = data["users"].get(uid, {"points": 0})
                        data["users"][uid]["points"] += 25; save_data()

    @tasks.loop(hours=336)
    async def biweekly_check(self): # نظام الجرد الآلي (كل أسبوعين)
        guild = self.get_guild(GUILD_ID)
        for uid, info in list(data["users"].items()):
            if info.get("points", 0) < 600:
                m = guild.get_member(int(uid))
                if m and VACATION_ROLE_ID not in [r.id for r in m.roles]:
                    await add_warning(guild, m, "تقصير في التفاعل (أقل من 600 نقطة)", 4)
            info["points"] = 0; save_data()

bot = MyBot()

@bot.event
async def on_message(message):
    if not message.author.bot: # محرك نقاط الشات
        uid = str(message.author.id)
        data["users"][uid] = data["users"].get(uid, {"points": 0})
        data["users"][uid]["points"] += 20; save_data()
    await bot.process_commands(message)

# --- الأوامر ---
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    view = discord.ui.View(timeout=None).add_item(TicketDropdown())
    await ctx.send(embed=discord.Embed(title="مركز تذاكر BLS", color=0x2f3136).set_image(url=BANNER_URL), view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def summon(ctx, member: discord.Member):
    await ctx.send(f"⚠️ {member.mention} استدعاء إداري في <#{SUMMON_TARGET_ROOM}>", view=SummonView(member.id))

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_vacation(ctx):
    await ctx.send(embed=discord.Embed(title="نظام الإجازات", description="اضغط لطلب إجازة"), view=VacationPanel())

bot.run(TOKEN)
