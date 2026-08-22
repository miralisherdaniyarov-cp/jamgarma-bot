import hashlib
import hmac
import json
import os
import urllib.parse
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

import db

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
WEBHOOK_PATH = "/webhook"

CATEGORIES = {
    "ovqat": ("Ovqat", "🍲"),
    "transport": ("Transport", "🚌"),
    "kiyim": ("Kiyim", "👕"),
    "kongilochar": ("Ko'ngilochar", "🎬"),
    "kommunal": ("Kommunal", "💡"),
    "sogliq": ("Sog'liq", "💊"),
    "talim": ("Ta'lim", "📚"),
    "boshqa": ("Boshqa", "🗂️"),
}

app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()


# ---------- Telegram bot: /start ochadigan Mini App tugmasi ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if PUBLIC_URL:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Ilovani ochish", web_app=WebAppInfo(url=PUBLIC_URL))]]
        )
        await update.message.reply_text("Xarajat va jamg'arma ilovangiz tayyor 👇", reply_markup=kb)
    else:
        await update.message.reply_text("Ilova hali sozlanmagan (PUBLIC_URL yo'q).")


application.add_handler(CommandHandler("start", start_cmd))


@app.on_event("startup")
async def on_startup():
    db.init_db()
    await application.initialize()
    if PUBLIC_URL and BOT_TOKEN:
        await application.bot.set_webhook(url=PUBLIC_URL + WEBHOOK_PATH)


@app.on_event("shutdown")
async def on_shutdown():
    await application.shutdown()


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}


# ---------- Telegram Mini App initData tekshiruvi ----------
def verify_init_data(init_data: str) -> Optional[dict]:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if computed_hash != received_hash:
            return None
        user_json = parsed.get("user")
        if not user_json:
            return None
        return json.loads(user_json)
    except Exception:
        return None


def get_user_id(x_init_data: Optional[str]) -> int:
    if not x_init_data:
        raise HTTPException(401, "initData yo'q")
    user = verify_init_data(x_init_data)
    if not user:
        raise HTTPException(401, "Tekshiruv muvaffaqiyatsiz")
    return user["id"]


# ---------- Mini App REST API ----------
class TxIn(BaseModel):
    type: str
    amount: int
    category: Optional[str] = None
    date: str


class SavingsIn(BaseModel):
    amount: int
    note: Optional[str] = None


@app.get("/api/categories")
def api_categories():
    return {"categories": [{"id": k, "label": v[0], "emoji": v[1]} for k, v in CATEGORIES.items()]}


@app.get("/api/summary")
def api_summary(x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    income, expense = db.get_monthly_totals(uid)
    return {
        "balance": db.get_balance(uid),
        "monthlyIncome": income,
        "monthlyExpense": expense,
        "savings": db.get_savings_total(uid),
        "transactions": db.get_all_transactions(uid),
    }


@app.post("/api/tx")
def api_add_tx(tx: TxIn, x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    if tx.amount <= 0:
        raise HTTPException(400, "Summa musbat bo'lishi kerak")
    if tx.type not in ("income", "expense"):
        raise HTTPException(400, "Noto'g'ri tur")
    if tx.type == "expense" and tx.category not in CATEGORIES:
        raise HTTPException(400, "Noto'g'ri kategoriya")
    db.add_transaction(uid, tx.type, tx.amount, tx.category if tx.type == "expense" else None, None, tx.date)
    return {"ok": True}


@app.delete("/api/tx/{tx_id}")
def api_delete_tx(tx_id: int, x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    db.delete_transaction(uid, tx_id)
    return {"ok": True}


@app.get("/api/savings")
def api_savings(x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    return {"total": db.get_savings_total(uid), "log": db.get_savings_log(uid)}


@app.post("/api/savings")
def api_add_savings(s: SavingsIn, x_init_data: Optional[str] = Header(None)):
    uid = get_user_id(x_init_data)
    if s.amount == 0:
        raise HTTPException(400, "Summa 0 bo'lmasligi kerak")
    db.add_savings(uid, s.amount, s.note)
    return {"ok": True}


# ---------- Mini App frontend (static/index.html) ----------
app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
