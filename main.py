import os
import threading
import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kmt-control")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
APP_API_KEY = os.getenv("APP_API_KEY", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("Missing BOT_TOKEN environment variable")
if not ADMIN_ID_RAW.isdigit():
    raise RuntimeError("Set ADMIN_ID to your numeric Telegram user ID")
if not APP_API_KEY:
    raise RuntimeError("Set APP_API_KEY to a long random secret")

ADMIN_ID = int(ADMIN_ID_RAW)

# NOTE: This starter version stores settings in memory.
# They reset when the service restarts/redeploys. Add persistent storage before production use.
STATE = {
    "maintenance": False,
    "downloads_enabled": True,
    "notice": "",
}

app = FastAPI(title="KMT FB DOWNLOAD Control API", version="1.0.0")
_bot_thread: Optional[threading.Thread] = None


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == ADMIN_ID)


def keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [
            InlineKeyboardButton("🛠 Maintenance ON/OFF", callback_data="maintenance"),
            InlineKeyboardButton("⬇️ Download ON/OFF", callback_data="downloads"),
        ],
        [InlineKeyboardButton("ℹ️ Current Notice", callback_data="notice")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ ဒီ Bot ကို Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    await update.effective_message.reply_text(
        "KMT FB DOWNLOAD Control Panel\n\n/panel — Control Panel\n/status — Server/setting status\n/maintenance — Maintenance ဖွင့်/ပိတ်\n/download_on — Download ဖွင့်\n/download_off — Download ပိတ်\n/notice <စာသား> — App အသုံးပြုသူများအတွက် ကြေညာချက်\n/notice_clear — ကြေညာချက်ဖျက်",
        reply_markup=keyboard(),
    )


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    await update.effective_message.reply_text("Admin Panel — လုပ်ဆောင်ချက်တစ်ခု ရွေးပါ။", reply_markup=keyboard())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    await update.effective_message.reply_text(
        "🟢 API process is running\n"
        f"Maintenance: {'ON' if STATE['maintenance'] else 'OFF'}\n"
        f"Downloads: {'ON' if STATE['downloads_enabled'] else 'OFF'}\n"
        f"Notice: {STATE['notice'] or '(မရှိပါ)'}"
    )


async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    STATE["maintenance"] = not STATE["maintenance"]
    await update.effective_message.reply_text(
        f"🛠 Maintenance {'ON' if STATE['maintenance'] else 'OFF'}"
    )


async def download_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    STATE["downloads_enabled"] = True
    await update.effective_message.reply_text("✅ Download function ON")


async def download_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    STATE["downloads_enabled"] = False
    await update.effective_message.reply_text("⛔ Download function OFF")


async def notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /notice မင်္ဂလာပါ။ Server ပြုပြင်နေပါသည်။")
        return
    STATE["notice"] = msg[:1000]
    await update.effective_message.reply_text("✅ Notice သိမ်းပြီးပါပြီ။ App က /config endpoint မှတစ်ဆင့် ရယူနိုင်ပါတယ်။")


async def notice_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    STATE["notice"] = ""
    await update.effective_message.reply_text("✅ Notice ဖျက်ပြီးပါပြီ။")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        await query.answer("Admin only", show_alert=True)
        return
    await query.answer()
    if query.data == "status":
        await query.edit_message_text(
            "🟢 API process is running\n"
            f"Maintenance: {'ON' if STATE['maintenance'] else 'OFF'}\n"
            f"Downloads: {'ON' if STATE['downloads_enabled'] else 'OFF'}\n"
            f"Notice: {STATE['notice'] or '(မရှိပါ)'}",
            reply_markup=keyboard(),
        )
    elif query.data == "maintenance":
        STATE["maintenance"] = not STATE["maintenance"]
        await query.edit_message_text(f"Maintenance {'ON' if STATE['maintenance'] else 'OFF'}", reply_markup=keyboard())
    elif query.data == "downloads":
        STATE["downloads_enabled"] = not STATE["downloads_enabled"]
        await query.edit_message_text(f"Download {'ON' if STATE['downloads_enabled'] else 'OFF'}", reply_markup=keyboard())
    elif query.data == "notice":
        await query.edit_message_text(f"Current notice: {STATE['notice'] or '(မရှိပါ)'}", reply_markup=keyboard())


def run_bot():
    import asyncio

    async def bot_main():
        from telegram.request import HTTPXRequest

request = HTTPXRequest(
    connection_pool_size=8,
    connect_timeout=30.0,
    read_timeout=30.0,
    write_timeout=30.0,
    pool_timeout=30.0,
)

get_updates_request = HTTPXRequest(
    connection_pool_size=2,
    connect_timeout=30.0,
    read_timeout=40.0,
    write_timeout=30.0,
    pool_timeout=30.0,
)

bot = (
    Application.builder()
    .token(BOT_TOKEN)
    .request(request)
    .get_updates_request(get_updates_request)
    .build()
)

        bot.add_handler(CommandHandler("start", start))
        bot.add_handler(CommandHandler("panel", panel))
        bot.add_handler(CommandHandler("status", status))
        bot.add_handler(CommandHandler("maintenance", maintenance))
        bot.add_handler(CommandHandler("download_on", download_on))
        bot.add_handler(CommandHandler("download_off", download_off))
        bot.add_handler(CommandHandler("notice", notice))
        bot.add_handler(CommandHandler("notice_clear", notice_clear))
        bot.add_handler(CallbackQueryHandler(button_handler))

        await bot.initialize()
        await bot.start()

        if bot.updater is not None:
            await bot.updater.start_polling(drop_pending_updates=True)

        log.info("Telegram bot started successfully")

        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            if bot.updater is not None:
                await bot.updater.stop()
            await bot.stop()
            await bot.shutdown()

    try:
        asyncio.run(bot_main())
    except Exception:
        log.exception("Telegram bot stopped")


@app.on_event("startup")
def startup_event():
    global _bot_thread
    _bot_thread = threading.Thread(target=run_bot, daemon=True)
    _bot_thread.start()


@app.get("/")
def root():
    return {"service": "KMT FB DOWNLOAD Control API", "status": "ok", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def public_config():
    return {
        "maintenance": STATE["maintenance"],
        "downloads_enabled": STATE["downloads_enabled"],
        "notice": STATE["notice"],
    }


class SettingsUpdate(BaseModel):
    maintenance: Optional[bool] = None
    downloads_enabled: Optional[bool] = None
    notice: Optional[str] = None


@app.post("/admin/settings")
def update_settings(data: SettingsUpdate, x_api_key: str = Header(default="")):
    if x_api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if data.maintenance is not None:
        STATE["maintenance"] = data.maintenance
    if data.downloads_enabled is not None:
        STATE["downloads_enabled"] = data.downloads_enabled
    if data.notice is not None:
        STATE["notice"] = data.notice[:1000]
    return {"ok": True, **STATE}
