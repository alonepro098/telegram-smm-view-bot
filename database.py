import sqlite3
import datetime
from typing import Optional, Dict, Any, List, Tuple
import config

class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance REAL DEFAULT 0.0,
                    referrer_id INTEGER,
                    total_orders INTEGER DEFAULT 0,
                    is_banned INTEGER DEFAULT 0,
                    last_bonus TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            try:
                cursor.execute("ALTER TABLE users ADD COLUMN last_bonus TEXT")
            except sqlite3.OperationalError:
                pass

            # Orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    smm_order_id INTEGER,
                    post_link TEXT,
                    quantity INTEGER,
                    cost REAL,
                    status TEXT DEFAULT 'Pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)

            # Redeem codes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS redeem_codes (
                    code TEXT PRIMARY KEY,
                    points REAL,
                    max_uses INTEGER,
                    used_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Code usage history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS used_codes (
                    code TEXT,
                    user_id INTEGER,
                    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(code, user_id)
                )
            """)

            # Top-up requests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topup_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount_inr REAL,
                    points REAL,
                    utr TEXT,
                    photo_id TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            try:
                cursor.execute("ALTER TABLE topup_requests ADD COLUMN photo_id TEXT")
            except sqlite3.OperationalError:
                pass

            # Key-Value Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            conn.commit()
            self._insert_default_settings(cursor, conn)

    def _insert_default_settings(self, cursor: sqlite3.Cursor, conn: sqlite3.Connection):
        defaults = {
            "smm_api_url": config.DEFAULT_SMM_API_URL,
            "smm_api_key": config.DEFAULT_SMM_API_KEY,
            "smm_service_id": str(config.DEFAULT_SMM_SERVICE_ID),
            "price_per_1000": str(config.DEFAULT_PRICE_PER_1000),
            "referral_reward": str(config.DEFAULT_REFERRAL_REWARD),
            "min_order_qty": str(config.DEFAULT_MIN_ORDER_QTY),
            "max_order_qty": str(config.DEFAULT_MAX_ORDER_QTY),
            "upi_id": config.DEFAULT_UPI_ID,
            "upi_name": config.DEFAULT_UPI_NAME,
            "inr_per_point": str(config.DEFAULT_INR_PER_POINT),
        }
        for key, val in defaults.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
        conn.commit()

    # --- Setting Operations ---
    def get_setting(self, key: str, default: Any = "") -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else str(default)

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    # --- User Operations ---
    def get_or_create_user(self, user_id: INTEGER, username: Optional[str] = None, first_name: Optional[str] = None, referrer_id: Optional[int] = None) -> Tuple[sqlite3.Row, bool]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            is_new = False
            
            if not user:
                is_new = True
                # Clean self-referral
                if referrer_id == user_id:
                    referrer_id = None
                
                # Check if valid referrer exists
                if referrer_id:
                    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
                    if not cursor.fetchone():
                        referrer_id = None

                cursor.execute(
                    "INSERT INTO users (user_id, username, first_name, referrer_id) VALUES (?, ?, ?, ?)",
                    (user_id, username, first_name, referrer_id)
                )
                
                # Award referral reward if valid
                if referrer_id:
                    ref_reward = float(self.get_setting("referral_reward", config.DEFAULT_REFERRAL_REWARD))
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (ref_reward, referrer_id))

                conn.commit()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()
            else:
                # Update info if changed
                if username != user["username"] or first_name != user["first_name"]:
                    cursor.execute("UPDATE users SET username = ?, first_name = ? WHERE user_id = ?", (username, first_name, user_id))
                    conn.commit()
                    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                    user = cursor.fetchone()

            return user, is_new

    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return cursor.fetchone()

    def update_balance(self, user_id: int, amount: float) -> float:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return row["balance"] if row else 0.0

    def set_user_ban(self, user_id: int, banned: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if banned else 0, user_id))
            conn.commit()

    def get_referral_count(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE referrer_id = ?", (user_id,))
            return cursor.fetchone()["cnt"]

    # --- Order Operations ---
    def add_order(self, user_id: int, smm_order_id: int, post_link: str, quantity: int, cost: float) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (user_id, smm_order_id, post_link, quantity, cost, status) VALUES (?, ?, ?, ?, ?, 'Success')",
                (user_id, smm_order_id, post_link, quantity, cost)
            )
            cursor.execute("UPDATE users SET total_orders = total_orders + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.lastrowid

    def get_user_orders(self, user_id: int, limit: int = 10) -> List[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
            return cursor.fetchall()

    def get_order_by_id(self, order_id: int) -> Optional[sqlite3.Row]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ? OR smm_order_id = ?", (order_id, order_id))
            return cursor.fetchone()

    # --- Redeem Code Operations ---
    def create_redeem_code(self, code: str, points: float, max_uses: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO redeem_codes (code, points, max_uses) VALUES (?, ?, ?)",
                    (code.upper(), points, max_uses)
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def redeem_code(self, user_id: int, code: str) -> Tuple[bool, str, float]:
        code = code.upper().strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM redeem_codes WHERE code = ?", (code,))
            rc = cursor.fetchone()
            if not rc:
                return False, "❌ Invalid redeem code!", 0.0
            
            if rc["used_count"] >= rc["max_uses"]:
                return False, "❌ This redeem code has reached its maximum usage limit!", 0.0

            cursor.execute("SELECT * FROM used_codes WHERE code = ? AND user_id = ?", (code, user_id))
            if cursor.fetchone():
                return False, "⚠️ You have already redeemed this code!", 0.0

            # Apply code
            cursor.execute("INSERT INTO used_codes (code, user_id) VALUES (?, ?)", (code, user_id))
            cursor.execute("UPDATE redeem_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (rc["points"], user_id))
            conn.commit()

            return True, f"🎉 Redeem successful! You received <b>+{config.clean_num(rc['points'])} Points</b>.", rc["points"]

    # --- Daily Bonus Operations ---
    def claim_daily_bonus(self, user_id: int) -> Tuple[bool, str, int]:
        today_str = datetime.date.today().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row and row["last_bonus"] == today_str:
                return False, "⚠️ <b>You have already claimed your daily bonus today!</b>\nCome back tomorrow for another bonus.", 0

            import random
            bonus_amount = random.randint(100, 150)
            cursor.execute("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?", (bonus_amount, today_str, user_id))
            conn.commit()

            return True, f"🎁 <b>DAILY BONUS CLAIMED!</b>\n━━━━━━━━━━━━━━━━━━━━\nYou received <b>+{bonus_amount} Points!</b>\n\nCome back tomorrow for more free points!", bonus_amount

    # --- TopUp Request Operations ---
    def create_topup_request(self, user_id: int, amount_inr: float, points: float, utr: str, photo_id: Optional[str] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO topup_requests (user_id, amount_inr, points, utr, photo_id) VALUES (?, ?, ?, ?, ?)",
                (user_id, amount_inr, points, utr, photo_id)
            )
            conn.commit()
            return cursor.lastrowid

    def process_topup_request(self, request_id: int, approve: bool) -> Tuple[bool, Optional[sqlite3.Row]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topup_requests WHERE id = ?", (request_id,))
            req = cursor.fetchone()
            if not req or req["status"] != "PENDING":
                return False, None
            
            new_status = "APPROVED" if approve else "REJECTED"
            cursor.execute("UPDATE topup_requests SET status = ? WHERE id = ?", (new_status, request_id))
            
            if approve:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (req["points"], req["user_id"]))

            conn.commit()
            return True, req

    # --- Admin Statistics ---
    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_users, SUM(balance) as total_balance FROM users")
            u_row = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*) as total_orders, SUM(cost) as total_spent FROM orders")
            o_row = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) as total_topups, SUM(amount_inr) as total_inr FROM topup_requests WHERE status = 'APPROVED'")
            t_row = cursor.fetchone()

            return {
                "total_users": u_row["total_users"] or 0,
                "total_balance": round(u_row["total_balance"] or 0.0, 2),
                "total_orders": o_row["total_orders"] or 0,
                "total_spent": round(o_row["total_spent"] or 0.0, 2),
                "approved_inr": round(t_row["total_inr"] or 0.0, 2)
            }

    def get_all_user_ids(self) -> List[int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
            return [row["user_id"] for row in cursor.fetchall()]
