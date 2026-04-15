from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# استدعاء الوظيفة قبل bot.run
keep_alive()

import discord
from discord.ext import commands, tasks
import datetime
import json
import asyncio
import random
import os

# --- الإعدادات (سحب البيانات من Render) ---
TOKEN = os.getenv('DISCORD_TOKEN') 
LOG_ROOM_ID = 1490820000477610036
WARNING_ROOM_ID = 1480389401535189065
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
GIVEAWAY_CHANNEL_ID = 1485968828059091016
LEAVE_CHANNEL_ID = 1490070238270718013

# --- نظام القيف اوي الأوتوماتيكي ---
class GiveawayModal(discord.ui.Modal, title="إعداد القيف اوي"):
    prize = discord.ui.TextInput(label="ما هي الجائزة؟", placeholder="مثال: رتبة VIP", required=True)
    duration = discord.ui.TextInput(label="مدة السحب (بالدقائق)", placeholder="مثال: 60 لساعة / 1440 ليوم", min_length=1, max_length=6, required=True)
    description = discord.ui.TextInput(label="الوصف أو الشروط", style=discord.TextStyle.paragraph, placeholder="اكتب هنا الشروط...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration.value)
            end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            timestamp = int(end_time.timestamp())

            embed = discord.Embed(title=f"🎉 قيف اوي: {self.prize.value} 🎉", color=0x5865F2)
            embed.description = f"{self.description.value}\n\n**ينتهي السحب:** <t:{timestamp}:R>"
            embed.set_footer(text="اضغط على الزر أدناه للمشاركة!")

            await interaction.response.send_message("✅ جاري إرسال القيف اوي...", ephemeral=True)
            msg = await interaction.channel.send(embed=embed, view=GiveawayView())

            await asyncio.sleep(minutes * 60)
            await end_giveaway_action(msg, self.prize.value)
        except ValueError:
            await interaction.response.send_message("❌ يرجى إدخال رقم صحيح للدقائق.", ephemeral=True)

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = []

    @discord.ui.button(label="(0) مشاركات", style=discord.ButtonStyle.primary, emoji="🎉", custom_id="join_gv_unique")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("❌ أنت مشارك بالفعل!", ephemeral=True)
        self.participants.append(interaction.user.id)
        button.label = f"({len(self.participants)}) مشاركات"
        await interaction.response.edit_message(view=self)

async def end_giveaway_action(message, prize_name):
    view = discord.ui.View.from_message(message)
    participants = []
    for item in view.children:
        if item.custom_id == "join_gv_unique":
            participants = getattr(view, 'participants', [])
    if not participants:
        await message.channel.send(f"😕 انتهى السحب على **{prize_name}** ولكن لم يشارك أحد.")
    else:
        winner_id = random.choice(participants)
        await message.channel.send(f"🎊 مبروك <@{winner_id}>! لقد فزت بـ **{prize_name}** 🎉")
    try: await message.delete()
    except: pass

class GiveawaySetupBtn(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="بدء إعداد الهدية", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GiveawayModal())

# --- نظام الإجازات ---
class VacationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="أخذ إجازة", style=discord.ButtonStyle.success, emoji="📝", custom_id="take_vacation")
    async def take_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if discord.utils.get(interaction.user.roles, id=WARNING_ROLE_ID):
            return await interaction.response.send_message("❌ لا يمكنك طلب إجازة ولديك إنذار إداري.", ephemeral=True)
        await interaction.response.send_modal(LeaveModal())

    @discord.ui.button(label="سحب الإجازة", style=discord.ButtonStyle.danger, emoji="🔙", custom_id="cancel_vacation")
    async def cancel_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        if user_id not in data or not data[user_id].get("on_leave"):
            return await interaction.response.send_message("❌ أنت لست في حالة إجازة حالياً.", ephemeral=True)

        now = datetime.datetime.now()
        start_time = datetime.datetime.fromtimestamp(data[user_id]["leave_start"])
        diff = (now - start_time).total_seconds()
        data[user_id]["cancel_count"] = data[user_id].get("cancel_count", 0) + 1
        should_warn, reason = False, ""

        if diff > 86400:
            should_warn, reason = True, "سحب إجازة بعد مرور 24 ساعة"
        elif data[user_id]["cancel_count"] >= 2:
            should_warn, reason = True, "تكرار طلب وسحب الإجازة (للمرة الثانية)"
            data[user_id]["cancel_count"] = 0

        if should_warn:
            data[user_id]["warning_expiry"] = (now + datetime.timedelta(days=5)).timestamp()
            await issue_warning(interaction.user, reason, 5)

        await interaction.user.remove_roles(interaction.guild.get_role(VACATION_ROLE_ID))
        data[user_id]["on_leave"] = False
        save_data()
        log_ch = bot.get_channel(LOG_ROOM_ID)
        if log_ch: await log_ch.send(embed=discord.Embed(title="⚠️ سحب إجازة", description=f"الموظف: {interaction.user.mention}", color=0xffa500))
        await interaction.response.send_message("⚠️ تم سحب الإجازة بنجاح.", ephemeral=True)

class LeaveModal(discord.ui.Modal, title="طلب إجازة"):
    days = discord.ui.TextInput(label="عدد الأيام", placeholder="3-14", min_length=1, max_length=2)
    async def on_submit(self, interaction: discord.Interaction):
        try: d = int(self.days.value)
        except: return await interaction.response.send_message("❌ رقم غير صحيح.", ephemeral=True)
        if d < 3: return await interaction.response.send_message("❌ الحد الأدنى 3 أيام.", ephemeral=True)

        user_id = str(interaction.user.id)
        user_info = data.get(user_id, {"days_used": 0, "on_leave": False, "cancel_count": 0})
        if user_info["days_used"] + d > 14:
            return await interaction.response.send_message(f"❌ رصيدك لا يكفي.", ephemeral=True)

        user_info["on_leave"], user_info["leave_start"] = True, datetime.datetime.now().timestamp()
        user_info["days_used"] += d
        data[user_id] = user_info
        save_data()
        await interaction.user.add_roles(interaction.guild.get_role(VACATION_ROLE_ID))
        log_ch = bot.get_channel(LOG_ROOM_ID)
        if log_ch: await log_ch.send(embed=discord.Embed(title="✅ طلب إجازة جديد", description=f"الموظف: {interaction.user.mention}\nالمدة: {d} يوم", color=0x00ff00))
        await interaction.response.send_message(f"✅ تم قبول إجازتك لمدة {d} أيام.", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members, intents.message_content = True, True
        super().__init__(command_prefix='!', intents=intents)
    async def setup_hook(self):
        self.add_view(VacationPanel())
        self.add_view(GiveawayView())

bot = MyBot()
data = {}

def save_data():
    with open('data.json', 'w') as f: json.dump(data, f)
def load_data():
    global data
    try:
        with open('data.json', 'r') as f: data = json.load(f)
    except: data = {}

async def issue_warning(member, reason, days):
    warn_ch, role = bot.get_channel(WARNING_ROOM_ID), member.guild.get_role(WARNING_ROLE_ID)
    if not role or not warn_ch: return
    await member.add_roles(role)
    embed = discord.Embed(title="⚠️ إنذار إداري تلقائي", color=0xff0000)
    embed.add_field(name="الموظف:", value=member.mention, inline=False)
    embed.add_field(name="السبب:", value=reason, inline=False)
    embed.set_footer(text=f"مدة الإنذار: {days} أيام")
    await warn_ch.send(embed=embed)

@tasks.loop(minutes=30)
async def check_expirations():
    now = datetime.datetime.now().timestamp()
    for user_id, info in list(data.items()):
        if info.get("warning_expiry") and now > info["warning_expiry"]:
            for guild in bot.guilds:
                member = guild.get_member(int(user_id))
                if member:
                    role = guild.get_role(WARNING_ROLE_ID)
                    if role in member.roles: await member.remove_roles(role)
            info["warning_expiry"] = None
            save_data()

@bot.event
async def on_ready():
    load_data()
    if not check_expirations.is_running(): check_expirations.start()
    print(f'Logged in as {bot.user.name}')

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_vacation(ctx):
    await ctx.message.delete()
    embed = discord.Embed(title="📦 نظام إجازات الموظفين", color=0x0000ff)
    embed.description = "استخدم الأزرار أدناه للتحكم في إجازتك."
    await ctx.send(embed=embed, view=VacationPanel())

@bot.command()
@commands.has_permissions(administrator=True)
async def giveaway(ctx):
    if ctx.channel.id != GIVEAWAY_CHANNEL_ID: return
    await ctx.message.delete()
    await ctx.send("⚙️ لوحة إعداد الهدية:", view=GiveawaySetupBtn(), delete_after=30)

@bot.command()
@commands.has_permissions(administrator=True)
async def unwarn(ctx, member: discord.Member):
    await ctx.message.delete()
    role = ctx.guild.get_role(WARNING_ROLE_ID)
    if role and role in member.roles: 
        await member.remove_roles(role)
    if str(member.id) in data:
        data[str(member.id)]["warning_expiry"] = None
        save_data()
    await ctx.send(f"✅ تم سحب الإنذار عن {member.mention}.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def reset_days(ctx, member: discord.Member):
    await ctx.message.delete()
    if str(member.id) in data:
        data[str(member.id)]["days_used"] = 0
        data[str(member.id)]["cancel_count"] = 0
        save_data()
        await ctx.send(f"✅ تم تصفير بيانات {member.mention}.", delete_after=5)

bot.run("DISCORD_TOKEN")
