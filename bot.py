import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True # مهم جداً للصوت

bot = commands.Bot(command_prefix="!", intents=intents)

# إعدادات مستخرج الصوت (yt-dlp)
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
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
        # جلب القنوات الصوتية في السيرفر فقط
        super().__init__(placeholder="اختر الروم الصوتي الذي تريد تشغيل الأغنية فيه...")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer() # تأخير الرد لتجنب انتهاء الوقت
        
        channel = interaction.guild.get_channel(int(self.values[0]))
        
        # الاتصال بالروم
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()

        vc = interaction.guild.voice_client

        # استخراج رابط الصوت وتشغيله
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(self.url, download=False)
                url2 = info['url']
                title = info.get('title', 'أغنية')
                
                if vc.is_playing():
                    vc.stop()
                
                vc.play(discord.FFmpegPCMAudio(url2, **FFMPEG_OPTIONS))
                await interaction.followup.send(f"🎶 جاري تشغيل: **{title}** في {channel.mention}")
            except Exception as e:
                await interaction.followup.send(f"❌ حدث خطأ أثناء التشغيل: {e}")

class MusicView(discord.ui.View):
    def __init__(self, url, channels):
        super().__init__(timeout=60)
        select = VoiceChannelSelect(url)
        # إضافة أول 25 روم صوتي للقائمة (حد ديسكورد الأقصى)
        for ch in channels[:25]:
            select.add_option(label=ch.name, value=str(ch.id), emoji="🔊")
        self.add_item(select)

# =========================
# أمر التشغيل (الرابط)
# =========================

@bot.command()
async def play(ctx, *, url: str):
    # التحقق من وجود رومات صوتية
    voice_channels = ctx.guild.voice_channels
    if not voice_channels:
        return await ctx.send("لا توجد رومات صوتية في هذا السيرفر!")

    # إرسال القائمة للمستخدم
    embed = discord.Embed(
        title="🎵 نظام الموسيقى",
        description="الرجاء اختيار الروم الصوتي من القائمة أدناه لبدء التشغيل",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=MusicView(url, voice_channels))

# =========================
# أمر الإيقاف والخروج
# =========================

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("🛑 تم إيقاف التشغيل والخروج من الروم.")
    else:
        await ctx.send("أنا لست متصلاً بروم صوتي أصلاً!")

@bot.event
async def on_ready():
    print(f"✅ تم تشغيل بوت الأغاني: {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!play [link]"))

bot.run(TOKEN)
