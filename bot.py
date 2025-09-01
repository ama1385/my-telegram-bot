import os, random, string, asyncio, aiohttp, re, json, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import requests
print("🔥 DEMAN Bot Started 🔥")
# ================= إعدادات =================
TOKEN = os.getenv("BOT_TOKEN", "8300059251:AAFabYuCoYzK-ty0vkIQGaCas8aWL8N9n5Q")
PASSWORD = os.getenv("BOT_DEFAULT_PASSWORD", "demansswor@d11")
ACCOUNTS_FILE = "accounts.json"
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# ================= Utils =================
def random_user(length=10):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def save_account(email, username, password, cookies):
    data = []
    if os.path.exists(ACCOUNTS_FILE):
        try:
            data = json.load(open(ACCOUNTS_FILE, "r", encoding="utf-8"))
        except:
            data = []
    data.append({"email": email, "username": username, "password": password})
    json.dump(data, open(ACCOUNTS_FILE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    with open(os.path.join(SESSIONS_DIR, f"{username}.json"), "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies}, f, indent=2, ensure_ascii=False)

def request_with_retry(sess, method, url, **kwargs):
    for _ in range(3):
        try:
            if method == "get":
                return sess.get(url, timeout=30, **kwargs)
            elif method == "post":
                return sess.post(url, timeout=30, **kwargs)
        except:
            time.sleep(2)
    return None

def get_email_guerrilla(sess):
    r = request_with_retry(sess, "get", "https://api.guerrillamail.com/ajax.php?f=get_email_address")
    if not r:
        return None, None
    data = r.json()
    return data["email_addr"], data["sid_token"]

def get_code_guerrilla(sess, sid_token):
    for _ in range(15):
        r = request_with_retry(sess, "get", f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid_token}")
        if r and r.json().get("list"):
            email_id = r.json()["list"][0]["mail_id"]
            msg = request_with_retry(sess, "get", f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={email_id}&sid_token={sid_token}")
            match = re.findall(r"\d{6}", msg.json().get("mail_body", ""))
            if match:
                return match[0]
        time.sleep(3)
    return None

async def insta_login(username, password):
    login_url = "https://www.instagram.com/accounts/login/ajax/"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/accounts/login/",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-IG-App-ID": "936619743392459"
    }

    async with aiohttp.ClientSession(headers=headers) as sess:
        async with sess.get("https://www.instagram.com/accounts/login/") as r:
            cookies = {c.key: c.value for c in sess.cookie_jar}
            csrftoken = cookies.get("csrftoken")
            if not csrftoken:
                return False, {}
            sess.headers["X-CSRFToken"] = csrftoken

        enc_pwd = f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}"
        payload = {"username": username, "enc_password": enc_pwd, "optIntoOneTap": "false"}

        async with sess.post(login_url, data=payload) as r:
            try:
                data = await r.json()
                return data.get("authenticated", False), {c.key: c.value for c in sess.cookie_jar}
            except:
                return False, {}

# ================= إنشاء الحساب =================
async def create_account(progress_cb):
    username = random_user(8)
    machine_id = ''.join(random.choice(string.hexdigits) for _ in range(16))

    sess = requests.Session()
    email, token = get_email_guerrilla(sess)
    if not email:
        return None
    await progress_cb(f"📧 البريد: {email}", 30)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Ig-App-Id": "936619743392459",
        "Referer": "https://www.instagram.com/accounts/emailsignup/",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    r = request_with_retry(sess, "get", "https://www.instagram.com/accounts/emailsignup/")
    csrftoken = r.cookies.get("csrftoken")
    if not csrftoken:
        return None
    sess.headers.update({"X-CSRFToken": csrftoken})

    request_with_retry(sess, "post",
                       "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/", data={
        "email": email,
        "username": username,
        "first_name": "DEMAN",
        "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{PASSWORD}",
        "client_id": machine_id,
    })

    request_with_retry(sess, "post", "https://www.instagram.com/api/v1/accounts/send_verify_email/",
                       data={"device_id": machine_id, "email": email})
    await progress_cb("📨 تم إرسال الكود للبريد...", 50)

    code = get_code_guerrilla(sess, token)
    if not code:
        return None
    await progress_cb(f"✅ الكود: {code}", 70)

    r = request_with_retry(sess, "post",
                           "https://www.instagram.com/api/v1/accounts/check_confirmation_code/",
                           data={"code": code, "device_id": machine_id, "email": email})
    data = r.json()
    if "signup_code" not in data:
        return None
    sn = data["signup_code"]

    r = request_with_retry(sess, "post", "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/", data={
        "email": email,
        "username": username,
        "first_name": "DEMAN",
        "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{PASSWORD}",
        "client_id": machine_id,
        "day": "22", "month": "8", "year": "1995",
        "tos_version": "row",
        "force_sign_up_code": sn,
    })

    if r.json().get("account_created"):
        ok, cookies = await insta_login(username, PASSWORD)
        if ok:
            save_account(email, username, PASSWORD, cookies)
            return email, username, PASSWORD, True
    return None

# ================= Telegram Bot =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🆕 إنشاء حساب", callback_data="new_account")],
        [InlineKeyboardButton("🛠️ لوحة التحكم", callback_data="dashboard")]
    ]
    await update.message.reply_text(
        "👋 أهلاً بك\n⚡ Powered by DEMAN.STORE",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

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

# ================= Main =================
def main():
    print("✅ Bot is starting...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
