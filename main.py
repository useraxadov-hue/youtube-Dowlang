import asyncio
import json
import logging
import os
import tempfile
import subprocess

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

# =============================================
# SOZLAMALAR — faqat shu 2 ta o'zgartiring
# =============================================
TOKEN = os.getenv("BOT_TOKEN", "8269983303:AAFgcvk0J6ml9Y00WtdIFh2UadlYlgsO5l4")
MAX_FILE_MB = 50  # Telegram bepul bot limiti: 50MB
# =============================================

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 *YouTube Video Yuklovchi Bot*\n\n"
        "Havolalarni JSON formatida yuboring:\n"
        '`["https://youtu.be/GgeGQ4BdbQ8"]`\n\n'
        "Yoki oddiy link yuboring:\n"
        "`https://youtu.be/GgeGQ4BdbQ8`\n\n"
        "✅ YouTube, Shorts, TikTok, Instagram va boshqalar ishlaydi!",
        parse_mode="Markdown"
    )


async def download_and_send(message: Message, url: str, index: int = 1, total: int = 1):
    """yt-dlp orqali yuklab Telegramga yuboradi"""
    label = f"[{index}/{total}] " if total > 1 else ""

    status = await message.answer(f"⏳ {label}Yuklanmoqda...")

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "video.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[height<=720]/best",
            "--merge-output-format", "mp4",
            "--max-filesize", f"{MAX_FILE_MB}M",
            "--write-thumbnail",
            "--convert-thumbnails", "jpg",
            "-o", output_path,
            "--print", "after_move:filepath",  # Fayl yo'lini chiqaradi
            url
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            if proc.returncode != 0:
                err_text = stderr.decode(errors="ignore")[-500:]
                logging.error(f"yt-dlp xato: {err_text}")

                # Xato sababini foydalanuvchiga tushunarli ko'rsatish
                if "File is larger than max-filesize" in err_text:
                    msg = f"❌ Video {MAX_FILE_MB}MB dan katta — Telegram limiti."
                elif "Sign in to confirm" in err_text or "cookies" in err_text.lower():
                    msg = "❌ YouTube login talab qilmoqda (katta yoki yoshga cheklangan video)."
                elif "Video unavailable" in err_text:
                    msg = "❌ Video mavjud emas yoki yopiq."
                elif "not a valid URL" in err_text:
                    msg = "❌ Noto'g'ri URL format."
                else:
                    msg = f"❌ Yuklash muvaffaqiyatsiz:\n`{err_text[-300:]}`"

                await status.edit_text(msg, parse_mode="Markdown")
                return

            # Yuklangan faylni topish
            video_file = None
            thumb_file = None

            for fname in os.listdir(tmpdir):
                fpath = os.path.join(tmpdir, fname)
                if fname.endswith(".mp4"):
                    video_file = fpath
                elif fname.endswith(".jpg") or fname.endswith(".webp"):
                    thumb_file = fpath

            if not video_file:
                await status.edit_text("❌ Video fayl topilmadi.")
                return

            file_size_mb = os.path.getsize(video_file) / (1024 * 1024)
            await status.edit_text(f"📤 {label}Telegram'ga yuklanmoqda ({file_size_mb:.1f}MB)...")

            video_input = FSInputFile(video_file)
            thumb_input = FSInputFile(thumb_file) if thumb_file else None

            # Video metadata olish (nomi)
            title_cmd = ["yt-dlp", "--no-playlist", "--print", "title", url]
            title_proc = await asyncio.create_subprocess_exec(
                *title_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            title_out, _ = await asyncio.wait_for(title_proc.communicate(), timeout=30)
            title = title_out.decode(errors="ignore").strip() or "Video"

            # Telegramga yuborish
            await message.answer_video(
                video=video_input,
                thumbnail=thumb_input,
                caption=f"🎬 {title[:900]}",
                supports_streaming=True,
            )
            await status.delete()

        except asyncio.TimeoutError:
            await status.edit_text("⏱ Timeout: video juda katta yoki internet sekin.")
        except FileNotFoundError:
            await status.edit_text(
                "❌ `yt-dlp` o'rnatilmagan!\n\n"
                "Railway'da Dockerfile kerak. Pastdagi ko'rsatmani bajaring.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.exception(e)
            await status.edit_text(f"❌ Kutilmagan xato: `{str(e)[:300]}`", parse_mode="Markdown")


# ✅ JSON ro'yxat: ["url1", "url2"]
@dp.message(F.text.startswith("["))
async def handle_json_links(message: Message):
    try:
        links = json.loads(message.text)
        if not isinstance(links, list) or not links:
            await message.reply("❌ Bo'sh yoki noto'g'ri ro'yxat.")
            return
    except json.JSONDecodeError:
        await message.reply(
            "❌ JSON xatosi. Format: `[\"link1\", \"link2\"]`",
            parse_mode="Markdown"
        )
        return

    await message.reply(f"✅ {len(links)} ta havola qabul qilindi.")

    for i, url in enumerate(links, 1):
        await download_and_send(message, url.strip(), i, len(links))


# ✅ Oddiy link yuborilsa
@dp.message(F.text.regexp(r'https?://'))
async def handle_plain_link(message: Message):
    url = message.text.strip()
    await download_and_send(message, url)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.info("Bot ishga tushdi (yt-dlp rejimi)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
