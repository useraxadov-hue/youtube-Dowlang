import asyncio
import json
import logging
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, URLInputFile
from aiogram.filters import Command

# Bot tokenini shu yerga kiriting
TOKEN = "8269983303:AAFgcvk0J6ml9Y00WtdIFh2UadlYlgsO5l4"

bot = Bot(token=TOKEN)
dp = Dispatcher()

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

    async with aiohttp.ClientSession() as session:
        for url in links:
            try:
                cobalt_api = "https://api.cobalt.tools/api/json"
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
                payload = {
                    "url": url,
                    "vQuality": "720"  # Sifatni 720p qilib belgilaymiz
                }
                
                async with session.post(cobalt_api, json=payload, headers=headers) as response:
                    if response.status == 200:
                        res_data = await response.json()
                        video_url = res_data.get("url")
                        video_title = res_data.get("text", "YouTube Video")
                        
                        if video_url:
                            # Telegram videoni serverdan to'g'ridan-to'g'ri havola orqali yuklab oladi
                            video_file = URLInputFile(video_url)
                            await message.answer_video(video=video_file, caption=video_title)
                        else:
                            await message.answer(f"❌ Video havolasini olib bo'lmadi: {url}")
                    else:
                        await message.answer(f"❌ Yuklash muvaffaqiyatsiz tugadi (Cobalt API xatosi): {url}")
            except Exception as e:
                await message.answer(f"❌ Quyidagi havolada xatolik yuz berdi: {url}\nSebab: `{str(e)}`", parse_mode="Markdown")

    await status_msg.edit_text("✅ Jarayon yakunlandi!")

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot hostingda muammosiz ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
