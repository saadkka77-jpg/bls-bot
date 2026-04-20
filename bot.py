import discord
from discord.ext import commands
import subprocess
import sys
import os
import asyncio

# محاولة تحميل المكتبات المطلوبة برمجياً في حال عدم وجودها
def install_requirements():
    requirements = ['yt-dlp', 'discord.py', 'PyNaCl']
    for lib in requirements:
        try:
            __import__(lib.replace('-', '_'))
        except ImportError:
            print(f"Installing {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

install_requirements()

import yt_dlp

# إعدادات البوت
TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# إعدادات تشغيل الصوت
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch', # يسمح بالبحث بالاسم وليس فقط الرابط
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# =========================
# قائمة اختيار الروم الصوتي
# =========================

class VoiceChannelSelect(discord.ui.Select):
    def __init__(self, url):
        self.url = url
        super().__init__(placeholder="🔊 اختر الروم الصوتي لبدء الأغنية...")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        channel = interaction.guild.get_channel(int(self.values[0]))
        
        # الاتصال أو الانتقال للروم
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()

        vc = interaction.guild.voice_client

        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(self.url, download=False)
                # إذا كان بحثاً، نأخذ أول نتيجة
                if 'entries' in info:
                    info = info['entries'][0]
                
                url2 = info['url']
                title = info.get('title', 'أغنية غير معروفة')
                
                if vc.is_playing():
                    vc.stop()
                
                vc.play(discord.FFmpegPCMAudio(url2, **FFMPEG_OPTIONS))
                await interaction.followup.send(f"✅ تم التشغيل: **{title}**\n📍 في روم: {channel.mention}")
            except Exception as e:
                await interaction.followup.send(f"❌ حدث خطأ فني: {e}")

class MusicView(discord.ui.View):
    def __init__(self, url, channels):
        super().__init__(timeout=60)
        select = VoiceChannelSelect(url)
        for ch in channels[:25]:
            select.add_option(label=ch.name, value=str(ch.id))
        self.add_item(select)

# =========================
# الأوامر
# =========================

@bot.command()
async def play(ctx, *, search: str):
    voice_channels = ctx.guild.voice_channels
    if not voice_channels:
        return await ctx.send("❌ لا توجد رومات صوتية في السيرفر!")

    embed = discord.Embed(
        title="🎵 مشغل الموسيقى",
        description="اختر الروم الصوتي الذي تريد من البوت دخوله:",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed, view=MusicView(search, voice_channels))

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 تم الخروج من الروم الصوتي.")
    else:
        await ctx.send("⚠️ أنا لست في روم صوتي حالياً.")

@bot.event
async def on_ready():
    print(f"🚀 {bot.user} Online!")

bot.run(TOKEN)
