import os, random, string, asyncio, aiohttp, re, json, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from instagrapi import Client

# ================= إعدادات =================
TOKEN = os.getenv("BOT_TOKEN", "8300059251:AAHskwndvl_iihk48fIzWdL_3STfAeu1A30")
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

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    try:
        return json.load(open(ACCOUNTS_FILE, "r", encoding="utf-8"))
    except:
        return []

def load_session(username):
    path = os.path.join(SESSIONS_DIR, f"{username}.json")
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except:
        return None

# ================= تسجيل دخول =================
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
            except:
                return False, {}
            return data.get("authenticated", False), {c.key: c.value for c in sess.cookie_jar}

# ================= بريد Evapmail =================
async def get_email_evp(sess):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'Content-Type': 'application/json'}
    json_data = {'deviceId': ''.join(random.choices(string.ascii_lowercase + string.digits, k=16)), 'expirationMinutes': 60}
    async with sess.post('https://api.evapmail.com/v1/accounts/create', json=json_data, headers=headers) as r:
        data = await r.json()
        return data['email'], data['token']

async def get_code_evp(sess, token, retries=30):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'authorization': f'Bearer {token}'}
    for _ in range(retries):
        async with sess.get('https://api.evapmail.com/v1/messages/inbox', headers=headers) as r:
            try:
                data = await r.json()
            except:
                await asyncio.sleep(2)
                continue
            if data and isinstance(data, list):
                for msg in data:
                    if "Instagram" in msg.get("from", "") or "Instagram" in msg.get("subject", ""):
                        match = re.findall(r"\d{6}", msg.get("subject", "") + msg.get("body", ""))
                        if match:
                            return match[0]
        await asyncio.sleep(2)
    return None

# ================= إنشاء الحساب =================
async def send_dm_with_instagrapi(username, password, to_username, text):
    try:
        cl = Client()
        cl.login(username, password)
        user_id = cl.user_id_from_username(to_username)
        cl.direct_send(text, [user_id])
        return f"📩 DM أُرسل إلى {to_username}"
    except Exception as e:
        return f"❌ فشل إرسال DM: {e}"

async def create_account(progress_cb):
    username = random_user(8)
    machine_id = ''.join(random.choice(string.hexdigits) for _ in range(16))

    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=conn) as sess:
        email, token = await get_email_evp(sess)
        if not email:
            return None
        await progress_cb(f"📧 البريد: {email}", 30)

        async with sess.get("https://www.instagram.com/accounts/emailsignup/") as r:
            cookies = {c.key: c.value for c in sess.cookie_jar}
            csrftoken = cookies.get("csrftoken")
            if not csrftoken:
                return None

        headers = {
            "User-Agent": "Mozilla/5.0",
            "X-Ig-App-Id": "936619743392459",
            "X-CSRFToken": csrftoken,
            "Referer": "https://www.instagram.com/accounts/emailsignup/",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        await sess.post("https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/",
                        headers=headers, data={
                            "email": email, "username": username,
                            "first_name": "DEMAN",
                            "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{PASSWORD}",
                            "client_id": machine_id,
                        })

        await sess.post("https://www.instagram.com/api/v1/accounts/send_verify_email/",
                        headers=headers, data={"device_id": machine_id, "email": email})
        await progress_cb("📨 تم إرسال الكود للبريد...", 50)

        code = await get_code_evp(sess, token)
        if not code:
            return None
        await progress_cb(f"✅ الكود: {code}", 70)

        async with sess.post("https://www.instagram.com/api/v1/accounts/check_confirmation_code/",
                             headers=headers, data={"code": code, "device_id": machine_id, "email": email}) as resp_code:
            data = await resp_code.json()
            if "signup_code" not in data:
                return None
            sn = data["signup_code"]

        async with sess.post("https://www.instagram.com/api/v1/web/accounts/web_create_ajax/",
                             headers=headers, data={
                                 "email": email, "username": username,
                                 "first_name": "DEMAN",
                                 "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{PASSWORD}",
                                 "client_id": machine_id,
                                 "day": "22", "month": "8", "year": "1995",
                                 "tos_version": "row",
                                 "force_sign_up_code": sn,
                             }) as resp_final:
            final = await resp_final.json()
            if final.get("account_created"):
                ok, cookies = await insta_login(username, PASSWORD)
                if ok:
                    save_account(email, username, PASSWORD, cookies)
                    return email, username, PASSWORD, True
    return None

# ================= الأكشنات =================
async def insta_action(username, action, target=None, text=None):
    session_data = load_session(username)
    if not session_data:
        return f"❌ ما لقيت جلسة للحساب {username}"

    cookies = session_data.get("cookies", {})
    csrftoken = cookies.get("csrftoken")
    headers = {"User-Agent": "Mozilla/5.0", "X-CSRFToken": csrftoken, "Referer": "https://www.instagram.com/"}

    async with aiohttp.ClientSession(cookies=cookies, headers=headers) as sess:
        if action == "like":
            url = f"https://www.instagram.com/web/likes/{target}/like/"
            async with sess.post(url) as r:
                return f"👍 لايك → {r.status}"
        elif action == "comment":
            url = f"https://www.instagram.com/web/comments/{target}/add/"
            async with sess.post(url, data={"comment_text": text}) as r:
                return f"💬 كومنت: {text} → {r.status}"
        elif action == "follow":
            url = f"https://www.instagram.com/web/friendships/{target}/follow/"
            async with sess.post(url) as r:
                return "✅ فولو تم" if r.status == 200 else f"❌ فشل ({r.status})"
        elif action == "unfollow":
            url = f"https://www.instagram.com/web/friendships/{target}/unfollow/"
            async with sess.post(url) as r:
                return f"❌ أنفولو → {r.status}"
        elif action == "dm":
            uname = target.replace("@", "").split("/")[-1].split("?")[0]
            return await send_dm_with_instagrapi(username, PASSWORD, uname, text)
        elif action == "refresh":
            return "🔄 تحديث الجلسة لاحقاً."

    return "⚠️ أكشن غير معروف"

# ================= لوحة التحكم =================
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

# ================= أوامر البوت =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🆕 إنشاء حساب", callback_data="new_account")],
        [InlineKeyboardButton("🛠️ لوحة التحكم", callback_data="dashboard")]
    ]
    await update.message.reply_text("👋 أهلاً بك\n⚡ Powered by DEMAN.STORE",
                                    reply_markup=InlineKeyboardMarkup(keyboard))

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
            context.user_data["pending_action"] = {"action": action, "username": username}
            await query.message.reply_text(f"✍️ أرسل الهدف الآن\n➡️ العملية: {action}\n➡️ الحساب: {username}")

# ================= استقبال النصوص =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "pending_action" not in context.user_data:
        return
    pending = context.user_data.pop("pending_action")
    action, username = pending["action"], pending["username"]
    text = update.message.text.strip()

    target = text
    result = await insta_action(username, action, target=target, text=text)
    await update.message.reply_text(result)

# ================= تشغيل البوت =================
def main():
    print("✅ Bot is starting...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
