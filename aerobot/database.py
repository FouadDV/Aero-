import asyncpg
import os
from datetime import datetime, timedelta


DB_URL = os.getenv("DATABASE_URL")


async def get_connection():
    return await asyncpg.connect(DB_URL)


async def init_db():
    conn = await get_connection()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                balance DECIMAL(18, 4) DEFAULT 0,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                last_daily TIMESTAMP,
                last_weekly TIMESTAMP,
                referral_code VARCHAR(20) UNIQUE,
                referred_by BIGINT,
                join_date TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                sender_id BIGINT,
                receiver_id BIGINT,
                amount DECIMAL(18, 4) NOT NULL,
                type VARCHAR(50) NOT NULL,
                description TEXT,
                confirmed BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id BIGINT PRIMARY KEY,
                reason TEXT,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key VARCHAR(50) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        defaults = [
            ("daily_reward", "5"),
            ("weekly_reward", "10"),
            ("referral_reward", "5"),
            ("tax_rate", "0"),
            ("aero_value", "0.018"),
        ]
        for key, value in defaults:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING
            """, key, value)

    finally:
        await conn.close()


async def get_user(user_id: int):
    conn = await get_connection()
    try:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None
    finally:
        await conn.close()


async def create_user(user_id: int, referral_code: str = None):
    conn = await get_connection()
    try:
        code = referral_code or f"AERO{user_id % 100000:05d}"
        await conn.execute("""
            INSERT INTO users (id, referral_code) VALUES ($1, $2)
            ON CONFLICT (id) DO NOTHING
        """, user_id, code)
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    finally:
        await conn.close()


async def ensure_user(user_id: int):
    user = await get_user(user_id)
    if not user:
        row = await create_user(user_id)
        return dict(row)
    return user


async def get_balance(user_id: int) -> float:
    user = await ensure_user(user_id)
    return float(user["balance"])


async def update_balance(user_id: int, amount: float, add_xp: int = 0):
    conn = await get_connection()
    try:
        await conn.execute("""
            UPDATE users SET balance = balance + $1, xp = xp + $2
            WHERE id = $3
        """, amount, add_xp, user_id)
    finally:
        await conn.close()


async def set_balance(user_id: int, amount: float):
    conn = await get_connection()
    try:
        await conn.execute("UPDATE users SET balance = $1 WHERE id = $2", amount, user_id)
    finally:
        await conn.close()


async def add_transaction(sender_id, receiver_id, amount: float, tx_type: str, description: str = ""):
    conn = await get_connection()
    try:
        await conn.execute("""
            INSERT INTO transactions (sender_id, receiver_id, amount, type, description)
            VALUES ($1, $2, $3, $4, $5)
        """, sender_id, receiver_id, amount, tx_type, description)
    finally:
        await conn.close()


async def get_transactions(user_id: int, limit: int = 10, offset: int = 0):
    conn = await get_connection()
    try:
        rows = await conn.fetch("""
            SELECT * FROM transactions
            WHERE sender_id = $1 OR receiver_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """, user_id, limit, offset)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def count_transactions(user_id: int):
    conn = await get_connection()
    try:
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM transactions
            WHERE sender_id = $1 OR receiver_id = $1
        """, user_id)
        return count
    finally:
        await conn.close()


async def is_blacklisted(user_id: int) -> bool:
    conn = await get_connection()
    try:
        row = await conn.fetchrow("SELECT 1 FROM blacklist WHERE user_id = $1", user_id)
        return row is not None
    finally:
        await conn.close()


async def add_blacklist(user_id: int, reason: str, added_by: int):
    conn = await get_connection()
    try:
        await conn.execute("""
            INSERT INTO blacklist (user_id, reason, added_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, reason, added_by)
    finally:
        await conn.close()


async def remove_blacklist(user_id: int):
    conn = await get_connection()
    try:
        await conn.execute("DELETE FROM blacklist WHERE user_id = $1", user_id)
    finally:
        await conn.close()


async def get_blacklist():
    conn = await get_connection()
    try:
        rows = await conn.fetch("SELECT * FROM blacklist ORDER BY added_at DESC")
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_setting(key: str) -> str:
    conn = await get_connection()
    try:
        val = await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)
        return val
    finally:
        await conn.close()


async def set_setting(key: str, value: str):
    conn = await get_connection()
    try:
        await conn.execute("""
            INSERT INTO settings (key, value, updated_at) VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """, key, value)
    finally:
        await conn.close()


async def get_leaderboard(limit: int = 10):
    conn = await get_connection()
    try:
        rows = await conn.fetch("""
            SELECT id, balance, level, xp FROM users
            ORDER BY balance DESC LIMIT $1
        """, limit)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_user_rank(user_id: int) -> int:
    conn = await get_connection()
    try:
        rank = await conn.fetchval("""
            SELECT COUNT(*) + 1 FROM users WHERE balance > (
                SELECT balance FROM users WHERE id = $1
            )
        """, user_id)
        return rank
    finally:
        await conn.close()


async def get_stats():
    conn = await get_connection()
    try:
        total = await conn.fetchval("SELECT COALESCE(SUM(balance), 0) FROM users")
        max_bal = await conn.fetchval("SELECT COALESCE(MAX(balance), 0) FROM users")
        min_bal = await conn.fetchval("SELECT COALESCE(MIN(balance), 0) FROM users WHERE balance > 0")
        avg_bal = await conn.fetchval("SELECT COALESCE(AVG(balance), 0) FROM users WHERE balance > 0")
        tx_count = await conn.fetchval("SELECT COUNT(*) FROM transactions")
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        return {
            "total_aero": float(total or 0),
            "max_balance": float(max_bal or 0),
            "min_balance": float(min_bal or 0),
            "avg_balance": float(avg_bal or 0),
            "tx_count": tx_count,
            "user_count": user_count,
        }
    finally:
        await conn.close()


async def update_last_daily(user_id: int):
    conn = await get_connection()
    try:
        await conn.execute("UPDATE users SET last_daily = NOW() WHERE id = $1", user_id)
    finally:
        await conn.close()


async def update_last_weekly(user_id: int):
    conn = await get_connection()
    try:
        await conn.execute("UPDATE users SET last_weekly = NOW() WHERE id = $1", user_id)
    finally:
        await conn.close()


async def check_level_up(user_id: int):
    conn = await get_connection()
    try:
        row = await conn.fetchrow("SELECT xp, level FROM users WHERE id = $1", user_id)
        if not row:
            return None
        xp = row["xp"]
        level = row["level"]
        xp_needed = 5 * (level ** 2)
        if xp >= xp_needed:
            new_level = level + 1
            reward = new_level * 2
            await conn.execute("""
                UPDATE users SET level = $1, xp = xp - $2, balance = balance + $3
                WHERE id = $4
            """, new_level, xp_needed, reward, user_id)
            return new_level, reward
        return None
    finally:
        await conn.close()


async def get_referral_by_code(code: str):
    conn = await get_connection()
    try:
        row = await conn.fetchrow("SELECT id FROM users WHERE referral_code = $1", code)
        return dict(row) if row else None
    finally:
        await conn.close()


async def set_referred_by(user_id: int, referrer_id: int):
    conn = await get_connection()
    try:
        await conn.execute("""
            UPDATE users SET referred_by = $1 WHERE id = $2 AND referred_by IS NULL
        """, referrer_id, user_id)
    finally:
        await conn.close()
