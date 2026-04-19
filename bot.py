import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import io
import os

# =========================
# TOKEN CHECK
# =========================

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("TOKEN not found! Add TOKEN in environment variables.")

# =========================
# INTENTS (مهم)
# =========================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# IDS
# =========================

TICKET_PANEL_CHANNEL = 1481127399042322582
LOG_CHANNEL_ID = 1480456866613170267

WARNING_ROLE_ID = 1493332501811171470

# =========================
# ROLES
# =========================

SUPPORT_ROLES = [
1477492633847857252,
1482194383515422752,
1480443913557905499,
1490386915629989948,
1478971845729583276,
1478970736717598840
]

ACTIVITY_ROLES = SUPPORT_ROLES

ROLE_LIST = [
1490075194528759838,
1480443913557905499,
1485560413146841210,
1485549583861022802,
1480649204593332324,
1485551861334540378
]

# =========================
# DATA
# =========================

warnings_data = {}
active_vacations = {}
vacation_balance = {}
points_data = {}
voice_times = {}

# =========================
# HELPERS
# =========================

def has_role(member, roles):
    return any(r.id in roles for r in member.roles)

# =========================
# CLOSE MODAL
# =========================

class CloseModal(discord.ui.Modal, title="اغلاق التكت"):

    reason = discord.ui.TextInput(
        label="سبب الاغلاق",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        channel = interaction.channel
        log = bot.get_channel(LOG_CHANNEL_ID)

        msgs = []

        async for m in channel.history(limit=None, oldest_first=True):
            msgs.append(
                f"[{m.created_at}] {m.author}: {m.content}"
            )

        file = discord.File(
            io.BytesIO("\n".join(msgs).encode()),
            filename="transcript.txt"
        )

        if log:
            await log.send(file=file)

        await interaction.response.send_message(
            "جاري الاغلاق...",
            ephemeral=True
        )

        await asyncio.sleep(2)

        await channel.delete()

# =========================
# WARNING SYSTEM
# =========================

async def add_warning(member, days, reason, staff):

    end = datetime.datetime.utcnow() + datetime.timedelta(days=days)

    warnings_data.setdefault(member.id, []).append({
        "reason": reason,
        "end": end
    })

    role = member.guild.get_role(WARNING_ROLE_ID)

    if role:
        await member.add_roles(role)

@tasks.loop(minutes=1)
async def check_warnings():

    now = datetime.datetime.utcnow()

    for uid in list(warnings_data.keys()):

        active = []

        for w in warnings_data[uid]:

            if w["end"] > now:
                active.append(w)

        if not active:
            warnings_data.pop(uid, None)
        else:
            warnings_data[uid] = active

# =========================
# VACATION SYSTEM
# =========================

class VacationView(discord.ui.View):

    @discord.ui.button(
        label="طلب اجازة",
        style=discord.ButtonStyle.green
    )
    async def req(self, interaction, button):

        if interaction.user.id in warnings_data:
            return await interaction.response.send_message(
                "عليك انذار",
                ephemeral=True
            )

        days = vacation_balance.get(
            interaction.user.id,
            14
        )

        now = datetime.datetime.utcnow()

        active_vacations[interaction.user.id] = {
            "start": now,
            "end": now + datetime.timedelta(days=days),
            "days": days
        }

        vacation_balance[interaction.user.id] = 0

        await interaction.response.send_message(
            "تمت الاجازة",
            ephemeral=True
        )

    @discord.ui.button(
        label="سحب الاجازة",
        style=discord.ButtonStyle.red
    )
    async def withdraw(self, interaction, button):

        if interaction.user.id not in active_vacations:
            return await interaction.response.send_message(
                "لا توجد اجازة",
                ephemeral=True
            )

        vac = active_vacations.pop(
            interaction.user.id
        )

        vacation_balance[interaction.user.id] = vac["days"]

        await interaction.response.send_message(
            "تم السحب",
            ephemeral=True
        )

@tasks.loop(minutes=1)
async def check_vacations():

    now = datetime.datetime.utcnow()

    for uid in list(active_vacations.keys()):

        if active_vacations[uid]["end"] <= now:
            active_vacations.pop(uid, None)

# =========================
# ACTIVITY SYSTEM
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if has_role(message.author, ACTIVITY_ROLES):

        points_data[message.author.id] = (
            points_data.get(message.author.id, 0)
            + 15
        )

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):

    if not has_role(member, ACTIVITY_ROLES):
        return

    now = datetime.datetime.utcnow()

    if before.channel is None and after.channel:

        voice_times[member.id] = now

    elif before.channel and not after.channel:

        start = voice_times.pop(member.id, None)

        if start:

            mins = (now - start).seconds // 60

            points_data[member.id] = (
                points_data.get(member.id, 0)
                + mins * 25
            )

# =========================
# COMMANDS
# =========================

@bot.command()
async def points(ctx, member: discord.Member = None):

    member = member or ctx.author

    await ctx.send(
        f"{member.mention} | نقاط: {points_data.get(member.id,0)}"
    )

# =========================
# READY
# =========================

@bot.event
async def on_ready():

    if not check_warnings.is_running():
        check_warnings.start()

    if not check_vacations.is_running():
        check_vacations.start()

    print(f"Bot Ready {bot.user}")

# =========================
# RUN
# =========================

bot.run(TOKEN)
