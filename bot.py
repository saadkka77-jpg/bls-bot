from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
import datetime
import json
import os
import io

# --- 1. نظام الويب ---
app = Flask('')
@app.route('/')
def home(): return "BLS Ticket System is Online!"

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

keep_alive()

# --- 2. الإعدادات ---
TOKEN = os.getenv('TOKEN') 

LOG_TICKET_ID = 1480456866613170267
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
LEAVE_CHANNEL_ID = 1490070238270718013

TICKET_CATEGORIES = {
    "support": 1487721982945394728,
    "report": 1487709726765748295
}

# رتب المتجر وشكوى إداري
STORE_ROLES = [
    1478970736717598840,
    1490386915629989948,
    1478971845729583276
]

# رتب الدعم الفني وشكوى شخص
SUPPORT_ROLES = [
    1477492633847857252,
    1482194383515422752,
    1480443913557905499
]

def load_data():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except:
        return {"ticket_count": 0}

data = load_data()

def save_data():
    with open('data.json', 'w') as f:
        json.dump(data, f, indent=4)

# --- إغلاق التذكرة ---
class TicketCloseModal(discord.ui.Modal, title="إغلاق التذكرة"):
    reason = discord.ui.TextInput(
        label="سبب الإغلاق",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):

        await interaction.response.defer()

        log_content = f"Log for {interaction.channel.name}\n"

        async for msg in interaction.channel.history(
            limit=500,
            oldest_first=True
        ):
            log_content += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author}: {msg.content}\n"

        log_ch = interaction.client.get_channel(LOG_TICKET_ID)

        if log_ch:

            file = discord.File(
                fp=io.BytesIO(log_content.encode()),
                filename=f"{interaction.channel.name}.txt"
            )

            await log_ch.send(
                f"تم إغلاق تذكرة بواسطة {interaction.user.mention}\nالسبب: {self.reason.value}",
                file=file
            )

        await interaction.channel.delete()

# --- أزرار التذكرة ---
class TicketActionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="استلام",
        style=discord.ButtonStyle.success,
        custom_id="claim_t"
    )
    async def claim(self, interaction, button):

        button.disabled = True
        button.label = f"استلمها: {interaction.user.display_name}"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(
        label="إغلاق",
        style=discord.ButtonStyle.danger,
        custom_id="close_t"
    )
    async def close(self, interaction, button):

        await interaction.response.send_modal(
            TicketCloseModal()
        )

# --- قائمة التذاكر ---
class TicketDropdown(discord.ui.Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="دعم فني",
                value="support",
                emoji="🛠️"
            ),

            discord.SelectOption(
                label="شكوى",
                value="report",
                emoji="⚠️"
            )
        ]

        super().__init__(
            placeholder="اختر نوع التذكرة...",
            options=options,
            custom_id="ticket_select"
        )

    async def callback(self, interaction):

        data["ticket_count"] += 1
        save_data()

        category = interaction.guild.get_channel(
            TICKET_CATEGORIES.get(self.values[0])
        )

        overwrites = {

            interaction.guild.default_role:
                discord.PermissionOverwrite(
                    read_messages=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True
                )
        }

        # دعم فني / شكوى شخص
        if self.values[0] == "support":

            for role_id in SUPPORT_ROLES:

                role = interaction.guild.get_role(role_id)

                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )

        # متجر / شكوى إداري
        if self.values[0] == "report":

            for role_id in STORE_ROLES:

                role = interaction.guild.get_role(role_id)

                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True,
                        send_messages=True
                    )

        ticket_ch = await interaction.guild.create_text_channel(

            name=f"ticket-{data['ticket_count']}",

            category=category,

            overwrites=overwrites

        )

        embed = discord.Embed(
            title="تذكرة جديدة",
            description="انتظر رد الإدارة.",
            color=0x2f3136
        )

        await ticket_ch.send(

            content=f"{interaction.user.mention}",

            embed=embed,

            view=TicketActionView()

        )

        await interaction.response.send_message(

            f"✅ تم فتح التذكرة: {ticket_ch.mention}",

            ephemeral=True
        )

# --- نظام الإجازات ---
class VacationPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="أخذ إجازة",
        style=discord.ButtonStyle.success,
        emoji="📝",
        custom_id="v_take"
    )
    async def take(self, interaction, b):

        role = interaction.guild.get_role(
            VACATION_ROLE_ID
        )

        await interaction.user.add_roles(role)

        await interaction.response.send_message(
            "✅ تم تفعيل الإجازة.",
            ephemeral=True
        )

# --- تشغيل البوت ---
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

@bot.event
async def on_ready():

    bot.add_view(TicketActionView())

    bot.add_view(VacationPanel())

    bot.add_view(
        discord.ui.View().add_item(
            TicketDropdown()
        )
    )

    print(f"✅ {bot.user.name} جاهز!")

@bot.command()
@commands.has_permissions(administrator=True)

async def setup_ticket(ctx):

    view = discord.ui.View(
        timeout=None
    ).add_item(TicketDropdown())

    await ctx.send(

        embed=discord.Embed(
            title="مركز تذاكر BLS",
            color=0x00ff00
        ),

        view=view
    )

@bot.command()
@commands.has_permissions(administrator=True)

async def setup_vacation(ctx):

    await ctx.send(

        embed=discord.Embed(
            title="نظام الإجازات",
            color=0x0000ff
        ),

        view=VacationPanel()
    )

if TOKEN:

    bot.run(TOKEN)
