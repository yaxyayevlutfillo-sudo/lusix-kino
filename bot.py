
import os
import re
import json
import uuid
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

# =========================
# SETTINGS
# =========================

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB = DATA_DIR / "lusix.db"

UPLOADS = DATA_DIR / "uploads"
POSTERS = UPLOADS / "posters"
VIDEOS = UPLOADS / "videos"
POSTERS.mkdir(parents=True, exist_ok=True)
VIDEOS.mkdir(parents=True, exist_ok=True)

if os.getenv("BOT_TOKEN"):
    TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
else:
    with open(BASE / "bot_config.json", encoding="utf-8") as f:
        CONFIG = json.load(f)

    TOKEN = CONFIG["token"]
    ADMIN_ID = int(CONFIG["admin_id"])
NAME, TYPE, YEAR, DESC, POSTER_MODE, POSTER, VIDEO_MODE, VIDEO, VIP = range(9)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

# =========================
# DATABASE
# =========================

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def admin(update):
    return bool(
        update.effective_user
        and update.effective_user.id == ADMIN_ID
    )


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo‘shish", callback_data="add")],
        [InlineKeyboardButton("🎬 Kinolar", callback_data="movies")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="users")],
        [InlineKeyboardButton("⭐ VIP", callback_data="vip")],
        [InlineKeyboardButton("💳 To‘lovlar", callback_data="payments")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ])


async def say_menu(message):
    await message.reply_text(
        "🎬 LUSIX KINO ADMIN PANEL\nBo‘limni tanlang:",
        reply_markup=menu()
    )


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin(update):
        await update.message.reply_text("⛔ Siz admin emassiz.")
        return
    await say_menu(update.message)


# =========================
# ADD MOVIE
# =========================

async def begin_add(update, context):
    q = update.callback_query
    await q.answer()

    if not admin(update):
        await q.message.reply_text("⛔ Ruxsat yo‘q.")
        return ConversationHandler.END

    context.user_data.clear()
    await q.message.reply_text("🎬 Kino nomini yuboring:")
    return NAME


async def get_name(update, context):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "📂 Kino turini tanlang:\n"
        "film / serial / cartoon / anime"
    )
    return TYPE


async def get_type(update, context):
    value = update.message.text.lower().strip()
    if value not in ("film", "serial", "cartoon", "anime"):
        await update.message.reply_text(
            "❌ film, serial, cartoon yoki anime deb yozing."
        )
        return TYPE

    context.user_data["type"] = value
    await update.message.reply_text("📅 Kino yilini kiriting:")
    return YEAR


async def get_year(update, context):
    value = update.message.text.strip()
    if not value.isdigit() or not 1888 <= int(value) <= 2100:
        await update.message.reply_text("❌ Yil noto‘g‘ri.")
        return YEAR

    context.user_data["year"] = int(value)
    await update.message.reply_text("📝 Kino haqida tavsif yozing:")
    return DESC


async def get_desc(update, context):
    context.user_data["description"] = update.message.text.strip()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 URL orqali", callback_data="poster_url")],
        [InlineKeyboardButton("🖼 Galereyadan", callback_data="poster_file")],
        [InlineKeyboardButton("⏭ Postersiz", callback_data="poster_skip")]
    ])

    await update.message.reply_text(
        "🖼 Poster qo‘shish usulini tanlang:",
        reply_markup=keyboard
    )
    return POSTER_MODE


# =========================
# POSTER METHOD
# =========================

async def poster_mode(update, context):
    q = update.callback_query
    await q.answer()

    if q.data == "poster_url":
        context.user_data["poster_kind"] = "url"
        await q.message.reply_text("🌐 Poster rasmining URL manzilini yuboring:")
        return POSTER

    if q.data == "poster_file":
        context.user_data["poster_kind"] = "file"
        await q.message.reply_text("🖼 Galereyadan JPG, PNG yoki WEBP rasm yuboring:")
        return POSTER

    context.user_data["poster"] = ""
    return await ask_video_mode(q.message)


async def ask_video_mode(message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 URL orqali", callback_data="video_url")],
        [InlineKeyboardButton("📁 Galereyadan", callback_data="video_file")],
        [InlineKeyboardButton("⏭ Videosiz", callback_data="video_skip")]
    ])
    await message.reply_text(
        "🎥 Video qo‘shish usulini tanlang:",
        reply_markup=keyboard
    )
    return VIDEO_MODE


async def get_poster(update, context):
    message = update.message
    kind = context.user_data.get("poster_kind")

    if kind == "url":
        url = message.text.strip()
        if not re.match(r"^https?://", url, re.I):
            await message.reply_text("❌ To‘g‘ri HTTP yoki HTTPS URL yuboring.")
            return POSTER
        context.user_data["poster"] = url

    else:
        if message.photo:
            file_id = message.photo[-1].file_id
            ext = ".jpg"
        elif message.document and message.document.mime_type:
            mime = message.document.mime_type.lower()
            if mime not in ("image/jpeg", "image/png", "image/webp"):
                await message.reply_text("❌ Rasm fayl yuboring.")
                return POSTER
            file_id = message.document.file_id
            ext = Path(message.document.file_name or "poster.jpg").suffix.lower()
            if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
        else:
            await message.reply_text("❌ Rasm yuboring.")
            return POSTER

        filename = uuid.uuid4().hex + ext
        path = POSTERS / filename

        try:
            f = await context.bot.get_file(file_id)
            await f.download_to_drive(custom_path=str(path))
        except Exception:
            await message.reply_text("❌ Rasm yuklanmadi. Qayta urinib ko‘ring.")
            return POSTER

        context.user_data["poster"] = "/uploads/posters/" + filename

    return await ask_video_mode(message)


# =========================
# VIDEO METHOD
# =========================

async def video_mode(update, context):
    q = update.callback_query
    await q.answer()

    if q.data == "video_url":
        context.user_data["video_kind"] = "url"
        await q.message.reply_text("🌐 Video URL manzilini yuboring:")
        return VIDEO

    if q.data == "video_file":
        context.user_data["video_kind"] = "file"
        await q.message.reply_text("📁 Galereyadan MP4 video yuboring:")
        return VIDEO

    context.user_data["video"] = ""
    return await ask_vip(q.message)


async def get_video(update, context):
    message = update.message

    if context.user_data.get("video_kind") == "url":
        url = message.text.strip()
        if not re.match(r"^https?://", url, re.I):
            await message.reply_text("❌ To‘g‘ri HTTP yoki HTTPS URL yuboring.")
            return VIDEO
        context.user_data["video"] = url

    else:
        if message.video:
            file_id = message.video.file_id
            ext = ".mp4"
        elif message.document and (
            message.document.mime_type == "video/mp4"
            or (message.document.file_name or "").lower().endswith(".mp4")
        ):
            file_id = message.document.file_id
            ext = ".mp4"
        else:
            await message.reply_text("❌ MP4 video yuboring.")
            return VIDEO

        filename = uuid.uuid4().hex + ext
        path = VIDEOS / filename

        try:
            f = await context.bot.get_file(file_id)
            await f.download_to_drive(custom_path=str(path))
        except Exception:
            await message.reply_text(
                "❌ Video yuklanmadi. Fayl hajmi Telegram Bot API "
                "cheklovidan oshgan bo‘lishi mumkin."
            )
            return VIDEO

        context.user_data["video"] = "/uploads/videos/" + filename

    return await ask_vip(message)


async def ask_vip(message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ VIP", callback_data="vip_yes")],
        [InlineKeyboardButton("🆓 Oddiy", callback_data="vip_no")]
    ])
    await message.reply_text(
        "Kontent turini tanlang:",
        reply_markup=keyboard
    )
    return VIP


# =========================
# SAVE MOVIE
# =========================

async def save_movie(update, context):
    q = update.callback_query
    await q.answer()

    if q.data not in ("vip_yes", "vip_no"):
        return VIP

    data = dict(context.user_data)
    is_vip = 1 if q.data == "vip_yes" else 0

    try:
        con = db()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO movies
            (name, type, year, description, poster, video, is_vip, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["name"],
            data["type"],
            data["year"],
            data["description"],
            data.get("poster", ""),
            data.get("video", ""),
            is_vip,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        movie_id = cur.lastrowid
        con.commit()
        con.close()

    except Exception:
        logging.exception("Movie save error")
        await q.message.reply_text("❌ Kinoni bazaga saqlashda xato.")
        return ConversationHandler.END

    context.user_data.clear()
    await q.message.reply_text(
        "✅ KINO SAQLANDI!\n\n"
        f"🎬 {data['name']}\n"
        f"🆔 ID: {movie_id}\n"
        f"⭐ VIP: {'Ha' if is_vip else 'Yo‘q'}\n\n"
        "Saytni yangilab tekshiring.",
        reply_markup=menu()
    )
    return ConversationHandler.END


# =========================
# CANCEL
# =========================

async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=menu())
    return ConversationHandler.END


# =========================
# ADMIN MENU
# =========================

async def buttons(update, context):
    q = update.callback_query
    await q.answer()

    if not admin(update):
        await q.message.reply_text("⛔ Ruxsat yo‘q.")
        return

    data = q.data

    if data == "movies":
        con = db()
        rows = con.execute(
            "SELECT id,name,type,year FROM movies ORDER BY id DESC LIMIT 30"
        ).fetchall()
        con.close()

        if not rows:
            await q.message.reply_text("Kinolar hali yo‘q.")
            return

        for m in rows:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑 O‘chirish", callback_data=f"del:{m['id']}")
            ]])
            await q.message.reply_text(
                f"🎬 {m['name']}\nID: {m['id']}\n{m['type']} • {m['year']}",
                reply_markup=kb
            )

    elif data.startswith("del:"):
        movie_id = int(data.split(":")[1])
        con = db()
        con.execute("DELETE FROM favorites WHERE movie_id=?", (movie_id,))
        con.execute("DELETE FROM watch_history WHERE movie_id=?", (movie_id,))
        con.execute("DELETE FROM episodes WHERE movie_id=?", (movie_id,))
        con.execute("DELETE FROM movies WHERE id=?", (movie_id,))
        con.commit()
        con.close()
        await q.message.reply_text("✅ Kino o‘chirildi.")

    elif data == "users":
        con = db()
        count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        con.close()
        await q.message.reply_text(f"👥 Foydalanuvchilar: {count}")

    elif data == "vip":
        await q.message.reply_text(
            "VIP berish:\n/vip email@example.com 30"
        )

    elif data == "payments":
        con = db()
        rows = con.execute(
            "SELECT * FROM payments ORDER BY id DESC LIMIT 15"
        ).fetchall()
        con.close()

        if not rows:
            await q.message.reply_text("To‘lovlar mavjud emas.")
            return

        for p in rows:
            await q.message.reply_text(
                f"💳 ID: {p['id']}\n"
                f"User: {p['user_id']}\n"
                f"Summa: {p['amount']}\n"
                f"Usul: {p['method']}\n"
                f"Holat: {p['status']}"
            )

    elif data == "stats":
        con = db()
        movies = con.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        subs = con.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE status='active'"
        ).fetchone()[0]
        pays = con.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        con.close()

        await q.message.reply_text(
            "📊 STATISTIKA\n\n"
            f"🎬 Kinolar: {movies}\n"
            f"👥 Foydalanuvchilar: {users}\n"
            f"⭐ Faol VIP: {subs}\n"
            f"💳 To‘lovlar: {pays}"
        )


# =========================
# VIP
# =========================

async def vip_command(update, context):
    if not admin(update):
        await update.message.reply_text("⛔ Ruxsat yo‘q.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("/vip email@example.com 30")
        return

    email = context.args[0]
    try:
        days = int(context.args[1])
        if days < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Kun sonini to‘g‘ri kiriting.")
        return

    con = db()
    user = con.execute(
        "SELECT id FROM users WHERE email=?", (email,)
    ).fetchone()

    if not user:
        con.close()
        await update.message.reply_text("Bunday foydalanuvchi topilmadi.")
        return

    expiry = datetime.now() + timedelta(days=days)
    con.execute("""
        INSERT INTO subscriptions (user_id,plan,expires_at,status)
        VALUES (?,?,?,'active')
    """, (
        user["id"],
        f"{days} kunlik VIP",
        expiry.strftime("%Y-%m-%d %H:%M:%S")
    ))
    con.commit()
    con.close()

    await update.message.reply_text(f"✅ {email} uchun VIP berildi.")


# =========================
# ERROR
# =========================

async def error_handler(update, context):
    logging.error("BOT ERROR", exc_info=context.error)


# =========================
# MAIN
# =========================

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(begin_add, pattern="^add$")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_type)],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_year)],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc)],
            POSTER_MODE: [
                CallbackQueryHandler(poster_mode, pattern="^poster_")
            ],
            POSTER: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND
                    | filters.PHOTO
                    | filters.Document.IMAGE,
                    get_poster
                )
            ],
            VIDEO_MODE: [
                CallbackQueryHandler(video_mode, pattern="^video_")
            ],
            VIDEO: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND
                    | filters.VIDEO
                    | filters.Document.VIDEO,
                    get_video
                )
            ],
            VIP: [
                CallbackQueryHandler(save_movie, pattern="^vip_(yes|no)$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CommandHandler("vip", vip_command))
    app.add_error_handler(error_handler)

    print("LUSIX KINO BOT IS RUNNING")
    app.run_polling()


if __name__ == "__main__":
    main()
