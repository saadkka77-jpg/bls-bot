import discord
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import datetime
import json
import random
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
LOG_VACATION_ID = 1490820000477610036
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
BANNER_URL = "https://cloud-388m17uha-static-dot-nodes-site.googleusercontent.com/static.png"

ADMIN_ROLES = [1490386915629989948, 1478971845729583276]
SUPPORT_ROLES = [1482194383515422752, 1480443913557905499]
STORE_ROLES = [1490386915629989948, 1478971845729583276]

# --- نظام التذاكر ---

class TicketCloseModal(discord.ui.Modal, title="إغلاق التذكرة"):
    reason = discord.ui.TextInput(label="سبب الإغلاق", style=discord.TextStyle.paragraph, placeholder="اكتب السبب هنا...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        log_content = ""
        async for message in interaction.channel.history(limit=500, oldest_first=True):
            time = message.created_at.strftime("%Y-%m-%d %H:%M")
            log_content += f"[{time}] {message.author}: {message.content}\n"

        log_ch = interaction.client.get_channel(LOG_TICKET_ID)
        if log_ch:
            file = discord.File(fp=io.BytesIO(log_content.encode()), filename=f"ticket-{interaction.channel.name}.txt")
            embed = discord.Embed(title="🔒 تذكرة مغلقة", color=discord.Color.red())
            embed.add_field(name="صاحب التذكرة:", value=interaction.channel.topic or "غير معروف")
            embed.add_field(name="أغلق بواسطة:", value=interaction.user.mention)
            embed.add_field(name="السبب:", value=self.reason.value, inline=False)
            embed.timestamp = datetime.datetime.now()
            await log_ch.send(embed=embed, file=file)

        try:
            owner_id = int(interaction.channel.name.split('-')[-1])
            owner = interaction.guild.get_member(owner_id)
            if owner:
                await owner.send(f"⚠️ تم إغلاق تذكرتك في سيرفر BLS\n**بواسطة:** {interaction.user.mention}\n**السبب:** {self.reason.value}")
        except: pass
        await interaction.channel.delete()

class TicketActionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.success, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        # التحقق من الصلاحيات
        staff_roles = ADMIN_ROLES + SUPPORT_ROLES + STORE_ROLES
        if not any(role.id in staff_roles for role in interaction.user.roles):
            return await interaction.response.send_message("❌ ليس لديك صلاحية استلام التذكرة.", ephemeral=True)

        button.disabled = True
        button.label = f"استلمها: {interaction.user.display_name}"
        
        overwrites = interaction.channel.overwrites
        for role_id in staff_roles:
            role = interaction.guild.get_role(role_id)
            if role: overwrites[role] = discord.PermissionOverwrite(send_messages=False, read_messages=True)
        
        overwrites[interaction.user] = discord.PermissionOverwrite(send_messages=True, read_messages=True)
        await interaction.channel.edit(overwrites=overwrites)
        
        user_id = str(interaction.user.id)
        data[user_id] = data.get(user_id, {"points": 0})
        data[user_id]["points"] += 50
        save_data()

        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"✅ {interaction.user.mention} استلم التذكرة، سيتم الرد عليك قريباً.")

    @discord.ui.button(label="إغلاق التذكرة", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketCloseModal())

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="الدعم الفني", emoji="🛠️", value="support"),
            discord.SelectOption(label="طلب رانك", emoji="🎖️", value="rank"),
            discord.SelectOption(label="شكوى على شخص", emoji="👤", value="report_user"),
            discord.SelectOption(label="شكوى على إداري", emoji="👔", value="report_staff"),
            discord.SelectOption(label="تكت المتجر", emoji="🛒", value="store"),
        ]
        super().__init__(placeholder="اختر نوع التذكرة...", options=options, custom_id="ticket_dropdown_main")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user
        val = self.values[0]
        channel_name = f"ticket-{val}-{user.id}"
        
        view_roles = ADMIN_ROLES.copy()
        if val in ["support", "rank", "report_user", "report_staff"]:
            view_roles += SUPPORT_ROLES
        elif val == "store":
            view_roles += STORE_ROLES

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for r_id in view_roles:
            role = guild.get_role(r_id)
            if role: overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await guild.create_text_channel(channel_name, overwrites=overwrites, topic=user.mention)
        embed = discord.Embed(title="حياكم الله في خدمة تكت BLS", description="سيقوم الفريق المختص بالرد عليك قريباً.", color=0x2f3136)
        embed.set_image(url=BANNER_URL)
        await channel.send(content=f"{user.mention} | إدارة القسم", embed=embed, view=TicketActionView())
        await interaction.response.send_message(f"✅ تم فتح تذكرتك: {channel.mention}", ephemeral=True)

class PersistentTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- نظام الإجازات ---

class VacationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="أخذ إجازة", style=discord.ButtonStyle.success, emoji="📝", custom_id="vac_take")
    async def take(self, interaction: discord.Interaction, button: discord.ui.Button):
        if discord.utils.get(interaction.user.roles, id=WARNING_ROLE_ID):
            return await interaction.response.send_message("❌ لديك إنذار نشط.", ephemeral=True)
        await interaction.response.send_modal(LeaveModal())

    @discord.ui.button(label="سحب الإجازة", style=discord.ButtonStyle.danger, emoji="🔙", custom_id="vac_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in data or not data[user_id].get("on_leave"):
            return await interaction.response.send_message("❌ لست في إجازة.", ephemeral=True)

        now = datetime.datetime.now()
        start = datetime.datetime.fromtimestamp(data[user_id]["leave_start"])
        diff = (now - start).total_seconds()
        data[user_id]["cancel_count"] = data[user_id].get("cancel_count", 0) + 1
        
        if diff > 86400 or data[user_id]["cancel_count"] >= 2:
            await issue_escalated_warning(interaction.user, "سحب إجازة مخالف للشروط")

        await interaction.user.remove_roles(interaction.guild.get_role(VACATION_ROLE_ID))
        data[user_id]["on_leave"] = False
        save_data()
        await interaction.response.send_message("⚠️ تم سحب الإجازة.", ephemeral=True)

class LeaveModal(discord.ui.Modal, title="طلب إجازة (الحد 14 يوم)"):
    days = discord.ui.TextInput(label="المدة بالأيام", min_length=1, max_length=2)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            d = int(self.days.value)
            if d > 14: return await interaction.response.send_message("الحد 14 يوم", ephemeral=True)
            user_id = str(interaction.user.id)
            data[user_id] = data.get(user_id, {})
            data[user_id].update({"on_leave": True, "leave_start": datetime.datetime.now().timestamp()})
            save_data()
            await interaction.user.add_roles(interaction.guild.get_role(VACATION_ROLE_ID))
            await interaction.response.send_message(f"✅ تم تسجيل إجازتك: {d} يوم", ephemeral=True)
        except: await interaction.response.send_message("خطأ في الرقم", ephemeral=True)

# --- المهام والبيانات ---

def save_data():
    with open('data.json', 'w') as f: json.dump(data, f)

async def issue_escalated_warning(member, reason):
    user_id = str(member.id)
    data[user_id] = data.get(user_id, {"warns": 0})
    data[user_id]["warns"] += 1
    count = data[user_id]["warns"]
    expiry = datetime.datetime.now() + datetime.timedelta(days=5 * count)
    data[user_id]["warning_expiry"] = expiry.timestamp()
    save_data()
    role = member.guild.get_role(WARNING_ROLE_ID)
    if role: await member.add_roles(role)
    ch = member.guild.get_channel(WARNING_ROOM_ID)
    if ch:
        embed = discord.Embed(title="⚠️ إنذار إداري تصاعدي", color=0xff0000)
        embed.description = f"**الموظف:** {member.mention}\n**السبب:** {reason}\n**المستوى:** {count}"
        await ch.send(embed=embed)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.all())
    
    async def setup_hook(self):
        # هنا الإصلاح: إضافة الـ Views كـ Persistent
        self.add_view(TicketActionView())
        self.add_view(VacationPanel())
        self.add_view(PersistentTicketView())

bot = MyBot()
data = {}

@bot.event
async def on_ready():
    global data
    if os.path.exists('data.json'):
        with open('data.json', 'r') as f: data = json.load(f)
    print(f"Logged in as {bot.user}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    if ctx.channel.id != TICKET_SETUP_CHANNEL: return
    await ctx.message.delete()
    embed = discord.Embed(title="مركز تذاكر BLS", description="اختر القسم المناسب أدناه.", color=0x2f3136)
    embed.set_image(url=BANNER_URL)
    await ctx.send(embed=embed, view=PersistentTicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_vacation(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="📦 نظام إجازات الموظفين", color=0x0000ff)
    embed.description = "سحب الإجازة بعد 24 ساعة يعرضك لإنذار."
    await ctx.send(embed=embed, view=VacationPanel())

@bot.command()
@commands.has_permissions(administrator=True)
async def unwarn(ctx, member: discord.Member):
    if ctx.channel.id != WARNING_ROOM_ID: return
    user_id = str(member.id)
    if user_id in data: data[user_id]["warning_expiry"] = None
    save_data()
    role = ctx.guild.get_role(WARNING_ROLE_ID)
    if role: await member.remove_roles(role)
    await ctx.send(f"✅ تم سحب الإنذار عن {member.mention}")

bot.run(TOKEN)
