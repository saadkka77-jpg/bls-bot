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
LOG_CHANNEL_ID = 1480456866613170267

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

# =========================
# LOG FUNCTION
# =========================

async def send_log(message):

    log_channel = bot.get_channel(
        LOG_CHANNEL_ID
    )

    if log_channel:
        await log_channel.send(message)

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

        now = datetime.datetime.now().strftime(
            "%Y-%m-%d | %H:%M"
        )

        await send_log(
            f"🔴 تم اغلاق التكت {channel.name}\n"
            f"بواسطة {interaction.user.mention}\n"
            f"الوقت: {now}\n"
            f"السبب: {self.reason}"
        )

        await asyncio.sleep(3)

        await channel.delete()

# =========================
# BUTTONS
# =========================

class TicketButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # =====================
    # CLAIM
    # =====================

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

        channel = interaction.channel

        claimed_tickets[
            channel.id
        ] = interaction.user.id

        # منع باقي الدعم من الكتابة

        for role_id in SUPPORT_ROLES:

            role = interaction.guild.get_role(
                role_id
            )

            if role:

                await channel.set_permissions(
                    role,
                    send_messages=False
                )

        # السماح للمستلم فقط

        await channel.set_permissions(
            interaction.user,
            send_messages=True
        )

        await send_log(
            f"🟢 تم استلام {channel.name}\n"
            f"بواسطة {interaction.user.mention}"
        )

        await interaction.response.send_message(
            "تم استلام التكت",
            ephemeral=True
        )

    # =====================
    # CLOSE REQUEST
    # =====================

    @discord.ui.button(
        label="طلب اغلاق",
        style=discord.ButtonStyle.red
    )
    async def close_request(
        self,
        interaction,
        button
    ):

        channel = interaction.channel

        await send_log(
            f"🟡 طلب اغلاق {channel.name}\n"
            f"بواسطة {interaction.user.mention}"
        )

        await interaction.response.send_message(
            "تم ارسال طلب الاغلاق للإدارة",
            ephemeral=True
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

        # منع الدعم من الكتابة قبل الاستلام

        for role_id in SUPPORT_ROLES:

            role = guild.get_role(role_id)

            if role:

                overwrites[role] = (
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=False
                    )
                )

        channel = await guild.create_text_channel(
            name=ticket_name,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title=f"تذكرة رقم #{ticket_counter}",
            description="اكتب مشكلتك وسيتم الرد عليك",
            color=discord.Color.blue()
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=TicketButtons()
        )

        await send_log(
            f"📩 تم فتح {channel.name}\n"
            f"بواسطة {user.mention}"
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
        description="حياك الله في خدمة التكت الخاصة بي BLS\nاختر القسم",
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
