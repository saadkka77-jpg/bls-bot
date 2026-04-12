import discord
from discord.ext import commands, tasks
from discord.ui import Select, View, Modal, TextInput, Button
import datetime
import io
import asyncio
import os
import json
from flask import Flask
from threading import Thread

# ==================== كود إبقاء البوت شغال 24 ساعة ====================
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# =================================================================

# ==================== إعدادات السيرفر (النهائية) ====================
TRANSCRIPT_LOG_ID = 1480456866613170267
TICKET_SETUP_CHANNEL_ID = 1481127399042322582

CATEGORY_MAP = {
    "الدعم الفني": 1487721982945394728,
    "شكوى على إداري": 1487709726765748295,
    "تكت متجر": 1487848330804330699
}

SUPPORT_ROLES = [1482194383515422752, 1480443913557905499]
COMPLAINT_ROLES = [1478971845729583276, 1477492633847857252]
STORE_ROLES = [1478958399495340223, 1478971845729583276]

LEAVE_LOG_CHANNEL_ID = 1490820000477610036
LEAVE_ROLE_ID = 1492607429249339502  # رتبة الإجازة
LEAVE_DATA_FILE = "leave_system_data.json"

ticket_counter = 1

# =============================================================

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

def load_data():
    if os.path.exists(LEAVE_DATA_FILE):
        with open(LEAVE_DATA_FILE, "r", encoding="utf-8") as f: 
            try:
                content = json.load(f)
                if "balances" not in content: return {"balances": {}, "active_leaves": {}}
                return content
            except: return {"balances": {}, "active_leaves": {}}
    return {"balances": {}, "active_leaves": {}}

def save_data(data):
    with open(LEAVE_DATA_FILE, "w", encoding="utf-8") as f: 
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- نظام التذاكر ---
class CloseReasonModal(Modal, title='إغلاق التذكرة وتوثيقها'):
    reason = TextInput(label='سبب الإغلاق', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        channel = interaction.channel
        target_member = None
        async for msg in channel.history(limit=50, oldest_first=True):
            if msg.mentions:
                target_member = msg.mentions[0]
                break
        if target_member:
            embed_dm = discord.Embed(title="🔒 تم إغلاق تذكرتك بنجاح", color=0xff4b2b)
            embed_dm.add_field(name="تم إغلاق التذكرة من قبل:", value=interaction.user.mention, inline=False)
            embed_dm.add_field(name="📝 سبب الإغلاق:", value=f"**{self.reason.value}**", inline=False)
            try: await target_member.send(embed=embed_dm)
            except: pass

        transcript = f"سجل تذكرة: {channel.name}\nأغلقت بواسطة: {interaction.user}\nالسبب: {self.reason.value}\n" + "="*30 + "\n"
        async for msg in channel.history(limit=None, oldest_first=True):
            transcript += f"[{msg.created_at.strftime('%H:%M')}] {msg.author}: {msg.content}\n"

        file = discord.File(io.BytesIO(transcript.encode()), filename=f"{channel.name}-log.txt")
        log_ch = bot.get_channel(TRANSCRIPT_LOG_ID)
        if log_ch:
            embed_log = discord.Embed(title="📄 تذكرة مغلقة", color=0x2f3136)
            embed_log.add_field(name="المسؤول:", value=interaction.user.mention)
            await log_ch.send(embed=embed_log, file=file)
        await channel.delete()

class TicketActionsView(View):
    def __init__(self, admin_roles):
        super().__init__(timeout=None)
        self.admin_roles = admin_roles

    @discord.ui.button(label="استلام التذكرة", style=discord.ButtonStyle.green, emoji="🖐️")
    async def claim(self, interaction: discord.Interaction, button: Button):
        user_roles = [role.id for role in interaction.user.roles]
        if not any(r in user_roles for r in self.admin_roles):
            return await interaction.response.send_message("عذراً، هذا الزر للمسؤولين فقط.", ephemeral=True)
        button.disabled = True
        button.label = f"تم الاستلام بواسطة {interaction.user.name}"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="إغلاق", style=discord.ButtonStyle.red, emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CloseReasonModal())

class TicketDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="شكوى على إداري", emoji="💎"),
            discord.SelectOption(label="الدعم الفني", emoji="🛠️"),
            discord.SelectOption(label="تكت متجر", emoji="💰"),
        ]
        super().__init__(placeholder="...اختر القسم المناسب", options=options)

    async def callback(self, interaction: discord.Interaction):
        global ticket_counter
        guild = interaction.guild
        dept = self.values[0]
        roles = SUPPORT_ROLES if dept == "الدعم الفني" else COMPLAINT_ROLES if dept == "شكوى على إداري" else STORE_ROLES
        category = guild.get_channel(CATEGORY_MAP.get(dept))

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for r_id in roles:
            role = guild.get_role(r_id)
            if role: overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ch = await guild.create_text_channel(name=f"{dept}-{ticket_counter}", category=category, overwrites=overwrites)
        ticket_counter += 1
        await interaction.response.send_message(f"تم فتح تذكرتك: {ch.mention}", ephemeral=True)

        embed = discord.Embed(color=discord.Color.blue())
        if dept == "الدعم الفني":
            embed.title = "🛠️ الدعم الفني"
            embed.description = f"حياك اكتب مشكلتك\n**عدم الرد خلال 24 ساعه يلغي التكت**"
        elif dept == "شكوى على إداري":
            embed.title = "💎 شكوى على إداري"
            embed.description = f"حياك اكتب تلخيص الشكوى وارسل الدليل\n**عدم الرد خلال 24 ساعه يلغي التكت**"
        elif dept == "تكت متجر":
            embed.title = "💰 متجر BLS"
            embed.description = f"حياك الله اكتب المنتج الي تبغاه\n**عدم الرد خلال 24 ساعه يلغي التكت**"

        await ch.send(content=f"{interaction.user.mention}", embed=embed, view=TicketActionsView(roles))

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# --- نظام الإجازات ---
class LeaveRequestModal(Modal, title='تقديم طلب إجازة - BLS'):
    duration = TextInput(label='مدة الإجازة (بالأيام)', placeholder='مثال: 3', min_length=1, max_length=2, required=True)
    reason = TextInput(label='سبب الإجازة', style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try: days = int(self.duration.value)
        except: return await interaction.response.send_message("⚠️ يرجى إدخال أرقام فقط.", ephemeral=True)
        uid = str(interaction.user.id)
        data = load_data()
        balance = data["balances"].get(uid, 10)
        if uid in data["active_leaves"]:
            return await interaction.response.send_message("❌ لديك إجازة نشطة بالفعل.", ephemeral=True)
        if days > balance:
            return await interaction.response.send_message(f"❌ رصيدك {balance} يوم فقط.", ephemeral=True)

        end_time = datetime.datetime.now() + datetime.timedelta(days=days)
        data["balances"][uid] = balance - days
        data["active_leaves"][uid] = {"end": end_time.isoformat(), "days_taken": days}
        save_data(data)

        role = interaction.guild.get_role(LEAVE_ROLE_ID)
        if role: await interaction.user.add_roles(role)
        await interaction.response.send_message(f"✅ تم قبول الإجازة. المتبقي: {data['balances'][uid]}", ephemeral=True)

        log_ch = bot.get_channel(LEAVE_LOG_CHANNEL_ID)
        if log_ch:
            embed = discord.Embed(title="🛌 سجل إجازة جديد", color=discord.Color.green())
            embed.add_field(name="الموظف:", value=interaction.user.mention)
            embed.add_field(name="المدة:", value=f"{days} أيام")
            embed.add_field(name="السبب:", value=self.reason.value)
            await log_ch.send(embed=embed)

class LeaveView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تقديم طلب إجازة", style=discord.ButtonStyle.grey, emoji="📝")
    async def request(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(LeaveRequestModal())

    @discord.ui.button(label="سحب الإجازة", style=discord.ButtonStyle.red, emoji="🔙")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        uid = str(interaction.user.id)
        data = load_data()
        if uid not in data["active_leaves"]:
            return await interaction.response.send_message("❌ ليس لديك إجازة نشطة.", ephemeral=True)

        days_to_return = data["active_leaves"][uid]["days_taken"]
        data["balances"][uid] = data["balances"].get(uid, 10) + days_to_return
        del data["active_leaves"][uid]
        save_data(data)

        role = interaction.guild.get_role(LEAVE_ROLE_ID)
        if role: await interaction.user.remove_roles(role)

        await interaction.response.send_message("✅ تم سحب الإجازة واستعادة الرصيد.", ephemeral=True)

        log_ch = bot.get_channel(LEAVE_LOG_CHANNEL_ID)
        if log_ch:
            embed = discord.Embed(title="🔄 سحب إجازة", color=discord.Color.orange())
            embed.add_field(name="الموظف:", value=interaction.user.mention)
            embed.add_field(name="الحالة:", value=f"قام بسحب الإجازة واستعادة {days_to_return} أيام للرصيد.")
            await log_ch.send(embed=embed)

# --- المهام والأحداث ---
@tasks.loop(minutes=30)
async def check_leaves():
    now = datetime.datetime.now()
    data = load_data()
    guild = bot.guilds[0] if bot.guilds else None
    if not guild: return
    changed = False
    for uid, info in list(data["active_leaves"].items()):
        if now > datetime.datetime.fromisoformat(info["end"]):
            member = guild.get_member(int(uid))
            role = guild.get_role(LEAVE_ROLE_ID)
            if member and role: await member.remove_roles(role)
            del data["active_leaves"][uid]
            changed = True
    if changed: save_data(data)

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} يعمل الآن!')
    if not check_leaves.is_running(): check_leaves.start()

@bot.command(aliases=['rl'])
@commands.has_permissions(administrator=True)
async def reset_l(ctx, member: discord.Member):
    data = load_data()
    data["balances"][str(member.id)] = 10
    save_data(data)
    await ctx.send(f"🔄 تم تصفير رصيد {member.mention} إلى 10 أيام.")

@bot.command(aliases=['st'])
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    target_ch = bot.get_channel(TICKET_SETUP_CHANNEL_ID)
    if target_ch:
        embed = discord.Embed(title="**BLS**", description="حياك في خدمة التكت اختر من الاقسام", color=0x2f3136)
        await target_ch.send(embed=embed, view=TicketView())
        await ctx.send("✅ تم النشر.")

@bot.command(aliases=['sl'])
@commands.has_permissions(administrator=True)
async def setup_leave(ctx):
    embed = discord.Embed(title="🏝️ نظام الإجازات الإدارية", description="رصيدك 10 أيام شهرياً.", color=discord.Color.blue())
    await ctx.send(embed=embed, view=LeaveView())

# --- تشغيل البوت مع ميزة الـ Keep Alive ---
keep_alive()
token = os.getenv('DISCORD_TOKEN') or os.getenv('TOKEN')
bot.run(token)
