# KMT FB DOWNLOAD — Telegram Control API (Starter)

ဒီ Project က Telegram Bot ကနေ API setting အချို့ကို ထိန်းချုပ်ဖို့ starter scaffold ဖြစ်ပါတယ်။

## လက်ရှိပါဝင်တာ
- Telegram Admin-only Bot commands
- `/panel`, `/status`
- `/maintenance` (ON/OFF toggle)
- `/download_on`, `/download_off`
- `/notice <စာသား>`, `/notice_clear`
- `GET /health`
- `GET /config` — App က remote settings ဖတ်ရန်
- `POST /admin/settings` — `X-API-Key` ဖြင့် settings update

## အရေးကြီးတဲ့ ကန့်သတ်ချက်
**ဒီ starter က Facebook video downloader engine မပါသေးပါ။** အရင်ဆုံး Bot + remote control API ကို တည်ဆောက်ထားတာပါ။
Settings တွေကို လက်ရှိ RAM ထဲမှာပဲ သိမ်းထားလို့ Render restart/redeploy ဖြစ်ရင် default ပြန်ဖြစ်မယ်။ ရေရှည်အသုံးပြုဖို့ persistent database/storage ထည့်ရပါမယ်။
Render Free ကို keep-alive ping လုပ်တာက sleep policy ကို အမြဲကျော်လွှားနိုင်မယ်လို့ အာမမခံနိုင်ပါ။

## Render တင်နည်း (ဖုန်း Browser နဲ့)
1. GitHub မှာ repository အသစ်ဖန်တီးပါ။
2. ဒီ ZIP ထဲက ဖိုင်တွေကို extract လုပ်ပြီး repository root ထဲ upload လုပ်ပါ။
3. Render Dashboard → New → Blueprint (သို့) Web Service ကိုရွေးပါ။
4. `render.yaml` ကိုအသုံးပြုမယ်ဆိုရင် Blueprint deploy လုပ်ပါ။ Manual Web Service ဆိုရင် Build Command `pip install -r requirements.txt`, Start Command `uvicorn main:app --host 0.0.0.0 --port $PORT` ထည့်ပါ။
5. Environment Variables ထဲမှာ အောက်ပါ ၃ ခု ထည့်ပါ။
   - `BOT_TOKEN` = BotFather ကပေးတဲ့ token
   - `ADMIN_ID` = မင်းရဲ့ numeric Telegram user ID
   - `APP_API_KEY` = ရှည်လျားပြီး ခန့်မှန်းရခက်တဲ့ secret string
6. Deploy ပြီး `/health` ကိုဖွင့်ပြီး `{"status":"ok"}` ပြန်လာမလာ စစ်ပါ။
7. Telegram Bot ကိုဖွင့်ပြီး `/start` သို့မဟုတ် `/panel` ပို့ပါ။

## လုံခြုံရေး
- Bot token ကို GitHub code ထဲမထည့်ပါနဲ့။
- `APP_API_KEY` ကို App ထဲမှာ hardcode မလုပ်ပါနဲ့။ Public app ထဲထည့်ထားရင် ထုတ်ယူနိုင်ပါတယ်။
- Telegram bot admin restriction က `ADMIN_ID` ကို စစ်ဆေးပါတယ်။
- `/config` public endpoint မှာ maintenance/download flags/notice သာပါဝင်ပါတယ်။

## Render Free keep-alive
External uptime monitor-оор `/health` ping хийж болох ч Render-ийн free sleep policy-г тойрч гарах баталгаа биш. Monitoring нь uptime шалгахад зориулагдсан байх ёстой.
