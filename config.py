import os
from dotenv import load_dotenv

load_dotenv()

def clean_num(val) -> str:
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return f"{f:.2f}".rstrip('0').rstrip('.')
    except Exception:
        return str(val)

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip().isdigit()]

# Default SMM Panel Configuration (Can also be managed via Admin command / DB)
DEFAULT_SMM_API_URL = os.getenv("SMM_API_URL", "https://smm-panel-domain.com/api/v2")
DEFAULT_SMM_API_KEY = os.getenv("SMM_API_KEY", "YOUR_SMM_API_KEY")
DEFAULT_SMM_SERVICE_ID = int(os.getenv("SMM_SERVICE_ID", "1")) # Service ID for Telegram Views

# Bot Economy Settings
DEFAULT_PRICE_PER_1000 = float(os.getenv("PRICE_PER_1000", "1000")) # 1000 Points per 1000 views (1 View = 1 Point)
DEFAULT_REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "5")) # 5 Points per referral
DEFAULT_MIN_ORDER_QTY = int(os.getenv("MIN_ORDER_QTY", "100")) # Min 100 views
DEFAULT_MAX_ORDER_QTY = int(os.getenv("MAX_ORDER_QTY", "100000")) # Max 100k views
DEFAULT_UPI_ID = os.getenv("UPI_ID", "admin@upi")
DEFAULT_UPI_NAME = os.getenv("UPI_NAME", "Admin View Store")
DEFAULT_INR_PER_POINT = float(os.getenv("INR_PER_POINT", "0.10")) # ₹1 = 10 points (0.10 INR per point)

# Database File Path
DB_PATH = os.getenv("DB_PATH", "bot.db")
