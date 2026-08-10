import logging
import asyncio
from typing import Dict, Any, Optional
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

import config
from config import clean_num
from database import Database
from smm_api import SMMPanelClient

# Enable Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize DB
db = Database()

# Conversation States
(
    STATE_ORDER_LINK,
    STATE_ORDER_QTY,
    STATE_ORDER_CONFIRM,
    STATE_ORDER_STATUS_ID,
    STATE_TOPUP_SELECT_PKG,
    STATE_TOPUP_PROOF,
    STATE_REDEEM_CODE,
    STATE_BROADCAST,
    STATE_GENCODE,
) = range(9)

# Predefined TopUp Packages
TOPUP_PACKAGES = [
    {"pts": 1000, "inr": 5},
    {"pts": 5000, "inr": 25},
    {"pts": 10000, "inr": 50},
    {"pts": 50000, "inr": 250},
    {"pts": 100000, "inr": 500},
]

# Keyboards
def get_main_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("👁️ Order View"), KeyboardButton("🔎 Order Status")],
        [KeyboardButton("👤 My Account"), KeyboardButton("🎁 Bonus")],
        [KeyboardButton("👥 Refer & Earn"), KeyboardButton("🎟️ Redeem Code")],
        [KeyboardButton("💳 Top Up"), KeyboardButton("ℹ️ Help / Support")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Bot & SMM Stats", callback_data="admin_stats"),
            InlineKeyboardButton("💳 Check SMM Balance", callback_data="admin_smm_bal")
        ],
        [
            InlineKeyboardButton("➕ Add Points", callback_data="admin_add_pts"),
            InlineKeyboardButton("➖ Remove Points", callback_data="admin_rem_pts")
        ],
        [
            InlineKeyboardButton("🎟️ Create Promo Code", callback_data="admin_gen_code"),
            InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("⚙️ SMM Settings", callback_data="admin_settings"),
            InlineKeyboardButton("🚫 Ban/Unban User", callback_data="admin_ban_menu")
        ]
    ])

# Helper Function: Check Admin
def is_user_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

# --- START COMMAND ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Check for referral parameter in /start REF_ID
    referrer_id = None
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])

    db_user, is_new = db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        referrer_id=referrer_id
    )

    if db_user["is_banned"]:
        await update.message.reply_text("❌ <b>You are banned from using this bot.</b>", parse_mode="HTML")
        return

    admin_flag = is_user_admin(user.id)
    welcome_msg = (
        f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
        f"🚀 <b>Telegram View Order Bot</b>\n"
        f"Get high quality instant views on your Telegram posts using SMM Panel.\n\n"
        f"💰 <b>Your Current Balance:</b> <code>{clean_num(db_user['balance'])} Points</code>\n"
        f"🆔 <b>Your User ID:</b> <code>{user.id}</code>\n\n"
        f"👇 Use the menu below to place orders or manage your account."
    )

    if is_new and referrer_id and referrer_id != user.id:
        try:
            ref_reward = db.get_setting("referral_reward", config.DEFAULT_REFERRAL_REWARD)
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 <b>New Referral Joined!</b>\nUser {user.first_name} joined using your link.\nYou earned <b>+{clean_num(ref_reward)} Points!</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await update.message.reply_text(welcome_msg, parse_mode="HTML", reply_markup=get_main_keyboard(admin_flag))

# --- MY ACCOUNT ---
async def my_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user, _ = db.get_or_create_user(user.id, user.username, user.first_name)

    if db_user["is_banned"]:
        return

    ref_count = db.get_referral_count(user.id)
    bot_obj = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_obj.username}?start={user.id}"

    account_msg = (
        f"👤 <b>ACCOUNT SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"👤 <b>Name:</b> {user.first_name}\n"
        f"🏷️ <b>Username:</b> @{user.username if user.username else 'N/A'}\n\n"
        f"💎 <b>Points Balance:</b> <code>{clean_num(db_user['balance'])} Points</code>\n"
        f"👥 <b>Total Referrals:</b> <code>{ref_count}</code>\n\n"
        f"🔗 <b>Your Referral Link:</b>\n<code>{ref_link}</code>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📜 View Order History", callback_data="user_order_history")],
        [InlineKeyboardButton("💳 Top Up Points", callback_data="start_topup_flow")]
    ])

    await update.message.reply_text(account_msg, parse_mode="HTML", reply_markup=keyboard)

# --- REFER & EARN ---
async def refer_earn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_obj = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_obj.username}?start={user.id}"
    ref_count = db.get_referral_count(user.id)
    ref_reward = db.get_setting("referral_reward", config.DEFAULT_REFERRAL_REWARD)

    refer_msg = (
        f"👥 <b>REFER & EARN PROGRAM</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Earn free points for every friend you invite!\n\n"
        f"🎁 <b>Reward per Refer:</b> <code>+{clean_num(ref_reward)} Points</code>\n"
        f"📊 <b>Your Total Referrals:</b> <code>{ref_count} Users</code>\n\n"
        f"👇 <b>Share your link:</b>\n<code>{ref_link}</code>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={ref_link}&text=Get%20instant%20Telegram%20views!")]
    ])

    await update.message.reply_text(refer_msg, parse_mode="HTML", reply_markup=keyboard)

# --- DAILY BONUS ---
async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ok, msg, pts = db.claim_daily_bonus(user_id)
    await update.message.reply_text(msg, parse_mode="HTML")

# --- HELP / SUPPORT ---
async def help_support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upi_id = db.get_setting("upi_id", config.DEFAULT_UPI_ID)
    rate = db.get_setting("price_per_1000", config.DEFAULT_PRICE_PER_1000)
    help_msg = (
        f"ℹ️ <b>BOT HELP & SUPPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Service:</b> Telegram Post Views\n"
        f"💰 <b>Current Rate:</b> 1 View = 1 Point (<code>{clean_num(rate)} Points</code> per 1,000 views)\n"
        f"💳 <b>Payment UPI:</b> <code>{upi_id}</code>\n\n"
        f"❓ <b>How to place order?</b>\n"
        f"1. Click on 👁️ <b>Order View</b>\n"
        f"2. Send your Telegram post URL (e.g. <code>https://t.me/channel/123</code>)\n"
        f"3. Enter required views quantity (e.g. 1000)\n"
        f"4. Confirm and instant delivery starts!\n\n"
        f"❓ <b>How to check order status?</b>\n"
        f"Click on 🔎 <b>Order Status</b> and send your Order ID!\n\n"
        f"📩 Contact admin if you have any questions."
    )
    await update.message.reply_text(help_msg, parse_mode="HTML")

# --- ORDER HISTORY CALLBACK ---
async def order_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    orders = db.get_user_orders(user_id, limit=5)

    if not orders:
        await query.message.reply_text("📜 <b>No orders found yet!</b>", parse_mode="HTML")
        return

    msg = "📜 <b>YOUR RECENT ORDERS:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for ord in orders:
        msg += (
            f"🆔 <b>Order ID:</b> <code>#{ord['id']}</code> | SMM Ref: #{ord['smm_order_id']}\n"
            f"🔗 <b>Link:</b> <code>{ord['post_link'][:35]}...</code>\n"
            f"👁️ <b>Qty:</b> {ord['quantity']} views | 💵 <b>Cost:</b> {clean_num(ord['cost'])} Pts\n"
            f"📅 <b>Date:</b> {ord['created_at']}\n"
            f"------------------------------------\n"
        )
    await query.message.reply_text(msg, parse_mode="HTML")


# ==========================================
# ORDER VIEW CONVERSATION FLOW
# ==========================================

async def order_view_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = db.get_user(user.id)

    if db_user and db_user["is_banned"]:
        await update.message.reply_text("❌ You are banned from placing orders.")
        return ConversationHandler.END

    price_per_1000 = float(db.get_setting("price_per_1000", config.DEFAULT_PRICE_PER_1000))

    await update.message.reply_text(
        f"👁️ <b>TELEGRAM VIEW ORDER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Price Rate:</b> 1 View = 1 Point (<code>{clean_num(price_per_1000)} Points</code> per 1,000 views)\n"
        f"💳 <b>Your Balance:</b> <code>{clean_num(db_user['balance'])} Points</code>\n\n"
        f"👉 <b>Please send your Telegram Post URL:</b>\n"
        f"<i>Example: https://t.me/your_channel/123</i>\n\n"
        f"<i>Type /cancel to cancel anytime.</i>",
        parse_mode="HTML"
    )
    return STATE_ORDER_LINK

async def order_view_get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/cancel"):
        await update.message.reply_text("❌ Order cancelled.")
        return ConversationHandler.END

    if not ("t.me/" in text or "telegram.me/" in text):
        await update.message.reply_text("⚠️ <b>Invalid link format!</b>\nPlease enter a valid Telegram post URL (e.g. <code>https://t.me/channel/123</code>):", parse_mode="HTML")
        return STATE_ORDER_LINK

    context.user_data["order_link"] = text
    min_qty = int(db.get_setting("min_order_qty", config.DEFAULT_MIN_ORDER_QTY))
    max_qty = int(db.get_setting("max_order_qty", config.DEFAULT_MAX_ORDER_QTY))

    await update.message.reply_text(
        f"✅ <b>Post Link Received!</b>\n\n"
        f"🔢 <b>Enter quantity of views:</b>\n"
        f"• Minimum: <code>{min_qty}</code>\n"
        f"• Maximum: <code>{max_qty}</code>",
        parse_mode="HTML"
    )
    return STATE_ORDER_QTY

async def order_view_get_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/cancel"):
        await update.message.reply_text("❌ Order cancelled.")
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid number for quantity:")
        return STATE_ORDER_QTY

    qty = int(text)
    min_qty = int(db.get_setting("min_order_qty", config.DEFAULT_MIN_ORDER_QTY))
    max_qty = int(db.get_setting("max_order_qty", config.DEFAULT_MAX_ORDER_QTY))

    if qty < min_qty or qty > max_qty:
        await update.message.reply_text(f"⚠️ Quantity must be between <code>{min_qty}</code> and <code>{max_qty}</code>. Try again:", parse_mode="HTML")
        return STATE_ORDER_QTY

    rate = float(db.get_setting("price_per_1000", config.DEFAULT_PRICE_PER_1000))
    cost = round((qty / 1000.0) * rate, 2)
    user_id = update.effective_user.id
    db_user = db.get_user(user_id)

    context.user_data["order_qty"] = qty
    context.user_data["order_cost"] = cost

    if db_user["balance"] < cost:
        await update.message.reply_text(
            f"❌ <b>Insufficient Balance!</b>\n\n"
            f"💰 Required: <code>{clean_num(cost)} Points</code>\n"
            f"💳 Your Balance: <code>{clean_num(db_user['balance'])} Points</code>\n\n"
            f"Please top up your balance using the 💳 <b>Top Up</b> menu.",
            parse_mode="HTML"
        )
        return ConversationHandler.END

    confirm_msg = (
        f"📝 <b>CONFIRM YOUR ORDER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Post Link:</b> <code>{context.user_data['order_link']}</code>\n"
        f"👁️ <b>Quantity:</b> <code>{qty} views</code>\n"
        f"💵 <b>Total Cost:</b> <code>{clean_num(cost)} Points</code>\n"
        f"💳 <b>Your Balance:</b> <code>{clean_num(db_user['balance'])} Points</code>\n"
        f"💰 <b>Balance After Order:</b> <code>{clean_num(db_user['balance'] - cost)} Points</code>\n\n"
        f"Do you want to confirm this order?"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm & Order", callback_data="confirm_order_yes"),
            InlineKeyboardButton("❌ Cancel Order", callback_data="confirm_order_no")
        ]
    ])

    await update.message.reply_text(confirm_msg, parse_mode="HTML", reply_markup=keyboard)
    return STATE_ORDER_CONFIRM

async def order_view_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_order_no":
        await query.edit_message_text("❌ Order cancelled.")
        return ConversationHandler.END

    user_id = query.from_user.id
    db_user = db.get_user(user_id)
    cost = context.user_data.get("order_cost", 0)
    link = context.user_data.get("order_link", "")
    qty = context.user_data.get("order_qty", 0)

    if db_user["balance"] < cost:
        await query.edit_message_text("❌ Insufficient balance! Order failed.")
        return ConversationHandler.END

    await query.edit_message_text("⏳ <b>Processing your order with SMM Panel...</b>", parse_mode="HTML")

    # Get SMM Config
    api_url = db.get_setting("smm_api_url", config.DEFAULT_SMM_API_URL)
    api_key = db.get_setting("smm_api_key", config.DEFAULT_SMM_API_KEY)
    service_id = int(db.get_setting("smm_service_id", config.DEFAULT_SMM_SERVICE_ID))

    smm_client = SMMPanelClient(api_url, api_key)
    success, res = await smm_client.place_order(service_id=service_id, link=link, quantity=qty)

    if success:
        smm_order_id = res.get("order", 0)
        # Deduct balance & log order
        db.update_balance(user_id, -cost)
        order_db_id = db.add_order(user_id, smm_order_id, link, qty, cost)

        rem_bal = round(db_user["balance"] - cost, 2)
        success_msg = (
            f"✅ <b>ORDER SUCCESSFUL!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Order ID:</b> <code>#{order_db_id}</code>\n"
            f"🌐 <b>SMM Order Ref:</b> <code>#{smm_order_id}</code>\n"
            f"👁️ <b>Quantity:</b> {qty} views\n"
            f"💵 <b>Cost Deducted:</b> {clean_num(cost)} Points\n"
            f"💳 <b>Remaining Balance:</b> {clean_num(rem_bal)} Points\n\n"
            f"🚀 <b>Views are being delivered to your post now!</b>\n"
            f"💡 You can check live progress anytime using 🔎 <b>Order Status</b> (Order ID: <code>#{order_db_id}</code>)."
        )
        await query.edit_message_text(success_msg, parse_mode="HTML")
    else:
        err_detail = res.get("error", "Unknown SMM API Error")
        fail_msg = (
            f"❌ <b>ORDER FAILED!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Reason: <code>{err_detail}</code>\n\n"
            f"No points were deducted from your account. Please contact admin if this persists."
        )
        await query.edit_message_text(fail_msg, parse_mode="HTML")

    return ConversationHandler.END


# ==========================================
# ORDER STATUS LOOKUP FLOW
# ==========================================

async def order_status_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if order_id passed in command e.g. /status 101
    if context.args and context.args[0].replace("#", "").isdigit():
        order_id = int(context.args[0].replace("#", ""))
        await show_order_status(update, context, order_id)
        return ConversationHandler.END

    await update.message.reply_text(
        "🔎 <b>ORDER STATUS LOOKUP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Please send your <b>Order ID</b> (e.g. <code>101</code>):\n\n"
        "<i>Type /cancel to cancel.</i>",
        parse_mode="HTML"
    )
    return STATE_ORDER_STATUS_ID

async def order_status_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace("#", "")
    if text.startswith("/cancel"):
        await update.message.reply_text("❌ Operation cancelled.")
        return ConversationHandler.END

    if not text.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid numerical Order ID (e.g. 101):")
        return STATE_ORDER_STATUS_ID

    order_id = int(text)
    await show_order_status(update, context, order_id)
    return ConversationHandler.END

async def show_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    order = db.get_order_by_id(order_id)
    if not order:
        await update.message.reply_text(f"❌ <b>Order #{order_id} not found!</b>\nPlease check your Order ID and try again.", parse_mode="HTML")
        return

    api_url = db.get_setting("smm_api_url", config.DEFAULT_SMM_API_URL)
    api_key = db.get_setting("smm_api_key", config.DEFAULT_SMM_API_KEY)
    client = SMMPanelClient(api_url, api_key)
    
    ok, res = await client.get_order_status(order['smm_order_id'])
    
    live_status = order['status']
    start_count = "N/A"
    remains = "N/A"

    if ok and isinstance(res, dict):
        s_text = str(res.get("status", "")).title()
        if s_text:
            live_status = s_text
        if "start_count" in res:
            start_count = res.get("start_count")
        if "remains" in res:
            remains = res.get("remains")

    status_emoji = "⏳"
    if "Completed" in live_status:
        status_emoji = "🟢"
    elif "Processing" in live_status or "In Progress" in live_status:
        status_emoji = "🔵"
    elif "Cancel" in live_status or "Refund" in live_status:
        status_emoji = "❌"

    status_msg = (
        f"🔎 <b>ORDER STATUS REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Order ID:</b> <code>#{order['id']}</code>\n"
        f"🌐 <b>SMM Order Ref:</b> <code>#{order['smm_order_id']}</code>\n"
        f"🔗 <b>Post Link:</b> <code>{order['post_link'][:35]}...</code>\n"
        f"👁️ <b>Quantity:</b> <code>{order['quantity']} views</code>\n"
        f"💵 <b>Cost:</b> <code>{clean_num(order['cost'])} Points</code>\n"
        f"📅 <b>Placed On:</b> {order['created_at']}\n\n"
        f"📊 <b>Live Status:</b> {status_emoji} <b>{live_status}</b>\n"
    )
    if start_count != "N/A":
        status_msg += f"📈 Start Count: <code>{start_count}</code> | Remains: <code>{remains}</code>\n"

    await update.message.reply_text(status_msg, parse_mode="HTML")


# ==========================================
# REVAMPED TOP UP / PACKAGES CONVERSATION FLOW
# ==========================================

async def topup_start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    upi_id = db.get_setting("upi_id", config.DEFAULT_UPI_ID)
    upi_name = db.get_setting("upi_name", config.DEFAULT_UPI_NAME)

    keyboard_buttons = []
    for pkg in TOPUP_PACKAGES:
        btn_text = f"🪙 {clean_num(pkg['pts'])} Points = ₹{pkg['inr']}"
        callback_data = f"topup_pkg_{pkg['pts']}_{pkg['inr']}"
        keyboard_buttons.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    msg = (
        f"💳 <b>TOP UP / BUY POINTS PACKAGES</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Select a points package below to proceed with payment:\n\n"
        f"📱 <b>Payment UPI ID:</b> <code>{upi_id}</code> ({upi_name})\n\n"
        f"👇 <b>Choose your package:</b>"
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)
    return STATE_TOPUP_SELECT_PKG

async def topup_package_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    parts = data.split("_")
    pts = int(parts[2])
    inr = int(parts[3])

    context.user_data["topup_pts"] = pts
    context.user_data["topup_inr"] = inr

    upi_id = db.get_setting("upi_id", config.DEFAULT_UPI_ID)
    upi_name = db.get_setting("upi_name", config.DEFAULT_UPI_NAME)

    msg = (
        f"💳 <b>SELECTED PACKAGE: {clean_num(pts)} Points (₹{inr})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Choose how you would like to pay:\n\n"
        f"• <b>UPI ID:</b> <code>{upi_id}</code>\n"
        f"• <b>Name:</b> {upi_name}\n\n"
        f"👇 Click an option below:"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Show UPI ID", callback_data="topup_show_upi"),
            InlineKeyboardButton("🖼️ Show QR Code", callback_data="topup_show_qr")
        ]
    ])

    await query.edit_message_text(msg, parse_mode="HTML", reply_markup=keyboard)
    return STATE_TOPUP_PROOF

async def topup_method_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    pts = context.user_data.get("topup_pts", 1000)
    inr = context.user_data.get("topup_inr", 5)
    upi_id = db.get_setting("upi_id", config.DEFAULT_UPI_ID)
    upi_name = db.get_setting("upi_name", config.DEFAULT_UPI_NAME)

    if data == "topup_show_upi":
        msg = (
            f"📱 <b>PAY VIA UPI ID</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Package:</b> <code>{clean_num(pts)} Points</code>\n"
            f"💵 <b>Price:</b> <code>₹{inr} INR</code>\n\n"
            f"👇 <b>Copy UPI ID:</b>\n<code>{upi_id}</code>\n"
            f"👤 <b>Name:</b> {upi_name}\n\n"
            f"📸 <b>AFTER PAYMENT:</b>\n"
            f"Send the <b>Payment Screenshot (Photo)</b> or <b>UTR / Transaction Ref</b> in this chat now!"
        )
        await query.edit_message_text(msg, parse_mode="HTML")
    elif data == "topup_show_qr":
        msg = (
            f"🖼️ <b>PAY VIA QR CODE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Package:</b> <code>{clean_num(pts)} Points</code>\n"
            f"💵 <b>Price:</b> <code>₹{inr} INR</code>\n\n"
            f"📲 Pay to UPI ID: <code>{upi_id}</code> ({upi_name})\n\n"
            f"📸 <b>AFTER PAYMENT:</b>\n"
            f"Send the <b>Payment Screenshot (Photo)</b> or <b>UTR / Transaction Ref</b> in this chat now!"
        )
        await query.edit_message_text(msg, parse_mode="HTML")

    return STATE_TOPUP_PROOF

async def topup_receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    pts = context.user_data.get("topup_pts", 1000)
    amount_inr = context.user_data.get("topup_inr", 5)

    photo_id = None
    utr_text = "Payment Screenshot Attached"

    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        if update.message.caption:
            utr_text = update.message.caption.strip()
    elif update.message.text:
        utr_text = update.message.text.strip()
        if utr_text.startswith("/cancel"):
            await update.message.reply_text("❌ Top up cancelled.")
            return ConversationHandler.END

    req_id = db.create_topup_request(user.id, amount_inr, pts, utr_text, photo_id)

    await update.message.reply_text(
        f"⏳ <b>Top-Up Proof Received!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Request ID:</b> #{req_id}\n"
        f"📦 <b>Package:</b> {clean_num(pts)} Points\n"
        f"💵 <b>Amount:</b> ₹{clean_num(amount_inr)}\n"
        f"🧾 <b>Ref/UTR:</b> <code>{utr_text}</code>\n\n"
        f"Admin will verify your payment and credit points shortly.",
        parse_mode="HTML"
    )

    # Admin Alert Message
    admin_alert_msg = (
        f"🚨 <b>NEW TOP-UP PAYMENT RECEIVED!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Req ID:</b> #{req_id}\n"
        f"👤 <b>User:</b> {user.first_name} (@{user.username or 'N/A'})\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📦 <b>Package Points:</b> <code>{clean_num(pts)} Points</code>\n"
        f"💵 <b>Amount Paid:</b> <code>₹{clean_num(amount_inr)} INR</code>\n"
        f"🧾 <b>UTR / Screenshot Ref:</b> <code>{utr_text}</code>"
    )

    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ Approve & Credit {clean_num(pts)} Pts", callback_data=f"admin_approve_topup_{req_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_topup_{req_id}")
        ]
    ])

    for admin_id in config.ADMIN_IDS:
        try:
            if photo_id:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_id,
                    caption=admin_alert_msg,
                    parse_mode="HTML",
                    reply_markup=admin_keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_alert_msg,
                    parse_mode="HTML",
                    reply_markup=admin_keyboard
                )
        except Exception as e:
            logger.error(f"Failed to alert admin {admin_id}: {e}")

    return ConversationHandler.END


# ==========================================
# REDEEM CODE FLOW
# ==========================================

async def redeem_code_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎟️ <b>REDEEM PROMO CODE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Enter your redeem code below to claim free points:\n\n"
        "<i>Type /cancel to cancel.</i>",
        parse_mode="HTML"
    )
    return STATE_REDEEM_CODE

async def redeem_code_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    if code.startswith("/cancel"):
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    success, msg, pts = db.redeem_code(user_id, code)

    await update.message.reply_text(msg, parse_mode="HTML")
    return ConversationHandler.END


# ==========================================
# ADMIN PANEL HANDLERS
# ==========================================

async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use admin commands.")
        return

    admin_msg = (
        f"👑 <b>ADMIN PANEL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome Admin! Select an action below to manage the bot:"
    )
    await update.message.reply_text(admin_msg, parse_mode="HTML", reply_markup=get_admin_inline_keyboard())

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_user_admin(user_id):
        await query.message.reply_text("❌ Unauthorized.")
        return

    data = query.data

    if data == "admin_stats":
        stats = db.get_stats()
        msg = (
            f"📊 <b>BOT STATISTICS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Total Users:</b> <code>{stats['total_users']}</code>\n"
            f"💎 <b>Total User Balance:</b> <code>{clean_num(stats['total_balance'])} Pts</code>\n"
            f"📦 <b>Total Orders Placed:</b> <code>{stats['total_orders']}</code>\n"
            f"💵 <b>Total Spent on Orders:</b> <code>{clean_num(stats['total_spent'])} Pts</code>\n"
            f"💳 <b>Approved Topups Total:</b> <code>₹{clean_num(stats['approved_inr'])} INR</code>"
        )
        await query.message.reply_text(msg, parse_mode="HTML")

    elif data == "admin_smm_bal":
        api_url = db.get_setting("smm_api_url", config.DEFAULT_SMM_API_URL)
        api_key = db.get_setting("smm_api_key", config.DEFAULT_SMM_API_KEY)
        client = SMMPanelClient(api_url, api_key)
        ok, res = await client.get_balance()
        if ok:
            bal = res.get("balance", "N/A")
            curr = res.get("currency", "USD")
            await query.message.reply_text(f"💳 <b>SMM Panel Balance:</b> <code>{bal} {curr}</code>", parse_mode="HTML")
        else:
            await query.message.reply_text(f"❌ <b>SMM Error:</b> {res.get('error')}", parse_mode="HTML")

    elif data == "admin_add_pts":
        await query.message.reply_text("💡 Use command: <code>/addpoints &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")

    elif data == "admin_rem_pts":
        await query.message.reply_text("💡 Use command: <code>/removepoints &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")

    elif data == "admin_settings":
        url = db.get_setting("smm_api_url")
        sid = db.get_setting("smm_service_id")
        rate = db.get_setting("price_per_1000")
        upi = db.get_setting("upi_id")
        msg = (
            f"⚙️ <b>CURRENT BOT SETTINGS</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 <b>API URL:</b> <code>{url}</code>\n"
            f"🆔 <b>Service ID:</b> <code>{sid}</code>\n"
            f"💰 <b>Rate/1k Views:</b> <code>{clean_num(rate)} Pts</code>\n"
            f"💳 <b>UPI ID:</b> <code>{upi}</code>\n\n"
            f"<b>Change Settings:</b>\n"
            f"• <code>/set smm_api_url &lt;url&gt;</code>\n"
            f"• <code>/set smm_api_key &lt;key&gt;</code>\n"
            f"• <code>/set smm_service_id &lt;id&gt;</code>\n"
            f"• <code>/set price_per_1000 &lt;amount&gt;</code>\n"
            f"• <code>/set upi_id &lt;upi_id&gt;</code>"
        )
        await query.message.reply_text(msg, parse_mode="HTML")

    elif data == "admin_ban_menu":
        await query.message.reply_text("💡 Commands:\n• Ban: <code>/ban &lt;user_id&gt;</code>\n• Unban: <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")

    elif data.startswith("admin_approve_topup_"):
        req_id = int(data.split("_")[-1])
        ok, req = db.process_topup_request(req_id, approve=True)
        if ok and req:
            edit_text = f"✅ Topup Request #{req_id} Approved! Credited {clean_num(req['points'])} Pts to User ID {req['user_id']}."
            if query.message.photo:
                await query.edit_message_caption(caption=edit_text)
            else:
                await query.edit_message_text(text=edit_text)

            try:
                await context.bot.send_message(
                    chat_id=req['user_id'],
                    text=f"🎉 <b>Top-Up Successful!</b>\nAdmin approved your payment of ₹{clean_num(req['amount_inr'])}.\n<b>+{clean_num(req['points'])} Points</b> credited to your balance!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            msg_fail = f"⚠️ Request #{req_id} already processed or invalid."
            if query.message.photo:
                await query.edit_message_caption(caption=msg_fail)
            else:
                await query.edit_message_text(text=msg_fail)

    elif data.startswith("admin_reject_topup_"):
        req_id = int(data.split("_")[-1])
        ok, req = db.process_topup_request(req_id, approve=False)
        if ok and req:
            edit_text = f"❌ Topup Request #{req_id} Rejected."
            if query.message.photo:
                await query.edit_message_caption(caption=edit_text)
            else:
                await query.edit_message_text(text=edit_text)

            try:
                await context.bot.send_message(
                    chat_id=req['user_id'],
                    text=f"❌ <b>Top-Up Request Rejected!</b>\nYour payment of ₹{clean_num(req['amount_inr'])} could not be verified. Contact admin if you believe this is an error.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        else:
            msg_fail = f"⚠️ Request #{req_id} already processed or invalid."
            if query.message.photo:
                await query.edit_message_caption(caption=msg_fail)
            else:
                await query.edit_message_text(text=msg_fail)


# --- ADMIN COMMAND UTILITIES ---

async def admin_addpoints_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: <code>/addpoints &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")
        return
    try:
        t_user = int(context.args[0])
        amt = float(context.args[1])
        new_bal = db.update_balance(t_user, amt)
        await update.message.reply_text(f"✅ Added {clean_num(amt)} Points to User {t_user}. New Balance: {clean_num(new_bal)} Pts.")
        try:
            await context.bot.send_message(t_user, f"🎉 <b>Admin added +{clean_num(amt)} Points to your account!</b>", parse_mode="HTML")
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("⚠️ Invalid parameters!")

async def admin_removepoints_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: <code>/removepoints &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")
        return
    try:
        t_user = int(context.args[0])
        amt = float(context.args[1])
        new_bal = db.update_balance(t_user, -amt)
        await update.message.reply_text(f"✅ Removed {clean_num(amt)} Points from User {t_user}. New Balance: {clean_num(new_bal)} Pts.")
    except ValueError:
        await update.message.reply_text("⚠️ Invalid parameters!")

async def admin_ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Usage: <code>/ban &lt;user_id&gt;</code>", parse_mode="HTML")
        return
    t_user = int(context.args[0])
    db.set_user_ban(t_user, True)
    await update.message.reply_text(f"🚫 User {t_user} has been banned.")

async def admin_unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Usage: <code>/unban &lt;user_id&gt;</code>", parse_mode="HTML")
        return
    t_user = int(context.args[0])
    db.set_user_ban(t_user, False)
    await update.message.reply_text(f"✅ User {t_user} has been unbanned.")

async def admin_gencode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text("⚠️ Usage: <code>/gencode &lt;CODE&gt; &lt;POINTS&gt; &lt;MAX_USES&gt;</code>", parse_mode="HTML")
        return
    code = context.args[0].upper()
    try:
        pts = float(context.args[1])
        max_u = int(context.args[2])
        if db.create_redeem_code(code, pts, max_u):
            await update.message.reply_text(f"🎟️ <b>Redeem Code Created!</b>\nCode: <code>{code}</code>\nPoints: <b>{clean_num(pts)}</b>\nMax Uses: <b>{max_u}</b>", parse_mode="HTML")
        else:
            await update.message.reply_text("❌ Code already exists!")
    except ValueError:
        await update.message.reply_text("⚠️ Invalid points or max uses!")

async def admin_set_setting_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: <code>/set &lt;key&gt; &lt;value&gt;</code>", parse_mode="HTML")
        return
    key = context.args[0].lower()
    val = " ".join(context.args[1:])
    db.set_setting(key, val)
    await update.message.reply_text(f"✅ Setting <code>{key}</code> updated to: <code>{val}</code>", parse_mode="HTML")

async def admin_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/broadcast &lt;message text/HTML&gt;</code>", parse_mode="HTML")
        return

    text = update.message.text.split(maxsplit=1)[1]
    users = db.get_all_user_ids()
    await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")

    success = 0
    failed = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05) # Prevent flood limit
        except Exception:
            failed += 1

    await update.message.reply_text(f"✅ <b>Broadcast Finished!</b>\nSent: {success} | Failed: {failed}", parse_mode="HTML")


# --- MAIN CANCEL HANDLER ---
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END


# ==========================================
# MAIN BOT INITIALIZATION
# ==========================================

def main():
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not config.BOT_TOKEN:
        print("[!] Error: BOT_TOKEN is not set in config.py or .env file!")
        print("Please edit .env file and set your BOT_TOKEN.")
        return

    app = Application.builder().token(config.BOT_TOKEN).build()

    # --- Conversation Handlers ---
    order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👁️ Order View$"), order_view_start)],
        states={
            STATE_ORDER_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_view_get_link)],
            STATE_ORDER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_view_get_qty)],
            STATE_ORDER_CONFIRM: [CallbackQueryHandler(order_view_confirm_callback, pattern="^confirm_order_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    status_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🔎 Order Status$"), order_status_start),
            CommandHandler("status", order_status_start)
        ],
        states={
            STATE_ORDER_STATUS_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_status_process)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    topup_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💳 Top Up$"), topup_start_flow),
            CallbackQueryHandler(topup_start_flow, pattern="^start_topup_flow$")
        ],
        states={
            STATE_TOPUP_SELECT_PKG: [CallbackQueryHandler(topup_package_callback, pattern="^topup_pkg_")],
            STATE_TOPUP_PROOF: [
                CallbackQueryHandler(topup_method_callback, pattern="^topup_show_"),
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), topup_receive_proof)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    redeem_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎟️ Redeem Code$"), redeem_code_start)],
        states={
            STATE_REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_code_process)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )

    # --- Register Handlers ---
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_panel_command))
    app.add_handler(CommandHandler("addpoints", admin_addpoints_cmd))
    app.add_handler(CommandHandler("removepoints", admin_removepoints_cmd))
    app.add_handler(CommandHandler("ban", admin_ban_cmd))
    app.add_handler(CommandHandler("unban", admin_unban_cmd))
    app.add_handler(CommandHandler("gencode", admin_gencode_cmd))
    app.add_handler(CommandHandler("set", admin_set_setting_cmd))
    app.add_handler(CommandHandler("broadcast", admin_broadcast_cmd))

    app.add_handler(order_conv)
    app.add_handler(status_conv)
    app.add_handler(topup_conv)
    app.add_handler(redeem_conv)

    app.add_handler(MessageHandler(filters.Regex("^👤 My Account$"), my_account_handler))
    app.add_handler(MessageHandler(filters.Regex("^🎁 Bonus$"), daily_bonus_handler))
    app.add_handler(MessageHandler(filters.Regex("^👥 Refer & Earn$"), refer_earn_handler))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help / Support$"), help_support_handler))
    app.add_handler(MessageHandler(filters.Regex("^👑 Admin Panel$"), admin_panel_command))

    app.add_handler(CallbackQueryHandler(order_history_callback, pattern="^user_order_history$"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

    print("[+] Telegram View SMM Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
