from flask import Flask
from threading import Thread
import discord
from discord.ext import commands, tasks
import datetime
import json
import asyncio
import random
import os

# --- نظام الويب للبقاء حياً (Keep Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# --- الإعدادات (سحب البيانات من Render) ---
# ملاحظة: تأكد أن اسم المتغير في Render هو TOKEN
TOKEN = os.getenv('TOKEN') 
LOG_ROOM_ID = 1490820000477610036
WARNING_ROOM_ID = 1480389401535189065
VACATION_ROLE_ID = 1492607429249339502
WARNING_ROLE_ID = 1493332501811171470
GIVEAWAY_CHANNEL_ID = 1485968828059091016
LEAVE_CHANNEL_ID = 1490070238270718013

# --- نظام القيف اوي الأوتوماتيكي ---
class GiveawayModal(discord.ui.Modal, title="إعداد القيف اوي"):
    prize = discord.ui.TextInput(label="ما هي الجائزة؟", placeholder="مثال: رتبة VIP", required=True)
    duration = discord.ui.TextInput(label="مدة السحب (بالدقائق)", placeholder="مثال: 60 لساعة / 1440 ليوم", min_length=1, max_length=6, required=True)
    description = discord.ui.TextInput(label="الوصف أو الشروط", style=discord.TextStyle.paragraph, placeholder="اكتب هنا الشروط...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration.value)
            end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            timestamp = int(end_time.timestamp())

            embed = discord.Embed(title=f"🎉 قيف اوي: {self.prize.value} 🎉", color=0x5865F2)
            embed.description = f"{self.description.value}\n\n**ينتهي السحب:** <t:{timestamp}:R>"
            embed.set_footer(text="اضغط على الزر أدناه للمشاركة!")

            await interaction.response.send_message("✅ جاري إرسال القيف اوي...", ephemeral=True)
            msg = await interaction.channel.send(embed=embed, view=GiveawayView())

            await asyncio.sleep(minutes * 60)
            await end_giveaway_action(msg, self.prize.value)
        except ValueError:
            await interaction.response.send_message("❌ يرجى إدخال رقم صحيح للدقائق.", ephemeral=True)

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.participants = []

    @discord.ui.button(label="(0) مشاركات", style=discord.ButtonStyle.primary, emoji="🎉", custom_id="join_gv_unique")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            return await interaction.response.send_message("❌ أنت مشارك بالفعل!", ephemeral=True)
        self.participants.append(interaction.user.id)
        button.label = f"({len(self.participants)}) مشاركات"
        await interaction.response.edit_message(view=self)

async def end_giveaway_action(message, prize_name):
    view = discord.ui.View.from_message(message)
    participants = []
    for item in view.children:
        if item.custom_id == "join_gv_unique":
            participants = getattr(view, 'participants', [])
    if not participants:
        await message.channel.send(f"😕 انتهى السحب على **{prize_name}** ولكن لم يشارك أحد.")
    else:
        winner_id = random.choice(participants)
        await message.channel.send(f"🎊 مبروك <@{winner_id}>! لقد فزت بـ **{prize_name}** 🎉")
    try: await message.delete()
    except: pass

class GiveawaySetupBtn(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="بدء إعداد الهدية", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GiveawayModal())

# --- نظام الإجازات ---
class VacationPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="أخذ إجازة", style=discord.ButtonStyle.success, emoji="📝", custom_id="take_vacation")
    async def take_vacation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if discord.utils.get(interaction.user.roles, id=WARNING_ROLE_ID):
            return await interaction.response.send_message("❌ لا يمكنك طلب إجازة ولديك إنذار إداري.", ephemeral=True)
... (149 lines left)

message.txt
