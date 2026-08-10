# 🚀 Telegram View SMM Panel Bot

A powerful, modern, aesthetic Telegram Bot to sell Telegram post views using any standard SMM Panel API v2.

---

## ✨ Features

### 👤 User Keyboard Menu
- **👁️ Order View**: Multi-step interactive order wizard (Link input -> Quantity input -> Live Points Cost preview -> Order Confirmation -> SMM Panel API execution).
- **👤 My Account**: Overview of User ID, Balance, Total Orders, Referral count, Personal Referral Link, and **Order History**.
- **👥 Refer & Earn**: Earn points per referral with unique share links (`t.me/bot?start=REF_ID`).
- **💳 Top Up**: Display Admin UPI ID / payment details, user enters INR amount & payment UTR. Admin gets real-time Telegram notification with **[✅ Approve]** & **[❌ Reject]** buttons.
- **🎟️ Redeem Code**: Instant promo code redemption system for free points.
- **ℹ️ Help / Support**: FAQ, rate details, and support info.

### 👑 Admin Panel & Features (`/admin`)
- 📊 **Bot & SMM Statistics**: View total users, total points, total orders, approved topups, and live SMM Panel balance.
- 🚫 **Ban / Unban User**: Restrict abusive users (`/ban <user_id>`, `/unban <user_id>`).
- 💰 **Add / Remove Points**: Instantly credit/debit user balance (`/addpoints <user_id> <amount>`, `/removepoints`).
- 🎟️ **Generate Redeem Code**: Create promo codes with custom point rewards & usage limits (`/gencode <code> <points> <max_uses>`).
- 📢 **Broadcast Message**: Broadcast HTML messages to all registered bot users (`/broadcast <message>`).
- ⚙️ **Dynamic Settings**: Modify SMM URL, API Key, Service ID, Rate per 1000 views, or UPI ID directly on the fly (`/set key value`).

---

## 🚀 Quick Setup & Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
Edit `.env` file with your details:
```env
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=123456789
SMM_API_URL=https://your-smm-panel.com/api/v2
SMM_API_KEY=your_smm_api_key
SMM_SERVICE_ID=1
PRICE_PER_1000=10.0
REFERRAL_REWARD=5.0
UPI_ID=yourname@upi
```

### 3. Run the Bot
```bash
python bot.py
```

---

## 🛠️ Code Architecture
- `config.py` - Environment configuration & default values.
- `database.py` - SQLite Database wrapper for user records, orders, promo codes, top-ups & settings.
- `smm_api.py` - Async client for SMM Panel API v2 (`action=add`, `action=balance`, `action=status`).
- `bot.py` - Telegram Bot main logic, handlers, keyboards, UI modals & Admin control panel.
