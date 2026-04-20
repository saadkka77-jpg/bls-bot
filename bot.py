import discord
from discord.ext import commands
import asyncio
import datetime
import io
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
LOG_CHANNEL_ID = 1480456866613170267

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

ADMIN_COMPLAINT_ROLES = [
1490386915629989948,
1478971845729583276,
1478970736717598840
]

STORE_ROLES = ADMIN_COMPLAINT_ROLES

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
        label="سبب اغلاق التكت",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        channel = interaction.channel
        closer = interaction.user

        now = datetime.datetime.now().strftime(
            "%Y-%m-%d | %H:%M"
        )

        user = None

        for m in await channel.history(
            limit=1,
            oldest_first=True
        ).flatten():

            user = m.mentions[0]

        await interaction.response.send_message(
            "يتم اغلاق التكت...",
            ephemeral=True
        )

        if user:

            try:

                await user.send(
                    f"""
تم اغلاق التكت الخاص بك

بواسطة: {closer.mention}

الوقت:
{now}

السبب:
{self.reason}
"""
                )

            except:
                pass

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

        if not has_role(
            interaction.user,
            SUPPORT_ROLES
        ):
            return await interaction.response.send_message(
                "لا تملك صلاحية",
                ephemeral=True
            )

        channel = interaction.channel

        for member in channel.members:

            if member != interaction.user:

                await channel.set_permissions(
                    member,
                    send_messages=False
                )

        await channel.set_permissions(
            interaction.user,
            send_messages=True
        )

        await interaction.response.send_message(
            f"تم استلام التكت بواسطة {interaction.user.mention}"
        )

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
# CATEGORY SELECT
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

        guild = interaction.guild
        user = interaction.user

        value = self.values[0]

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

        # =================

        if value == "support":

            message = (
                "حياك الله في الدعم الفني الخاص بي BLS\n"
                "اكتب شرح مشكلتك"
            )

            roles = SUPPORT_ROLES

        elif value == "store":

            message = (
                "حياك الله في المتجر\n"
                "اكتب اسم المنتج\n"
                "في حال عدم الرد خلال 24 ساعة يتم الغاء الطلب"
            )

            roles = STORE_ROLES

        elif value == "admin":

            message = (
                "حياك اكتب ملخص الشكوة و ارفق الدليل\n"
                "اسباب الرفض:\n"
                "مرور 24 ساعة على الشكوة\n"
                "عدم وجود دليل"
            )

            roles = ADMIN_COMPLAINT_ROLES

        elif value == "rank":

            message = (
                "حياك الله في خدمة الرانك\n"
                "اطلب رانك و رح يتواصل معك الاداري\n"
                "ارسل الدليل مع صورة حسابك و اسم اللعبة"
            )

        elif value == "person":

            message = (
                "اكتب ملخص الشكوة\n"
                "اسباب رفض الشكوة:\n"
                "مرور 24 ساعة على الحادثة\n"
                "عدم وجود دليل"
            )

        # =================

        for role_id in roles:

            role = guild.get_role(
                role_id
            )

            if role:

                overwrites[role] = (
                    discord.PermissionOverwrite(
                        view_channel=True
                    )
                )

        channel = await guild.create_text_channel(

            name=f"ticket-{user.name}",

            overwrites=overwrites

        )

        await channel.send(

            f"{user.mention}\n\n{message}",

            view=TicketButtons()

        )

        await interaction.response.send_message(
            f"تم فتح التكت: {channel.mention}",
            ephemeral=True
        )

# =========================
# PANEL VIEW
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

    await ctx.send(

        "حياك الله في خدمة التكت الخاصة بي BLS",

        view=TicketPanel()

    )

# =========================
# READY
# =========================

@bot.event
async def on_ready():

    print(
        f"Bot Ready {bot.user}"
    )

bot.run(TOKEN)
