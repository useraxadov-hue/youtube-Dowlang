import asyncio
import json
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, URLInputFile
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN", "8269983303:AAFgcvk0J6ml9Y00WtdIFh2UadlYlgsO5l4")
COBALT_API = os.getenv("COBALT_API_URL", "https://your-cobalt-instance.up.railway.app")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 *Salom! YouTube videolarni yuklovchi bot*\n\n"
        "JSON formatida yuboring:\n"
        '`["https://www.youtube.com/watch?v=GgeGQ4BdbQ8"]`',
        parse_mode="Markdown"
    )


@dp.message(Command("ping"))
async def cmd_ping(message: Message):
    """Cobalt instance ishlayaptimi tekshirish"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                COBALT_API.rstrip('/') + '/',
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                cobalt_info = data.get("cobalt", {})
                version = cobalt_info.get("version", "?")
                services = cobalt_info.get("services", [])
                yt_ok = "youtube" in services

                await message.reply(
                    f"✅ Cobalt instance ishlayapti!\n"
                    f"📦 Version: `{version}`\n"
                    f"🎬 YouTube: {'✅' if yt_ok else '❌'}",
                    parse_mode="Markdown"
                )
    except Exception as e:
        await message.reply(f"❌ Instance javob bermadi:\n`{e}`", parse_mode="Markdown")


@dp.message(F.text.startswith("["))
async def handle_links(message: Message):
    try:
        links = json.loads(message.text)
        if not isinstance(links, list):
            await message.reply("❌ Ro'yxat (list) ko'rinishida yuboring.")
            return
    except json.JSONDecodeError:
        await message.reply(
            "❌ JSON xatosi. Format: `[\"link1\"]`",
            parse_mode="Markdown"
        )
        return

    status_msg = await message.reply(f"⏳ {len(links)} ta havola — yuklash boshlanmoqda...")

    async with aiohttp.ClientSession() as session:
        for i, url in enumerate(links, 1):
            await status_msg.edit_text(f"⏳ {i}/{len(links)} yuklanmoqda...")
            try:
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                payload = {
                    "url": url,
                    "videoQuality": "720",
                    "filenameStyle": "pretty",
                    "downloadMode": "auto",
                }

                async with session.post(
                    COBALT_API.rstrip('/') + '/',
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    raw_text = await response.text()
                    logging.info(f"[Cobalt] Status: {response.status}, Body: {raw_text}")

                    # HTTP status xatosi
                    if response.status != 200:
                        await message.answer(
                            f"❌ HTTP {response.status} xatosi:\n`{raw_text[:300]}`",
                            parse_mode="Markdown"
                        )
                        continue

                    try:
                        res_data = json.loads(raw_text)
                    except json.JSONDecodeError:
                        await message.answer(f"❌ JSON parse xatosi:\n`{raw_text[:300]}`", parse_mode="Markdown")
                        continue

                    status = res_data.get("status", "yo'q")

                    # ✅ redirect — to'g'ridan-to'g'ri CDN URL
                    if status == "redirect":
                        video_url = res_data.get("url")
                        filename = res_data.get("filename", f"video_{i}.mp4")
                        video_file = URLInputFile(video_url, filename=filename)
                        await message.answer_video(video=video_file, caption=f"✅ {filename}")

                    # ✅ tunnel/stream — Cobalt proxy orqali
                    elif status in ("tunnel", "stream"):
                        video_url = res_data.get("url")
                        filename = res_data.get("filename", f"video_{i}.mp4")
                        video_file = URLInputFile(video_url, filename=filename)
                        await message.answer_video(video=video_file, caption=f"✅ {filename}")

                    # 🔀 picker — bir nechta media (playlist, gallery)
                    elif status == "picker":
                        items = res_data.get("picker", [])
                        sent = 0
                        for item in items[:5]:  # max 5 ta
                            v_url = item.get("url")
                            if v_url:
                                vf = URLInputFile(v_url)
                                await message.answer_video(video=vf, caption=f"✅ Video {sent+1}")
                                sent += 1
                        if sent == 0:
                            await message.answer(f"❌ Picker bo'sh: `{url}`", parse_mode="Markdown")

                    # ❌ error
                    elif status == "error":
                        # Turli Cobalt versiyalarida error format farq qiladi
                        error_obj = res_data.get("error", {})
                        if isinstance(error_obj, dict):
                            code = error_obj.get("code", "")
                            context = error_obj.get("context", "")
                        else:
                            code = str(error_obj)
                            context = ""

                        text = res_data.get("text", "")  # eski format

                        error_msg = code or text or "noma'lum"
                        await message.answer(
                            f"❌ Cobalt xatosi: `{error_msg}`\n"
                            f"{'📎 ' + str(context) if context else ''}\n"
                            f"🔗 URL: `{url}`\n\n"
                            f"📋 To'liq javob:\n`{raw_text[:400]}`",
                            parse_mode="Markdown"
                        )

                    # ❓ noma'lum status
                    else:
                        await message.answer(
                            f"❓ Noma'lum status: `{status}`\n"
                            f"📋 To'liq javob:\n`{raw_text[:400]}`",
                            parse_mode="Markdown"
                        )

            except aiohttp.ClientConnectorError as e:
                await message.answer(
                    f"❌ Cobalt serveriga ulanib bo'lmadi!\n"
                    f"COBALT\\_API\\_URL: `{COBALT_API}`\n"
                    f"Sabab: `{e}`",
                    parse_mode="Markdown"
                )
            except asyncio.TimeoutError:
                await message.answer(f"⏱ Timeout: `{url}`", parse_mode="Markdown")
            except Exception as e:
                await message.answer(
                    f"❌ Kutilmagan xato: `{url}`\nSabab: `{str(e)}`",
                    parse_mode="Markdown"
                )

    await status_msg.edit_text("✅ Jarayon yakunlandi!")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.info(f"Bot ishga tushdi. Cobalt: {COBALT_API}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
