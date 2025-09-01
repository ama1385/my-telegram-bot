import os, random, string, asyncio, aiohttp, re, json, time, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from instagrapi import Client

# ================= إعدادات =================
TOKEN = os.getenv("BOT_TOKEN", "8300059251:AAFabYuCoYzK-ty0vkIQGaCas8aWL8N9n5Q")
PASSWORD = os.getenv("BOT_DEFAULT_PASSWORD", "demansswor@d11")

ACCOUNTS_FILE = "accounts.json"
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ================= Logging =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ================= Utils =================
def random_user(length=10):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def save_account(email, username, password, cookies):
    data = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load accounts.json: {e}")
            data = []

    data.append({"email": email, "username": username, "password": password})
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    with open(os.path.join(SESSIONS_DIR, f"{username}.json"), "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies}, f, indent=2, ensure_ascii=False)

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to read accounts.json: {e}")
        return []

def load_session(username):
    path = os.path.join(SESSIONS_DIR, f"{username}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to load session for {username}: {e}")
        return None

# ================= تسجيل دخول =================
async def insta_login(username, password):
    try:
        cl = Client()
        cl.login(username, password)
        return True, cl.get_settings()
    except Exception as e:
        logging.warning(f"Login failed for {username}: {e}")
        return False, {}

# ================= بريد Evapmail =================
async def get_email_evp(sess):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'Content-Type': 'application/json'}
    json_data = {'deviceId': ''.join(random.choices(string.ascii_lowercase + string.digits, k=16)), 'expirationMinutes': 60}
    try:
        async with sess.post('https://api.evapmail.com/v1/accounts/create', json=json_data, headers=headers) as r:
            data = await r.json()
            return data['email'], data['token']
    except Exception as e:
        logging.warning(f"Failed to get Evapmail email: {e}")
        return None, None

async def get_code_evp(sess, token, retries=30):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'authorization': f'Bearer {token}'}
    for _ in range(retries):
        try:
            async with sess.get('https://api.evapmail.com/v1/messages/inbox', headers=headers) as r:
                data = await r.json()
                if data and isinstance(data, list):
                    for msg in data:
                        if "Instagram" in msg.get("from", "") or "Instagram" in msg.get("subject", ""):
                            match = re.findall(r"\d{6}", msg.get("subject", "") + msg.get("body", ""))
                            if match:
                                return match[0]
        except Exception:
            await asyncio.sleep(2)
            continue
        await asyncio.sleep(2)
    return None

# ================= إنشاء الحساب =================
async def create_account(progress_cb):
    username = random_user(8)
    machine_id = ''.join(random.choice(string.hexdigits) for _ in range(16))
    conn = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=conn) as sess:
        email, token = await get_email_evp(sess)
        if not email:
            return None
        await progress_cb(f"📧 البريد: {email}", 30)

        await progress_cb("⏳ خطوة تسجيل Instagram...", 50)
        ok, cookies = await insta_login(username, PASSWORD)
        if ok:
            save_account(email, username, PASSWORD, cookies)
            return email, username, PASSWORD, True
    return None

# ================= أوامر البوت =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🆕 إنشاء حساب", callback_data="new_account")],
        [InlineKeyboardButton("🛠️ لوحة التحكم", callback_data="dashboard")]
    ]
    await update.message.reply_text("👋 أهلاً بك\n⚡ Powered by DEMAN.STORE",
                                    reply_markup=InlineKeyboardMarkup(keyboard))

async def manage_account(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    keyboard = [
        [InlineKeyboardButton("👍 لايك", callback_data=f"like:{username}")],
        [InlineKeyboardButton("💬 كومنت", callback_data=f"comment:{username}")],
        [InlineKeyboardButton("➕ فولو", callback_data=f"follow:{username}")],
        [InlineKeyboardButton("❌ أنفولو", callback_data=f"unfollow:{username}")],
        [InlineKeyboardButton("📩 DM", callback_data=f"dm:{username}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{username}")]
    ]
    await update.callback_query.message.reply_text(
        f"🛠️ التحكم بالحساب: *{username}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "new_account":
        msg = await query.message.reply_text("⏳ بدء الإنشاء...")

        async def progress_cb(text, percent):
            bar = "🟪" * (percent // 20) + "⚪" * (5 - percent // 20)
            await msg.edit_text(f"{text}\n{bar} ({percent}%)\n⚡ Powered by DEMAN.STORE")

        result = await create_account(progress_cb)
        if result:
            email, username, password, ok = result
            await msg.edit_text(f"🎉 الحساب جاهز!\n📧 {email}\n👤 {username}\n🔑 {password}")
        else:
            await msg.edit_text("❌ فشل الإنشاء.")

    elif query.data == "dashboard":
        accounts = load_accounts()
        if not accounts:
            await query.message.reply_text("📂 لا يوجد حسابات.")
            return
        keyboard = [[InlineKeyboardButton(acc["username"], callback_data=f"manage:{acc['username']}")] for acc in accounts]
        await query.message.reply_text("🛠️ اختر الحساب:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("manage:"):
        username = query.data.split(":", 1)[1]
        await manage_account(update, context, username)

    elif ":" in query.data:
        action, username = query.data.split(":", 1)
        if action in ["like", "comment", "follow", "unfollow", "dm", "refresh"]:
            # pending لكل مستخدم
            if "pending_action" not in context.user_data:
                context.user_data["pending_action"] = {}
            context.user_data["pending_action"][user_id] = {"action": action, "username": username}
            await query.message.reply_text(f"✍️ أرسل الهدف الآن\n➡️ العملية: {action}\n➡️ الحساب: {username}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if "pending_action" not in context.user_data or user_id not in context.user_data["pending_action"]:
        return
    pending = context.user_data["pending_action"].pop(user_id)
    action, username = pending["action"], pending["username"]
    text = update.message.text.strip()
       # تنفيذ العملية على الحساب
    # هنا مجرد مثال placeholders، تقدر تغيرها حسب الوظائف الحقيقية
    if action == "like":
        await update.message.reply_text(f"❤️ تم إرسال لايك باستخدام الحساب {username} على {text}")
    elif action == "comment":
        await update.message.reply_text(f"💬 تم إرسال تعليق باستخدام الحساب {username} على {text}")
    elif action == "follow":
        await update.message.reply_text(f"➕ تم متابعة {text} بواسطة {username}")
    elif action == "unfollow":
        await update.message.reply_text(f"❌ تم إلغاء متابعة {text} بواسطة {username}")
    elif action == "dm":
        await update.message.reply_text(f"📩 تم إرسال رسالة لـ {text} بواسطة {username}")
    elif action == "refresh":
        await update.message.reply_text(f"🔄 تم تحديث بيانات الحساب {username}")
    else:
        await update.message.reply_text(f"⚠️ أمر غير معروف: {action}")

# ================= التشغيل =================
def main():
    application = Application.builder().token(TOKEN).build()

    # أوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logging.info("🤖 البوت جاهز للعمل...")
    # polling مع تجاهل الرسائل القديمة
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

