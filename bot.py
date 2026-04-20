import discord
from discord.ext import commands
import asyncio
import datetime
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================
# SETTINGS
# =========================

PANEL_CHANNEL_ID = 1481127399042322582

ticket_counter = 0
claimed_tickets = {}

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

ADMIN_ROLES = [
1490386915629989948,
1478971845729583276,
1478970736717598840
]

# =========================
# CLOSE MODAL
# =========================

class CloseModal(discord.ui.Modal, title="اغلاق التكت"):

    reason = discord.ui.TextInput(
        label="سبب اغلاق التكت",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        channel = interaction.channel
        closer = interaction.user

        now = datetime.datetime.now().strftime(
            "%Y-%m-%d | %H:%M"
        )

        embed = discord.Embed(
            title="تم اغلاق التكت",
            description=f"""
بواسطة: {closer.mention}

الوقت:
{now}

السبب:
{self.reason}
""",
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed
        )

        await asyncio.sleep(3)

        await channel.delete()

# =========================
# TICKET BUTTONS
# =========================

class TicketButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="استلام التكت",
        style=discord.ButtonStyle.green
    )
    async def claim(
        self,
        interaction,
        button
    ):

        if interaction.channel.id in claimed_tickets:
            return await interaction.response.send_message(
                "تم استلام التكت مسبقاً",
                ephemeral=True
            )

        if not any(
            r.id in SUPPORT_ROLES
            for r in interaction.user.roles
        ):
            return await interaction.response.send_message(
                "لا تملك صلاحية",
                ephemeral=True
            )

        claimed_tickets[
            interaction.channel.id
        ] = interaction.user.id

        await interaction.channel.send(
            f"تم استلام التكت بواسطة {interaction.user.mention}"
        )

        await interaction.response.defer()

    @discord.ui.button(
        label="اغلاق التكت",
        style=discord.ButtonStyle.red
    )
    async def close(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            CloseModal()
        )

# =========================
# SELECT MENU
# =========================

class TicketSelect(discord.ui.Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="الدعم الفني",
                value="support"
            ),

            discord.SelectOption(
                label="المتجر",
                value="store"
            ),

            discord.SelectOption(
                label="شكوة على اداري",
                value="admin"
            ),

            discord.SelectOption(
                label="تكت رانك",
                value="rank"
            ),

            discord.SelectOption(
                label="شكوة على شخص",
                value="person"
            )

        ]

        super().__init__(
            placeholder="اختر القسم",
            options=options
        )

    async def callback(self, interaction):

        global ticket_counter

        guild = interaction.guild
        user = interaction.user

        ticket_counter += 1

        ticket_name = f"ticket-{ticket_counter}"

        overwrites = {

            guild.default_role:
            discord.PermissionOverwrite(
                view_channel=False
            ),

            user:
            discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

        }

        message = ""

        roles = SUPPORT_ROLES

        if self.values[0] == "support":

            message = (
                "حياك الله في الدعم الفني الخاص بي BLS\n"
                "اكتب شرح مشكلتك"
            )

        elif self.values[0] == "store":

            message = (
                "حياك الله في المتجر\n"
                "اكتب اسم المنتج\n"
                "في حال عدم الرد خلال 24 ساعة يتم الغاء الطلب"
            )

            roles = ADMIN_ROLES

        elif self.values[0] == "admin":

            message = (
                "حياك اكتب ملخص الشكوة و ارفق الدليل\n"
                "اسباب الرفض:\n"
                "مرور 24 ساعة\n"
                "عدم وجود دليل"
            )

            roles = ADMIN_ROLES

        elif self.values[0] == "rank":

            message = (
                "حياك الله في خدمة الرانك\n"
                "اطلب رانك و ارسل الدليل"
            )

        elif self.values[0] == "person":

            message = (
                "اكتب ملخص الشكوة\n"
                "اسباب رفض الشكوة:\n"
                "مرور 24 ساعة\n"
                "عدم وجود دليل"
            )

        for role_id in roles:

            role = guild.get_role(role_id)

            if role:

                overwrites[role] = (
                    discord.PermissionOverwrite(
                        view_channel=True
                    )
                )

        channel = await guild.create_text_channel(
            name=ticket_name,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title=f"تذكرة رقم #{ticket_counter}",
            description=message,
            color=discord.Color.blue()
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=TicketButtons()
        )

        await interaction.response.send_message(
            f"تم فتح التكت {channel.mention}",
            ephemeral=True
        )

# =========================
# PANEL
# =========================

class TicketPanel(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(
            TicketSelect()
        )

# =========================
# COMMAND
# =========================

@bot.command()
async def ticketpanel(ctx):

    if ctx.channel.id != PANEL_CHANNEL_ID:
        return

    await ctx.message.delete()

    embed = discord.Embed(
        title="نظام التكت BLS",
        description="حياك الله في خدمة التكت الخاصة بي BLS\nاختر القسم من القائمة",
        color=discord.Color.green()
    )

    await ctx.send(
        embed=embed,
        view=TicketPanel()
    )

# =========================

@bot.event
async def on_ready():

    print(
        f"Bot Ready {bot.user}"
    )

bot.run(TOKEN)
