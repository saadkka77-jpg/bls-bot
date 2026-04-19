import discord
from discord.ext import commands
import asyncio
import datetime
import io
import os

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("TOKEN not found! Add TOKEN in environment variables.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# IDS
# =========================

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

# الرتب المسموح إعطاؤها (من كودك القديم)

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
# TICKET SYSTEM
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


class TicketButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام", style=discord.ButtonStyle.green)
    async def claim(self, interaction, button):

        if not has_role(interaction.user, SUPPORT_ROLES):
            return await interaction.response.send_message(
                "لا تملك صلاحية",
                ephemeral=True
            )

        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="اغلاق", style=discord.ButtonStyle.red)
    async def close(self, interaction, button):
        await interaction.response.send_modal(CloseModal())


class TicketPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="فتح تكت", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction, button):

        guild = interaction.guild

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
        }

        for role_id in SUPPORT_ROLES:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True
                )

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            overwrites=overwrites
        )

        await channel.send(
            f"{interaction.user.mention}",
            view=TicketButtons()
        )

        await interaction.response.send_message(
            f"تم فتح التكت: {channel.mention}",
            ephemeral=True
        )

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

# =========================
# ROLE SYSTEM
# =========================

class RoleSelect(discord.ui.Select):

    def __init__(self, member, action):

        self.member = member
        self.action = action

        options = []

        for role_id in ROLE_LIST:
            role = member.guild.get_role(role_id)
            if role:
                options.append(
                    discord.SelectOption(
                        label=role.name,
                        value=str(role.id)
                    )
                )

        super().__init__(
            placeholder="اختر رتبة",
            options=options
        )

    async def callback(self, interaction):

        role = interaction.guild.get_role(
            int(self.values[0])
        )

        if self.action == "give":

            await self.member.add_roles(role)
            msg = f"تم اعطاء {role.mention}"

        else:

            await self.member.remove_roles(role)
            msg = f"تم سحب {role.mention}"

        await interaction.response.send_message(
            msg,
            ephemeral=True
        )


class ActionSelect(discord.ui.Select):

    def __init__(self, member):

        self.member = member

        super().__init__(
            placeholder="اختر العملية",
            options=[
                discord.SelectOption(
                    label="اعطاء",
                    value="give"
                ),
                discord.SelectOption(
                    label="سحب",
                    value="remove"
                )
            ]
        )

    async def callback(self, interaction):

        view = discord.ui.View()

        view.add_item(
            RoleSelect(
                self.member,
                self.values[0]
            )
        )

        await interaction.response.edit_message(
            content="اختر الرتبة",
            view=view
        )

# =========================
# COMMANDS
# =========================

@bot.command()
async def ticketpanel(ctx):
    await ctx.send(
        "اضغط لفتح تكت",
        view=TicketPanel()
    )


@bot.command()
async def vacationpanel(ctx):
    await ctx.send(
        "نظام الإجازات",
        view=VacationView()
    )


@bot.command()
async def role(ctx, member: discord.Member):

    view = discord.ui.View()

    view.add_item(
        ActionSelect(member)
    )

    await ctx.send(
        "اختر العملية",
        view=view
    )


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
    print(f"Bot Ready {bot.user}")

bot.run(TOKEN)
