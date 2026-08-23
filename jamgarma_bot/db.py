import os
import sqlite3
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "jamgarma_bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'UZS',
            category TEXT,
            note TEXT,
            tx_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS savings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'UZS',
            note TEXT,
            tx_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    for table in ("transactions", "savings"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if "currency" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN currency TEXT NOT NULL DEFAULT 'UZS'")
    conn.commit()
    conn.close()


def add_transaction(user_id, ttype, amount, category, note, tx_date=None, currency="UZS"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO transactions (user_id, type, amount, currency, category, note, tx_date, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            user_id,
            ttype,
            amount,
            currency,
            category,
            note,
            tx_date or date.today().isoformat(),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def delete_transaction(user_id, tx_id):
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id))
    conn.commit()
    conn.close()


def add_savings(user_id, amount, note, tx_date=None, currency="UZS"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO savings (user_id, amount, currency, note, tx_date, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, amount, currency, note, tx_date or date.today().isoformat(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_balance(user_id, currency="UZS"):
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0) as bal "
        "FROM transactions WHERE user_id=? AND currency=?",
        (user_id, currency),
    ).fetchone()
    conn.close()
    return row["bal"]


def get_monthly_totals(user_id, currency="UZS"):
    month_key = date.today().strftime("%Y-%m")
    conn = get_conn()
    income = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM transactions "
        "WHERE user_id=? AND type='income' AND currency=? AND tx_date LIKE ?",
        (user_id, currency, f"{month_key}%"),
    ).fetchone()["s"]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM transactions "
        "WHERE user_id=? AND type='expense' AND currency=? AND tx_date LIKE ?",
        (user_id, currency, f"{month_key}%"),
    ).fetchone()["s"]
    conn.close()
    return income, expense


def get_savings_total(user_id, currency="UZS"):
    conn = get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) as s FROM savings WHERE user_id=? AND currency=?",
        (user_id, currency),
    ).fetchone()
    conn.close()
    return row["s"]


def get_savings_log(user_id, limit=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, amount, currency, note, tx_date FROM savings WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_transactions(user_id, limit=500):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, type, amount, currency, category, note, tx_date, created_at FROM transactions "
        "WHERE user_id=? ORDER BY tx_date DESC, created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
