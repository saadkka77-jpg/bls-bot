import discord
from discord.ext import commands
from discord.ui import View, Select
import os
import datetime
import json
import io

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ===============================
# نظام الترقيم
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
# الإعدادات
# ===============================

RANK_CATEGORY = 1494665237717323907
PERSON_CATEGORY = 1494665311331291258
SHOP_CATEGORY = 1487848330804330699
SUPPORT_CATEGORY = 1487721982945394728
ADMIN_CATEGORY = 1487709726765748295

LOG_CHANNEL = 1480456866613170267

# رتب الدعم العامة

SUPPORT_ROLES = [
1477492633847857252,
1482194383515422752,
1480443913557905499,
1478970736717598840
]

# رتب خاصة فقط للمتجر و شكوى إداري

SPECIAL_ROLES = [
1490386915629989948,
1495873706923393205,
1478971845729583276
]

ALL_ROLES = list(set(SUPPORT_ROLES + SPECIAL_ROLES))

# ===============================
# إغلاق التكت
# ===============================

class CloseModal(discord.ui.Modal, title="🔒 إغلاق التكت"):

    reason = discord.ui.TextInput(
        label="سبب إغلاق التكت",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        await interaction.response.defer()

        channel = interaction.channel

        log = bot.get_channel(LOG_CHANNEL)

        messages = []

        async for m in channel.history(limit=200):
            messages.append(f"{m.author}: {m.content}")

        transcript = "\n".join(messages)

        file = discord.File(
            io.BytesIO(transcript.encode()),
            filename="transcript.txt"
        )

        embed = discord.Embed(
            title="📁 تم إغلاق التكت",
            description=f"📌 السبب:\n{self.reason.value}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        if log:
            await log.send(embed=embed, file=file)

        try:
            opener_id = int(channel.topic)
            user = await bot.fetch_user(opener_id)
            await user.send(embed=embed)
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
        user = interaction.user

        if not any(r.id in ALL_ROLES for r in user.roles):

            return await interaction.followup.send(
                "❌ لا تملك صلاحية",
                ephemeral=True
            )

        opener_id = int(channel.topic)

        opener = guild.get_member(opener_id)

        # منع الكتابة عن الإداريين
        for r_id in ALL_ROLES:

            role = guild.get_role(r_id)

            if role:

                await channel.set_permissions(
                    role,
                    send_messages=False
                )

        # السماح للمستلم
        await channel.set_permissions(
            user,
            send_messages=True
        )

        # السماح لصاحب التكت
        if opener:

            await channel.set_permissions(
                opener,
                send_messages=True
            )

        embed = discord.Embed(
            description=f"📌 تم استلام التكت بواسطة {user.mention}",
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
                "❌ لديك تكت مفتوح بالفعل",
                ephemeral=True
            )

    ticket_number = get_ticket_number()

    categories = {

        "support": SUPPORT_CATEGORY,
        "shop": SHOP_CATEGORY,
        "admin": ADMIN_CATEGORY,
        "rank": RANK_CATEGORY,
        "person": PERSON_CATEGORY

    }

    category = guild.get_channel(
        categories[ticket_type]
    )

    ticket_name = f"ticket-{ticket_number}"

    overwrites = {

        guild.default_role:
            discord.PermissionOverwrite(
                read_messages=False
            ),

        user:
            discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )
    }

    # رتب حسب نوع التكت

    if ticket_type in ["shop", "admin"]:

        roles_to_add = SPECIAL_ROLES

    else:

        roles_to_add = SUPPORT_ROLES

    for r in roles_to_add:

        role = guild.get_role(r)

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

    embed = discord.Embed(

        title="🎫 نظام التكت",
        description=(
            "✅ **تم فتح التكت بنجاح**\n\n"
            "📌 يرجى شرح طلبك بالتفصيل"
        ),

        color=discord.Color.blue(),
        timestamp=datetime.datetime.utcnow()

    )

    embed.add_field(
        name="🎟️ رقم التكت",
        value=str(ticket_number),
        inline=True
    )

    embed.add_field(
        name="📂 الحالة",
        value="🟢 مفتوح",
        inline=True
    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    await channel.send(

        content=user.mention,
        embed=embed,
        view=TicketButtons()

    )

    await interaction.response.send_message(

        f"✅ تم فتح التكت: {channel.mention}",
        ephemeral=True

    )

# ===============================
# قائمة التكت
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
                label="طلب رانك",
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

        self.add_item(
            TicketSelect()
        )

# ===============================
# أمر فتح اللوحة
# ===============================

@bot.command()
async def panel(ctx):

    embed = discord.Embed(

        title="🎫 نظام التكت",
        description="اختر القسم المناسب من القائمة",

        color=discord.Color.blue()

    )

    if ctx.guild.icon:

        embed.set_thumbnail(
            url=ctx.guild.icon.url
        )

    await ctx.send(

        embed=embed,
        view=TicketPanel()

    )

# ===============================
# أمر إضافة عضو للتكت
# ===============================

@bot.command()
async def add(ctx, member: discord.Member):

    if ctx.channel.topic is None:
        return

    await ctx.channel.set_permissions(
        member,
        read_messages=True,
        send_messages=True
    )

    await ctx.send(
        f"✅ تم إضافة {member.mention} إلى التكت"
    )

# ===============================
# تشغيل
# ===============================

@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")

    bot.add_view(TicketPanel())
    bot.add_view(TicketButtons())

bot.run(TOKEN)
