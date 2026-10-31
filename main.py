import os
import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request
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

app = FastAPI(title="KMT FB DOWNLOAD API", version="1.1.0")

# Telegram Application instance ကို Global အနေဖြင့် သိမ်းဆည်းမည်
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


# ==========================================
# TELEGRAM WEBHOOK ENDPOINT
# ==========================================
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
    return {"service": "KMT FB DOWNLOAD API", "status": "ok", "health": "/health", "download_endpoint": "/download"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def public_config():
    return {"maintenance": STATE["maintenance"], "downloads_enabled": STATE["downloads_enabled"], "notice": STATE["notice"]}


class DownloadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


def validate_facebook_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = host == "facebook.com" or host.endswith(".facebook.com") or host == "fb.watch" or host.endswith(".fb.watch")
    if parsed.scheme not in ("http", "https") or not allowed:
        raise HTTPException(status_code=400, detail="Facebook သို့မဟုတ် fb.watch link ကိုသာ ထည့်ပါ။")
    return url.strip()


def extract_video(url: str):
    opts = {
        "quiet": True, 
        "no_warnings": True, 
        "skip_download": True, 
        "noplaylist": True,
        "socket_timeout": 20, 
        "retries": 1, 
        "extractor_retries": 1, 
        "format": "best[height<=480]/best"
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    if not info: 
        raise ValueError("No video info")
        
    formats = info.get("formats") or []
    
    # အသံပါပြီးသား (Muxed) format တွေကို အဓိကရှာပါ
    muxed_formats = [f for f in formats if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") not in (None, "none")]
    
    if not muxed_formats:
        muxed_formats = [f for f in formats if f.get("url") and f.get("vcodec"] != "none"]
        
    if info.get("url") and info.get("vcodec") != "none":
        muxed_formats.append(info)

    def get_best_by_height(max_h=None, min_h=None):
        filtered = muxed_formats
        if max_h is not None:
            filtered = [f for f in filtered if (f.get("height") or 0) <= max_h]
        if min_h is not None:
            filtered = [f for f in filtered if (f.get("height") or 0) >= min_h]
            
        if not filtered:
            return None
            
        return max(filtered, key=lambda x: (
            1 if x.get("acodec") not in (None, "none") else 0,
            x.get("height") or 0,
            x.get("tbr") or 0
        ))

    sd = get_best_by_height(max_h=480) or get_best_by_height()
    hd = get_best_by_height(min_h=720) or get_best_by_height()
    
    return {
        "title": info.get("title") or "Facebook video", 
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"), 
        "sd_url": sd.get("url") if sd else None,
        "hd_url": hd.get("url") if hd else None,
        "note": "Download URL များသည် ယာယီဖြစ်နိုင်ပြီး သက်တမ်းကုန်ပါက link အသစ်ပြန်ထုတ်ပါ။"
    }


@app.post("/download")
async def download_video(data: DownloadRequest):
    if STATE["maintenance"]: raise HTTPException(status_code=503, detail="Service maintenance လုပ်နေပါသည်။")
    if not STATE["downloads_enabled"]: raise HTTPException(status_code=403, detail="Download လုပ်ဆောင်ချက်ကို Admin က ပိတ်ထားပါသည်။")
    url = validate_facebook_url(data.url)
    try:
        result = await asyncio.wait_for(asyncio.to_thread(extract_video, url), timeout=50)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Video စစ်ဆေးချိန်ကုန်သွားပါပြီ။ နောက်တစ်ကြိမ် စမ်းပါ။")
    except Exception as exc:
        log.warning("Video extraction failed: %s", exc)
        raise HTTPException(status_code=422, detail="ဒီ video ကို မရယူနိုင်ပါ။ Public video link ဖြစ်ကြောင်း စစ်ပြီး ပြန်စမ်းပါ။")
    if not result.get("sd_url") and not result.get("hd_url"):
        raise HTTPException(status_code=422, detail="ဒီ video အတွက် တိုက်ရိုက် download link မရရှိပါ။")
    return {"ok": True, **result}


class SettingsUpdate(BaseModel):
    maintenance: Optional[bool] = None
    downloads_enabled: Optional[bool] = None
    notice: Optional[str] = None


@app.post("/admin/settings")
def update_settings(data: SettingsUpdate, x_api_key: str = Header(default="")):
    if x_api_key != APP_API_KEY: raise HTTPException(status_code=401, detail="Unauthorized")
    if data.maintenance is not None: STATE["maintenance"] = data.maintenance
    if data.downloads_enabled is not None: STATE["downloads_enabled"] = data.downloads_enabled
    if data.notice is not None: STATE["notice"] = data.notice[:1000]
    return {"ok": True, **STATE}
