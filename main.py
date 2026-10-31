import os
import asyncio
import logging
import tempfile
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.request import HTTPXRequest
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
STATE = {"maintenance": False, "downloads_enabled": True, "notice": ""}

app = FastAPI(title="KMT FB DOWNLOAD API", version="1.2.0")

telegram_app: Optional[Application] = None


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == ADMIN_ID)


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("🛠 Maintenance ON/OFF", callback_data="maintenance"),
         InlineKeyboardButton("⬇️ Download ON/OFF", callback_data="downloads")],
        [InlineKeyboardButton("ℹ️ Current Notice", callback_data="notice")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None: return
    if not is_admin(update):
        await message.reply_text("⛔ ဒီ Bot ကို Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    await message.reply_text(
        "KMT FB DOWNLOAD Control Panel (Webhook Mode)\n\n/panel — Control Panel\n/status — Server/setting status\n"
        "/maintenance — Maintenance ဖွင့်/ပိတ်\n/download_on — Download ဖွင့်\n"
        "/download_off — Download ပိတ်\n/notice <စာသား> — ကြေညာချက်\n/notice_clear — ကြေညာချက်ဖျက်",
        reply_markup=keyboard())


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    await update.effective_message.reply_text("Admin Panel — လုပ်ဆောင်ချက်တစ်ခု ရွေးပါ။", reply_markup=keyboard())


def status_text():
    return ("🟢 API process is running (Webhook)\n"
            f"Maintenance: {'ON' if STATE['maintenance'] else 'OFF'}\n"
            f"Downloads: {'ON' if STATE['downloads_enabled'] else 'OFF'}\n"
            f"Notice: {STATE['notice'] or '(မရှိပါ)'}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    await update.effective_message.reply_text(status_text(), reply_markup=keyboard())


async def maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    STATE["maintenance"] = not STATE["maintenance"]
    await update.effective_message.reply_text(f"🛠 Maintenance {'ON' if STATE['maintenance'] else 'OFF'}", reply_markup=keyboard())


async def download_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    STATE["downloads_enabled"] = True
    await update.effective_message.reply_text("✅ Download function ON", reply_markup=keyboard())


async def download_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    STATE["downloads_enabled"] = False
    await update.effective_message.reply_text("⛔ Download function OFF", reply_markup=keyboard())


async def notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    msg = " ".join(context.args).strip()
    if not msg:
        await update.effective_message.reply_text("အသုံးပြုပုံ: /notice မင်္ဂလာပါ။ Server ပြုပြင်နေပါသည်။"); return
    STATE["notice"] = msg[:1000]
    await update.effective_message.reply_text("✅ Notice သိမ်းပြီးပါပြီ။", reply_markup=keyboard())


async def notice_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only."); return
    STATE["notice"] = ""
    await update.effective_message.reply_text("✅ Notice ဖျက်ပြီးပါပြီ။", reply_markup=keyboard())


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None: return
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        await query.answer("Admin only", show_alert=True); return
    await query.answer()
    if query.data == "status":
        await query.edit_message_text(status_text(), reply_markup=keyboard())
    elif query.data == "maintenance":
        STATE["maintenance"] = not STATE["maintenance"]
        await query.edit_message_text(f"🛠 Maintenance {'ON' if STATE['maintenance'] else 'OFF'}", reply_markup=keyboard())
    elif query.data == "downloads":
        STATE["downloads_enabled"] = not STATE["downloads_enabled"]
        await query.edit_message_text(f"Download {'ON' if STATE['downloads_enabled'] else 'OFF'}", reply_markup=keyboard())
    elif query.data == "notice":
        await query.edit_message_text(f"Current notice: {STATE['notice'] or '(မရှိပါ)'}", reply_markup=keyboard())


@app.on_event("startup")
async def startup_event():
    global telegram_app
    request = HTTPXRequest(connection_pool_size=8, connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30)
    telegram_app = Application.builder().token(BOT_TOKEN).request(request).build()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("panel", panel))
    telegram_app.add_handler(CommandHandler("status", status))
    telegram_app.add_handler(CommandHandler("maintenance", maintenance))
    telegram_app.add_handler(CommandHandler("download_on", download_on))
    telegram_app.add_handler(CommandHandler("download_off", download_off))
    telegram_app.add_handler(CommandHandler("notice", notice))
    telegram_app.add_handler(CommandHandler("notice_clear", notice_clear))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))

    await telegram_app.initialize()
    await telegram_app.start()
    log.info("Telegram application initialized for webhook")


@app.on_event("shutdown")
async def shutdown_event():
    global telegram_app
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()
        log.info("Telegram application shut down")


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    if telegram_app is None:
        raise HTTPException(status_code=500, detail="Telegram app not initialized")
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.get("/")
def root():
    return {"service": "KMT FB DOWNLOAD API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def public_config():
    return {"maintenance": STATE["maintenance"], "downloads_enabled": STATE["downloads_enabled"], "notice": STATE["notice"]}


class DownloadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    quality: str = Field(default="sd")  # "sd" သို့မဟုတ် "hd"


def validate_facebook_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = host == "facebook.com" or host.endswith(".facebook.com") or host == "fb.watch" or host.endswith(".fb.watch")
    if parsed.scheme not in ("http", "https") or not allowed:
        raise HTTPException(status_code=400, detail="Facebook သို့မဟုတ် fb.watch link ကိုသာ ထည့်ပါ။")
    return url.strip()


def download_with_ytdlp(url: str, quality: str, output_path: str):
    # quality အလိုက် yt-dlp format သတ်မှတ်ခြင်း (ffmpeg ဖြင့် အသံနှင့်ရုပ် ပေါင်းပြီးသား mp4 ထွက်လာမည်)
    if quality == "hd":
        fmt = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    else:
        fmt = "bestvideo[height<=480]+bestaudio/best[height<=480]"

    ydl_opts = {
        "format": fmt,
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


@app.post("/download-file")
async def download_video_file(data: DownloadRequest, background_tasks: BackgroundTasks):
    if STATE["maintenance"]: 
        raise HTTPException(status_code=503, detail="Service maintenance လုပ်နေပါသည်။")
    if not STATE["downloads_enabled"]: 
        raise HTTPException(status_code=403, detail="Download လုပ်ဆောင်ချက်ကို Admin က ပိတ်ထားပါသည်။")
    
    url = validate_facebook_url(data.url)
    
    # ယာယီဖိုင် ဖန်တီးခြင်း
    temp_dir = tempfile.gettempdir()
    file_id = os.path.join(temp_dir, f"fb_{os.urandom(8).hex()}.mp4")
    
    try:
        # Background သို့မဟုတ် thread ထဲတွင် ffmpeg ဖြင့် ချက်ချင်း Download လုပ်ပြီး ပေါင်းစပ်မည်
        await asyncio.wait_for(
            asyncio.to_thread(download_with_ytdlp, url, data.quality, file_id),
            timeout=120
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="ဗီဒီယို ဒေါင်းလုပ်ဆွဲချိန် ကုန်သွားပါပြီ။")
    except Exception as exc:
        log.warning("Download failed: %s", exc)
        raise HTTPException(status_code=422, detail="ဒီဗီဒီယိုကို ဒေါင်းလုပ်ဆွဲ၍ မရပါ။ Public link ဖြစ်မဖြစ် စစ်ပါ။")
    
    if not os.path.exists(file_id):
        raise HTTPException(status_code=422, detail="ဗီဒီယိုဖိုင် ထုတ်ယူ၍မရပါ။")

    # ဖိုင်ပို့ပြီးပါက ယာယီဖိုင်ကို ဖျက်ရန်
    background_tasks.add_task(os.remove, file_id)
    
    return FileResponse(file_id, media_type="video/mp4", filename=f"facebook_{data.quality}.mp4")
