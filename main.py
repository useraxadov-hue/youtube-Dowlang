import asyncio
import json
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, URLInputFile
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN", "8269983303:AAFgcvk0J6ml9Y00WtdIFh2UadlYlgsO5l4")

# O'zingizning Cobalt instance URL'ingiz (Railway'da deploy qilingan)
COBALT_API = os.getenv("COBALT_API_URL", "https://your-cobalt-instance.up.railway.app")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = (
        "👋 *Salom! YouTube videolarni yuklovchi botga xush kelibsiz!*\n\n"
        "Menga videolarni yuklash uchun havolalarni *JSON formatida* yuboring.\n\n"
        "*Format namunasi:*\n"
        '`["https://www.youtube.com/watch?v=GgeGQ4BdbQ8"]`'
    )
    await message.reply(welcome_text, parse_mode="Markdown")


@dp.message(F.text.startswith("["))
async def handle_links(message: Message):
    try:
        links = json.loads(message.text)
        if not isinstance(links, list):
            await message.reply("❌ Format xato. Iltimos, ro'yxat (list) ko'rinishida yuboring.")
            return
    except json.JSONDecodeError:
        await message.reply(
            "❌ JSON formatida xatolik bor.\nTo'g'ri format: `[\"link1\", \"link2\"]`",
            parse_mode="Markdown"
        )
        return

    status_msg = await message.reply(f"⏳ {len(links)} ta havola qabul qilindi. Yuklash boshlanmoqda...")

    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(links, 1):
            try:
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                payload = {
                    "url": url,
                    "videoQuality": "720",     # Yangi Cobalt API maydoni
                    "filenameStyle": "pretty",
                }

                async with session.post(
                    f"{COBALT_API.rstrip('/')}/",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    res_data = await response.json()

                    status = res_data.get("status")

                    if status == "redirect" or status == "stream":
                        video_url = res_data.get("url")
                        filename = res_data.get("filename", f"video_{i}.mp4")

                        if video_url:
                            video_file = URLInputFile(video_url, filename=filename)
                            await message.answer_video(
                                video=video_file,
                                caption=f"✅ {filename}"
                            )
                        else:
                            await message.answer(f"❌ Video URL topilmadi: `{url}`", parse_mode="Markdown")

                    elif status == "picker":
                        # Bir nechta media (masalan, playlist) bo'lsa
                        picker = res_data.get("picker", [])
                        if picker:
                            first = picker[0]
                            video_url = first.get("url")
                            if video_url:
                                video_file = URLInputFile(video_url)
                                await message.answer_video(video=video_file, caption=f"✅ Video {i}")
                        else:
                            await message.answer(f"❌ Picker bo'sh: `{url}`", parse_mode="Markdown")

                    elif status == "error":
                        error_code = res_data.get("error", {}).get("code", "noma'lum xato")
                        await message.answer(
                            f"❌ Cobalt xatosi (`{error_code}`):\n`{url}`",
                            parse_mode="Markdown"
                        )
                    else:
                        await message.answer(
                            f"❌ Kutilmagan javob (`status={status}`):\n`{url}`",
                            parse_mode="Markdown"
                        )

            except aiohttp.ClientConnectorError:
                await message.answer(
                    f"❌ Cobalt serveriga ulanib bo'lmadi.\n`COBALT_API_URL` ni tekshiring.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                await message.answer(
                    f"❌ Xatolik: `{url}`\nSabab: `{str(e)}`",
                    parse_mode="Markdown"
                )

    await status_msg.edit_text("✅ Jarayon yakunlandi!")


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
