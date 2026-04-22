import discord
from discord.ext import commands
from discord.ui import View, Select
import os
import datetime
import json
import io

# 🔵 Flask لإجبار فتح port
from flask import Flask
from threading import Thread

# ===============================
# Flask Web Server (مهم لـ Web Service)
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
# إعداد البوت
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
            timestamp=datetime.datetime.now(datetime.UTC)
        )

        if log:
            await log.send(embed=embed, file=file)

        try:

            opener_id = int(channel.topic.split("|")[0])
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
        claimer = interaction.user

        if not any(r.id in ALL_ROLES for r in claimer.roles):

            return await interaction.followup.send(
                "❌ لا تملك صلاحية",
                ephemeral=True
            )

        opener_id, claimed_id = channel.topic.split("|")

        if claimed_id != "0":

            return await interaction.followup.send(
                "❌ التكت مستلمة بالفعل",
                ephemeral=True
            )

        opener = guild.get_member(int(opener_id))

        new_topic = f"{opener_id}|{claimer.id}"

        await channel.edit(topic=new_topic)

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
# القائمة
# ===============================

class TicketSelect(Select):

    def __init__(self):

        options = [

            discord.SelectOption(label="الدعم الفني", value="support"),
            discord.SelectOption(label="المتجر", value="shop"),
            discord.SelectOption(label="شكوى على إداري", value="admin"),
            discord.SelectOption(label="طلب رانك", value="rank"),
            discord.SelectOption(label="شكوى على شخص", value="person")

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
# إنشاء التكت
# ===============================

async def create_ticket(interaction, ticket_type):

    guild = interaction.guild
    user = interaction.user

    ticket_number = get_ticket_number()

    category = guild.get_channel(SUPPORT_CATEGORY)

    channel = await guild.create_text_channel(
        name=f"ticket-{ticket_number}",
        category=category,
        topic=f"{user.id}|0"
    )

    await channel.send(
        content=user.mention,
        embed=discord.Embed(
            title="🎫 نظام التكت",
            description="تم فتح التكت",
            timestamp=datetime.datetime.now(datetime.UTC)
        ),
        view=TicketButtons()
    )

    await interaction.response.send_message(
        f"✅ تم فتح التكت: {channel.mention}",
        ephemeral=True
    )

# ===============================
# الأوامر
# ===============================

@bot.command()
async def panel(ctx):

    embed = discord.Embed(
        title="🎫 نظام التكت",
        description="اختر القسم المناسب",
        color=discord.Color.blue()
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
    bot.add_view(TicketButtons())

# 🔴 مهم جداً
keep_alive()

bot.run(TOKEN)
