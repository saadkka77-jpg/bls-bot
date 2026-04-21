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
1478970736717598840,
1495873706923393205,
1478971845729583276,
1490386915629989948
]

ADMIN_COMPLAINT_ROLES = SUPPORT_ROLES

ALL_ROLES = list(set(SUPPORT_ROLES + ADMIN_COMPLAINT_ROLES))

# ===============================
# الإغلاق
# ===============================

class CloseModal(discord.ui.Modal, title="🔒 إغلاق التكت"):

    reason = discord.ui.TextInput(
        label="سبب الإغلاق",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction):

        await interaction.response.defer()

        channel = interaction.channel
        reason_text = self.reason.value

        log = bot.get_channel(LOG_CHANNEL)

        messages = []

        async for m in channel.history(limit=200):
            messages.append(f"{m.author}: {m.content}")

        transcript = "\n".join(messages)

        file = discord.File(io.BytesIO(transcript.encode()), filename="transcript.txt")

        embed = discord.Embed(
            title="📁 Ticket Closed",
            description=f"**Reason:** {reason_text}",
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
# الأزرار
# ===============================

class TicketButtons(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📌 Claim Ticket",
        style=discord.ButtonStyle.green,
        custom_id="claim_ticket"
    )
    async def claim_ticket(self, interaction, button):

        await interaction.response.defer()

        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        if not any(r.id in ALL_ROLES for r in user.roles):
            return await interaction.followup.send("❌ No permission", ephemeral=True)

        if not channel.topic:
            return await interaction.followup.send("❌ Invalid ticket", ephemeral=True)

        opener_id, claimed = channel.topic.split("|")

        if "claimed:" in claimed:
            claimed_id = int(claimed.split(":")[1])

            if claimed_id != 0:
                return await interaction.followup.send(
                    "❌ Ticket already claimed",
                    ephemeral=True
                )

        new_topic = f"{opener_id}|claimed:{user.id}"
        await channel.edit(topic=new_topic)

        # قفل الإداريين
        for r_id in ALL_ROLES:
            role = guild.get_role(r_id)
            if role:
                await channel.set_permissions(role, send_messages=False)

        await channel.set_permissions(user, send_messages=True)

        embed = discord.Embed(
            title="📌 Ticket Claimed",
            description=f"Claimed by {user.mention}",
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed)

    @discord.ui.button(
        label="🔒 Close",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction, button):

        await interaction.response.send_modal(CloseModal())

# ===============================
# إنشاء التكت
# ===============================

async def create_ticket(interaction, ticket_type):

    guild = interaction.guild
    user = interaction.user

    for ch in guild.text_channels:
        if ch.topic and ch.topic.startswith(str(user.id)):
            return await interaction.response.send_message("❌ لديك تكت مفتوح", ephemeral=True)

    ticket_number = get_ticket_number()

    categories = {
        "support": SUPPORT_CATEGORY,
        "shop": SHOP_CATEGORY,
        "admin": ADMIN_CATEGORY,
        "rank": RANK_CATEGORY,
        "person": PERSON_CATEGORY
    }

    category = guild.get_channel(categories[ticket_type])
    name = f"ticket-{ticket_number}-{ticket_type}"

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    for r in ALL_ROLES:
        role = guild.get_role(r)
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True)

    channel = await guild.create_text_channel(
        name=name,
        category=category,
        overwrites=overwrites,
        topic=f"{user.id}|claimed:0"
    )

    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Please describe your issue",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )

    embed.add_field(name="Ticket ID", value=str(ticket_number), inline=True)
    embed.add_field(name="Status", value="🟢 Open", inline=True)

    await channel.send(content=user.mention, embed=embed, view=TicketButtons())

    await interaction.response.send_message(f"✅ Created: {channel.mention}", ephemeral=True)

# ===============================
# القائمة
# ===============================

class TicketSelect(Select):

    def __init__(self):

        options = [
            discord.SelectOption(label="Support", value="support"),
            discord.SelectOption(label="Shop", value="shop"),
            discord.SelectOption(label="Admin", value="admin"),
            discord.SelectOption(label="Rank", value="rank"),
            discord.SelectOption(label="Person", value="person"),
        ]

        super().__init__(
            placeholder="Choose ticket type",
            options=options,
            custom_id="ticket_menu"
        )

    async def callback(self, interaction):
        await create_ticket(interaction, self.values[0])

class TicketPanel(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

# ===============================
# أمر البانل
# ===============================

@bot.command()
async def panel(ctx):

    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Select a category below",
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed, view=TicketPanel())

# ===============================
# تشغيل
# ===============================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.add_view(TicketPanel())
    bot.add_view(TicketButtons())

bot.run(TOKEN)
