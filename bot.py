import requests, random, string, time, re, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== إعدادات البوت =====
TOKEN = "8300059251:AAHskwndvl_iihk48fIzWdL_3STfAeu1A30"
PASSWORD = "Create@Password11"
PROXY_FILE = "proxy.txt"

# ===== دوال مساعدة =====
def load_proxy():
    """تحميل البروكسي من ملف"""
    try:
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            proxy = f.read().strip()
            if proxy:
                return {"http": proxy, "https": proxy}
    except FileNotFoundError:
        pass
    return None

def random_user(length=10):
    """توليد يوزر عشوائي"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def request_with_retry(sess, method, url, **kwargs):
    """تنفيذ طلب مع إعادة المحاولة حتى 3 مرات"""
    for _ in range(3):
        try:
            if method == "get":
                return sess.get(url, timeout=30, **kwargs)
            elif method == "post":
                return sess.post(url, timeout=30, **kwargs)
        except requests.exceptions.RequestException:
            time.sleep(2)
    return None

# ===== البريد المؤقت =====
def get_email_guerrilla(sess):
    r = request_with_retry(sess, "get", "https://api.guerrillamail.com/ajax.php?f=get_email_address")
    if not r: return None
    data = r.json()
    return data["email_addr"], data["sid_token"]

def get_code_guerrilla(sess, sid_token):
    for _ in range(12):
        r = request_with_retry(sess, "get", f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid_token}")
        if r and r.json().get("list"):
            email_id = r.json()["list"][0]["mail_id"]
            msg = request_with_retry(sess, "get", f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={email_id}&sid_token={sid_token}")
            match = re.findall(r"\d{6}", msg.json().get("mail_body", ""))
            if match:
                return match[0]
        time.sleep(3)
    return None

def get_email_evp(sess):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'Content-Type': 'application/json'}
    json_data = {'deviceId': ''.join(random.choices(string.ascii_lowercase + string.digits, k=16)), 'expirationMinutes': 60}
    r = request_with_retry(sess, "post", 'https://api.evapmail.com/v1/accounts/create', json=json_data, headers=headers)
    if not r: return None
    token = r.json()['token']
    return r.json()['email'], token

def get_code_evp(sess, token):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'authorization': f'Bearer {token}'}
    for _ in range(12):
        r = request_with_retry(sess, "get", 'https://api.evapmail.com/v1/messages/inbox', headers=headers)
        if r and 'Instagram' in r.text:
            code = str(r.json()[0]["subject"])[:6]
            return code
        time.sleep(3)
    return None

# ===== إنشاء الحساب =====
def create_account():
    sess = requests.Session()

    # تحميل البروكسي
    proxy = load_proxy()
    if proxy:
        try:
            sess.proxies = proxy
            sess.get("https://www.google.com", timeout=5)
        except:
            sess.proxies = {}
    else:
        sess.proxies = {}

    # جلب CSRF
    request_with_retry(sess, "get", "https://www.instagram.com/accounts/emailsignup/")
    csrftoken = sess.cookies.get_dict().get("csrftoken")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Ig-App-Id": "936619743392459",
        "X-Csrftoken": csrftoken,
        "Referer": "https://www.instagram.com/accounts/emailsignup/",
    }

    # تجربة GuerrillaMail أولاً
    email_data = get_email_guerrilla(sess)
    if email_data:
        email, sid_token = email_data
        code_func = lambda: get_code_guerrilla(sess, sid_token)
    else:
        # إذا فشل، تجربة Evapmail
        email_data = get_email_evp(sess)
        if not email_data:
            return None
        email, token = email_data
        code_func = lambda: get_code_evp(sess, token)

    username = random_user(12)
    machine_id = ''.join(random.choice(string.hexdigits) for _ in range(16))

    # محاولة التسجيل
    request_with_retry(sess, "post", "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/",
                       headers=headers,
                       data={
                           "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:0:{PASSWORD}",
                           "email": email,
                           "first_name": "DEMAN",
                           "username": username,
                           "client_id": machine_id,
                           "seamless_login_enabled": "1",
                           "opt_into_one_tap": "false",
                       })

    # إرسال الكود
    request_with_retry(sess, "post", "https://www.instagram.com/api/v1/accounts/send_verify_email/",
                       headers=headers, data={"device_id": machine_id, "email": email})

    # استلام الكود
    code = code_func()
    if not code:
        return None

    # تحقق الكود
    resp_code = request_with_retry(sess, "post", "https://www.instagram.com/api/v1/accounts/check_confirmation_code/",
                                   headers=headers, data={"code": code, "device_id": machine_id, "email": email})
    if not resp_code or "signup_code" not in resp_code.json():
        return None
    sn = resp_code.json()["signup_code"]

    # إنشاء نهائي
    resp_final = request_with_retry(sess, "post", "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/",
                                    headers=headers, data={
                                        "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:0:{PASSWORD}",
                                        "day": "22",
                                        "email": email,
                                        "first_name": "DEMAN",
                                        "month": "8",
                                        "username": username,
                                        "year": "1995",
                                        "client_id": machine_id,
                                        "tos_version": "row",
                                        "force_sign_up_code": sn,
                                    })
    if resp_final and resp_final.json().get("account_created"):
        return email, username, PASSWORD
    return None

# ===== بوت تيليجرام =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("إنشاء حساب", callback_data="new_account")]]
    await update.message.reply_text("👋 أهلاً بك في أداة الإنشاء\n⚡ Powered by @demanstoree", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "new_account":
        msg = await query.message.reply_text(f"⏳ بدء الإنشاء... 🟪⚪⚪⚪⚪ (20%)\n⚡ Powered by @demanstoree")
        steps = [
            ("📧 البريد جاهز...", "🟪🟪⚪⚪⚪ (40%)"),
            ("📨 بانتظار الكود...", "🟪🟪🟪⚪⚪ (60%)"),
            ("✅ تم التحقق من الكود...", "🟪🟪🟪🟪⚪ (80%)"),
        ]
        for text, bar in steps:
            await asyncio.sleep(1.5)
            await msg.edit_text(f"{text} {bar}\n⚡ Powered by DEMAN.STORE")

        result = create_account()
        if result:
            email, username, password = result
            keyboard = [[InlineKeyboardButton("➕ إنشاء حساب آخر", callback_data="new_account")]]
            await asyncio.sleep(1)
            await msg.edit_text(
                f"🎉 الحساب جاهز! 🟪🟪🟪🟪🟪 (100%)\n\n"
                f"📧 Email: `{email}`\n"
                f"👤 Username: `{username}`\n"
                f"🔑 Password: `{password}`\n\n"
                f"⚡ Powered by DEMAN.STORE",
                parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await msg.edit_text("❌ فشل إنشاء الحساب.\n⚡ Powered by DEMAN.STORE")

# ===== تشغيل البوت =====
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
