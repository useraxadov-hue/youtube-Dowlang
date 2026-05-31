import asyncio
import json
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command  # Yangi filter qo'shildi
import yt_dlp

# Bot tokenini shu yerga kiriting
TOKEN = "8269983303:AAFgcvk0J6ml9Y00WtdIFh2UadlYlgsO5l4"

bot = Bot(token=TOKEN)
dp = Dispatcher()

def download_video_sync(url):
    """Videoni yt-dlp yordamida yuklab olish (Blokirovkani chetlab o'tish sozlamalari bilan)"""
    ydl_opts = {
        # Telegram API uchun 50MB cheklov
        'format': 'best[filesize<50M]/best', 
        'outtmpl': '%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # YouTube blokirovkasini aylanib o'tish uchun mobil qurilma simulyatsiyasi
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android'],
                'player_skip': ['webpage', 'configs']
            }
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', "Noma'lum video")
        filename = ydl.prepare_filename(info)
        return filename, title

# === /start buyrug'i uchun handler ===
@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = (
        "👋 **Salom! YouTube videolarni yuklovchi botga xush kelibsiz!**\n\n"
        "Menga videolarni yuklash uchun havolalar ro'yxatini **JSON formatida** yuboring.\n\n"
        "**To'g'ri format na'munasi:**\n"
        "`[\"https://www.youtube.com/watch?v=GgeGQ4BdbQ8\"]`"
    )
    await message.reply(welcome_text, parse_mode="Markdown")

# === JSON havolalar ro'yxatini qabul qilish ===
@dp.message(F.text.startswith("["))
async def handle_links(message: Message):
    try:
        links = json.loads(message.text)
        if not isinstance(links, list):
            await message.reply("❌ Format xato. Iltimos, ro'yxat (list) ko'rinishida yuboring.")
            return
    except json.JSONDecodeError:
        await message.reply("❌ JSON formatida xatolik bor.\nTo'g'ri format: `[\"link1\", \"link2\"]`", parse_mode="Markdown")
        return

    status_msg = await message.reply(f"⏳ {len(links)} ta havola qabul qilindi. Yuklash boshlanmoqda...")

    for url in links:
        try:
            # Server qotib qolmasligi uchun yuklashni alohida oqimda bajaramiz
            filename, title = await asyncio.to_thread(download_video_sync, url)
            
            # Videoni Telegramga yuklash
            video = FSInputFile(filename)
            await message.answer_video(video=video, caption=title)
            
            # Railway xotirasi to'lib qolmasligi uchun darhol faylni o'chiramiz
            if os.path.exists(filename):
                os.remove(filename)
                
        except Exception as e:
            await message.answer(f"❌ Quyidagi havolada xatolik yuz berdi: {url}\nSebab: `{str(e)}`", parse_mode="Markdown")

    await status_msg.edit_text("✅ Barcha videolar muvaffaqiyatli yuklandi va yuborildi!")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot hostingda ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
