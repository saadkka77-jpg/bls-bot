import discord
from discord.ext import commands
from discord.ui import View, Select
import os
import datetime
import json
import io

from flask import Flask
from threading import Thread

# ===============================
# Flask (لـ Web Service)
# ===============================

app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ===============================

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
intents.message_content = True

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

SUPPORT_ROLES = [
1477492633847857252,
1482194383515422752,
1480443913557905499,
1478970736717598840
]

SPECIAL_ROLES = [
1490386915629989948,
1495873706923393205,
1478971845729583276
]

# ===============================
# إنشاء التكت
# ===============================

async def create_ticket(interaction, ticket_type):

    guild = interaction.guild
    user = interaction.user

    ticket_number = get_ticket_number()

    categories = {

        "support": SUPPORT_CATEGORY,
        "shop": SHOP_CATEGORY,
        "admin": ADMIN_CATEGORY,
        "rank": RANK_CATEGORY,
        "person": PERSON_CATEGORY

    }

    category = guild.get_channel(categories[ticket_type])

    # تحديد الرولات حسب النوع

    if ticket_type in ["shop", "admin"]:
        roles_to_add = SPECIAL_ROLES
    else:
        roles_to_add = SUPPORT_ROLES

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

    for role_id in roles_to_add:

        role = guild.get_role(role_id)

        if role:

            overwrites[role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )

    channel = await guild.create_text_channel(

        name=f"ticket-{ticket_number}",
        category=category,
        overwrites=overwrites,
        topic=f"{user.id}|0"

    )

    embed = discord.Embed(

        title="🎫 تم فتح التكت",

        description=(
            "📜 **قوانين التكت:**\n"
            "• اشرح مشكلتك بوضوح\n"
            "• لا تزعج الإدارة\n"
            "• احترام الجميع واجب\n\n"
            "⏳ سيتم الرد عليك قريباً"
        ),

        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.UTC)

    )

    if guild.icon:

        embed.set_thumbnail(
            url=guild.icon.url
        )

    await channel.send(
        content=user.mention,
        embed=embed
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
                emoji="🛠️",
                value="support"
            ),

            discord.SelectOption(
                label="المتجر",
                emoji="🛒",
                value="shop"
            ),

            discord.SelectOption(
                label="شكوى على إداري",
                emoji="⚖️",
                value="admin"
            ),

            discord.SelectOption(
                label="طلب رانك",
                emoji="⭐",
                value="rank"
            ),

            discord.SelectOption(
                label="شكوى على شخص",
                emoji="🚫",
                value="person"
            )

        ]

        super().__init__(
            placeholder="اختر نوع التكت",
            options=options,
            custom_id="ticket_select_menu"
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
# لوحة التكت
# ===============================

@bot.command()
async def panel(ctx):

    embed = discord.Embed(

        title="🎫 نظام التكت",

        description=(
            "📜 **قوانين فتح التكت:**\n"
            "• اختر القسم المناسب\n"
            "• لا تفتح أكثر من تكت\n"
            "• احترام الإدارة\n\n"
            "⬇️ اختر نوع التكت"
        ),

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
# تشغيل
# ===============================

@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")

    bot.add_view(TicketPanel())

keep_alive()

bot.run(TOKEN)


