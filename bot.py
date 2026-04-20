import discord
from discord.ext import commands
import yt_dlp
import os
import asyncio

# إعدادات التوكن
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # ضروري لقراءة الأوامر
intents.voice_states = True    # ضروري للصوت

bot = commands.Bot(command_prefix="!", intents=intents)

# إعدادات تشغيل الصوت
YDL_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch'}
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

class VoiceChannelSelect(discord.ui.Select):
    def __init__(self, url):
        self.url = url
        super().__init__(placeholder="🔊 اختر الروم الصوتي لبدء الأغنية...")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        channel = interaction.guild.get_channel(int(self.values[0]))
        
        try:
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.move_to(channel)
            else:
                await channel.connect()

            vc = interaction.guild.voice_client
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(self.url, download=False)
                if 'entries' in info: info = info['entries'][0]
                url2 = info['url']
                
                if vc.is_playing(): vc.stop()
                vc.play(discord.FFmpegPCMAudio(url2, **FFMPEG_OPTIONS))
                await interaction.followup.send(f"✅ تم التشغيل في: {channel.mention}")
        except Exception as e:
            await interaction.followup.send(f"❌ خطأ: {e}")

class MusicView(discord.ui.View):
    def __init__(self, url, channels):
        super().__init__(timeout=60)
        select = VoiceChannelSelect(url)
        for ch in channels[:25]:
            select.add_option(label=ch.name, value=str(ch.id))
        self.add_item(select)

# --- الأوامر ---

@bot.command()
async def play(ctx, *, search: str = None):
    if search is None:
        return await ctx.send("❌ يرجى كتابة اسم الأغنية أو الرابط بعد الأمر. مثال: `!play quran` ")

    voice_channels = ctx.guild.voice_channels
    if not voice_channels:
        return await ctx.send("❌ لا توجد رومات صوتية في السيرفر!")

    await ctx.send(f"🎵 جاري البحث عن: **{search}**... اختر الروم أدناه:", view=MusicView(search, voice_channels))

@bot.event
async def on_ready():
    print(f"✅ البوت متصل الآن باسم: {bot.user}")

bot.run(TOKEN)
