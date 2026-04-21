import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import os
import datetime

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===============================
# إعدادات الرومات
# ===============================

RANK_CATEGORY = 1494665237717323907
PERSON_CATEGORY = 1494665311331291258
SHOP_CATEGORY = 1487848330804330699
SUPPORT_CATEGORY = 1487721982945394728
ADMIN_CATEGORY = 1487709726765748295

LOG_CHANNEL = 000000000000000000  # حط روم اللوق هنا

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

SHOP_ROLES = ADMIN_COMPLAINT_ROLES
RANK_ROLES = SUPPORT_ROLES
PERSON_ROLES = SUPPORT_ROLES


# ===============================
# رسائل التكت
# ===============================

MESSAGES = {

"rank":
"""🎖️ **حياك الله في خدمة الرانك**

اطلب الرانك ورح يتواصل معك الإداري

📌 **أرسل التالي:**
• صورة الحساب  
• اسم اللعبة  
""",

"support":
"""🛠️ **حياك الله في الدعم الفني الخاص بـ BLS**

اكتب شرح مشكلتك بالتفصيل وسيتم الرد عليك قريبًا.
""",

"person":
"""⚠️ **شكوى على شخص**

📌 **اكتب ملخص الشكوى**

❌ **أسباب رفض الشكوى:**
• مرور 24 ساعة على الحادثة  
• عدم وجود دليل أو إثبات  
""",

"admin":
"""🚨 **شكوى على إداري**

📌 اكتب ملخص الشكوى و أرفق الدليل

❌ **أسباب الرفض:**
🔴 مرور 24 ساعة على الشكوى  
🔴 عدم وجود دليل  
""",

"shop":
"""🛒 **تكت متجر**

📌 اكتب اسم المنتج المطلوب

⚠️ في حال عدم الرد خلال 24 ساعة  
سيتم إلغاء الطلب.
"""
}


# ===============================
# إنشاء التكت
# ===============================

async def create_ticket(interaction, ticket_type):

    guild = interaction.guild
    user = interaction.user

    if ticket_type == "rank":
        category_id = RANK_CATEGORY
        roles = RANK_ROLES

    elif ticket_type == "support":
        category_id = SUPPORT_CATEGORY
        roles = SUPPORT_ROLES

    elif ticket_type == "person":
        category_id = PERSON_CATEGORY
        roles = PERSON_ROLES

    elif ticket_type == "admin":
        category_id = ADMIN_CATEGORY
        roles = ADMIN_COMPLAINT_ROLES

    elif ticket_type == "shop":
        category_id = SHOP_CATEGORY
        roles = SHOP_ROLES

    category = guild.get_channel(category_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    for role_id in roles:
        role = guild.get_role(role_id)
        overwrites[role] = discord.PermissionOverwrite(
            read_messages=True,
            send_messages=False
        )

    channel = await guild.create_text_channel(
        name=f"ticket-{user.name}",
        category=category,
        overwrites=overwrites
    )

    view = TicketButtons()

    await channel.send(
        f"{user.mention}",
        embed=discord.Embed(
            description=MESSAGES[ticket_type],
            color=discord.Color.blue()
        ),
        view=view
    )

    await interaction.response.send_message(
        f"✅ تم فتح التكت: {channel.mention}",
        ephemeral=True
    )


# ===============================
# أزرار التكت
# ===============================

class TicketButtons(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📌 استلام التكت",
        style=discord.ButtonStyle.green
    )
    async def claim_ticket(self, interaction, button):

        role_ids = [r.id for r in interaction.user.roles]

        channel = interaction.channel

        for member in channel.members:

            if member == interaction.user:
                await channel.set_permissions(
                    member,
                    send_messages=True
                )

            elif member != interaction.guild.owner:
                await channel.set_permissions(
                    member,
                    send_messages=False
                )

        await interaction.response.send_message(
            f"✅ تم استلام التكت بواسطة {interaction.user.mention}"
        )


    @discord.ui.button(
        label="🔒 إغلاق التكت",
        style=discord.ButtonStyle.red
    )
    async def close_ticket(self, interaction, button):

        await interaction.response.send_message(
            "✏️ اكتب سبب إغلاق التكت..."
        )

        def check(m):
            return m.author == interaction.user

        msg = await bot.wait_for("message", check=check)

        reason = msg.content

        channel = interaction.channel

        log_channel = bot.get_channel(LOG_CHANNEL)

        messages = []

        async for m in channel.history(limit=None):
            messages.append(f"{m.author}: {m.content}")

        transcript = "\n".join(messages)

        embed = discord.Embed(
            title="📁 Ticket Log",
            description=f"**Reason:** {reason}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        await log_channel.send(
            embed=embed,
            file=discord.File(
                fp=bytes(transcript, "utf-8"),
                filename="transcript.txt"
            )
        )

        opener = channel.topic

        try:
            user = await bot.fetch_user(int(opener))

            await user.send(
                f"🔒 تم إغلاق التكت بواسطة {interaction.user.mention}\n"
                f"📌 السبب: {reason}"
            )
        except:
            pass

        await channel.delete()


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
                label="تكت رانك",
                value="rank"
            ),

            discord.SelectOption(
                label="شكوى على شخص",
                value="person"
            )

        ]

        super().__init__(
            placeholder="حياك الله في خدمة التكت الخاصة بـ BLS",
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
# أمر إرسال لوحة التكت
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

bot.run(TOKEN)
