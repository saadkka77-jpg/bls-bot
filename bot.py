import discord
from discord.ext import commands
from discord.ui import View, Select
import os
import datetime
import json
import io

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===============================
# نظام ترقيم التكت
# ===============================

COUNTER_FILE = "ticket_counter.json"

def get_ticket_number():

    if not os.path.exists(COUNTER_FILE):

        with open(COUNTER_FILE, "w") as f:
            json.dump({"ticket": 0}, f)

    with open(COUNTER_FILE, "r") as f:
        data = json.load(f)

    data["ticket"] += 1

    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)

    return data["ticket"]


# ===============================
# إعدادات الرومات
# ===============================

RANK_CATEGORY = 1494665237717323907
PERSON_CATEGORY = 1494665311331291258
SHOP_CATEGORY = 1487848330804330699
SUPPORT_CATEGORY = 1487721982945394728
ADMIN_CATEGORY = 1487709726765748295

LOG_CHANNEL = 1480456866613170267


# ===============================
# الرتب
# ===============================

SUPPORT_ROLES = [
1477492633847857252,
1482194383515422752,
1480443913557905499,
1478970736717598840,
1495873706923393205,
1478971845729583276,
1490386915629989948
]

ADMIN_COMPLAINT_ROLES = [
1478970736717598840,
1495873706923393205,
1478971845729583276,
1490386915629989948
]

ALL_ROLES = list(set(SUPPORT_ROLES + ADMIN_COMPLAINT_ROLES))


# ===============================
# مودال الإغلاق
# ===============================

class CloseModal(discord.ui.Modal, title="🔒 إغلاق التكت"):

    reason = discord.ui.TextInput(
        label="سبب إغلاق التكت",
        placeholder="اكتب السبب هنا...",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        await interaction.response.defer()

        channel = interaction.channel
        reason_text = self.reason.value

        log_channel = bot.get_channel(LOG_CHANNEL)

        messages = []

        async for m in channel.history(limit=None):
            messages.append(f"{m.author}: {m.content}")

        transcript = "\n".join(messages)

        file = discord.File(
            io.BytesIO(transcript.encode()),
            filename="transcript.txt"
        )

        embed = discord.Embed(
            title="📁 Ticket Closed",
            description=f"📝 السبب:\n{reason_text}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        if log_channel:

            await log_channel.send(
                embed=embed,
                file=file
            )

        try:

            opener_id = int(channel.topic)
            user = await bot.fetch_user(opener_id)

            dm = discord.Embed(
                title="🔒 تم إغلاق التكت",
                description=(
                    f"👮‍♂️ المسؤول: {interaction.user.mention}\n"
                    f"📝 السبب:\n{reason_text}"
                ),
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )

            dm.set_footer(text="BLS Ticket System")

            await user.send(embed=dm)

        except:
            pass

        await channel.delete()


# ===============================
# أزرار التكت
# ===============================

class TicketButtons(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📌 استلام التكت",
        style=discord.ButtonStyle.green,
        custom_id="claim_ticket"
    )
    async def claim_ticket(self, interaction, button):

        await interaction.response.defer()

        channel = interaction.channel
        guild = interaction.guild
        claimer = interaction.user

        if not any(role.id in ALL_ROLES for role in claimer.roles):

            return await interaction.followup.send(
                "❌ لا تملك صلاحية استلام التكت",
                ephemeral=True
            )

        opener_id = int(channel.topic)

        # خلي كل الإداريين قراءة فقط
        for role_id in ALL_ROLES:

            role = guild.get_role(role_id)

            if role:

                await channel.set_permissions(
                    role,
                    read_messages=True,
                    send_messages=False
                )

        # السماح فقط للمستلم
        await channel.set_permissions(
            claimer,
            read_messages=True,
            send_messages=True
        )

        embed = discord.Embed(
            description=f"📌 تم استلام التكت بواسطة {claimer.mention}",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed)


    @discord.ui.button(
        label="🔒 إغلاق التكت",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction, button):

        await interaction.response.send_modal(
            CloseModal()
        )


# ===============================
# إنشاء التكت
# ===============================

async def create_ticket(interaction, ticket_type):

    guild = interaction.guild
    user = interaction.user

    for ch in guild.text_channels:

        if ch.topic == str(user.id):

            return await interaction.response.send_message(
                "❌ لديك تكت مفتوح بالفعل.",
                ephemeral=True
            )

    ticket_number = get_ticket_number()

    if ticket_type == "rank":
        category_id = RANK_CATEGORY
        ticket_name = f"ticket-{ticket_number}-rank"

    elif ticket_type == "support":
        category_id = SUPPORT_CATEGORY
        ticket_name = f"ticket-{ticket_number}-support"

    elif ticket_type == "person":
        category_id = PERSON_CATEGORY
        ticket_name = f"ticket-{ticket_number}-person"

    elif ticket_type == "admin":
        category_id = ADMIN_CATEGORY
        ticket_name = f"ticket-{ticket_number}-admin"

    elif ticket_type == "shop":
        category_id = SHOP_CATEGORY
        ticket_name = f"ticket-{ticket_number}-shop"

    category = guild.get_channel(category_id)

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(read_messages=False),

        user:
            discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )
    }

    # الإداريين يشوفون التكت من البداية

    for role_id in ALL_ROLES:

        role = guild.get_role(role_id)

        if role:

            overwrites[role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )

    channel = await guild.create_text_channel(

        name=ticket_name,
        category=category,
        overwrites=overwrites,
        topic=str(user.id)

    )

    view = TicketButtons()

    embed = discord.Embed(
        title="🎫 نظام التكت - BLS",
        description=(
            "✅ **تم فتح التكت بنجاح**\n\n"
            "📌 يرجى شرح طلبك بالتفصيل\n"
            "📎 إرفاق الأدلة إن وجدت"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()
    )

    embed.set_footer(
        text=f"Ticket #{ticket_number}"
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    await channel.send(
        content=user.mention,
        embed=embed,
        view=view
    )

    await interaction.response.send_message(
        f"✅ تم فتح التكت: {channel.mention}",
        ephemeral=True
    )


# ===============================
# القائمة
# ===============================

class TicketSelect(Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="الدعم الفني",
                value="support"
            ),

            discord.SelectOption(
                label="المتجر",
                value="shop"
            ),

            discord.SelectOption(
                label="شكوى على إداري",
                value="admin"
            ),

            discord.SelectOption(
                label="تكت رانك",
                value="rank"
            ),

            discord.SelectOption(
                label="شكوى على شخص",
                value="person"
            )

        ]

        super().__init__(
            placeholder="اختر نوع التكت",
            options=options
        )

    async def callback(self, interaction):

        await create_ticket(
            interaction,
            self.values[0]
        )


class TicketPanel(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ===============================
# أمر لوحة التكت
# ===============================

@bot.command()
async def panel(ctx):

    embed = discord.Embed(
        title="🎫 نظام التكت - BLS",
        description="اختر القسم المناسب من القائمة بالأسفل",
        color=discord.Color.blue()
    )

    await ctx.send(
        embed=embed,
        view=TicketPanel()
    )


# ===============================
# تشغيل البوت
# ===============================

@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")

    bot.add_view(TicketPanel())
    bot.add_view(TicketButtons())


bot.run(TOKEN)
