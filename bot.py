import threading
from flask import Flask
import requests, random, string, time, re, asyncio, json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== إعدادات البوت =====
TOKEN = "8300059251:AAHskwndvl_iihk48fIzWdL_3STfAeu1A30"
PASSWORD = "Create@Password11"
PROXY_FILE = "proxy.txt"

# ===== سيرفر ويب (لـ Render) =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! Powered by DEMAN.STORE"

def run_web():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_web, daemon=True).start()

# ===== دوال مساعدة =====
def log_debug(msg, color="white"):
    colors = {
        "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
        "blue": "\033[94m", "white": "\033[97m"
    }
    endc = "\033[0m"
    print(f"{colors.get(color,'')}[DEBUG] {msg}{endc}")

def load_proxy():
    try:
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            proxy = f.read().strip()
            if proxy:
                return {"http": proxy, "https": proxy}
    except FileNotFoundError:
        pass
    return None

def random_user(length=10):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def request_with_retry(sess, method, url, **kwargs):
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
    log_debug("Trying GuerrillaMail...", "blue")
    r = request_with_retry(sess, "get", "https://api.guerrillamail.com/ajax.php?f=get_email_address")
    if not r:
        log_debug("GuerrillaMail failed: No response", "red")
        return None
    data = r.json()
    if "email_addr" not in data:
        log_debug("GuerrillaMail failed: No email address received", "red")
        return None
    log_debug(f"GuerrillaMail success: {data['email_addr']}", "green")
    return data["email_addr"], data["sid_token"]

def get_code_guerrilla(sess, sid_token):
    for _ in range(12):
        r = request_with_retry(sess, "get", f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={sid_token}")
        if r and r.json().get("list"):
            email_id = r.json()["list"][0]["mail_id"]
            msg = request_with_retry(sess, "get", f"https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id={email_id}&sid_token={sid_token}")
            match = re.findall(r"\d{6}", msg.json().get("mail_body", ""))
            if match:
                log_debug(f"Code received from GuerrillaMail: {match[0]}", "green")
                return match[0]
        time.sleep(3)
    log_debug("No code received from GuerrillaMail", "red")
    return None

def get_email_evp(sess):
    log_debug("Trying Evapmail...", "blue")
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'Content-Type': 'application/json'}
    json_data = {'deviceId': ''.join(random.choices(string.ascii_lowercase + string.digits, k=16)), 'expirationMinutes': 60}
    r = request_with_retry(sess, "post", 'https://api.evapmail.com/v1/accounts/create', json=json_data, headers=headers)
    if not r:
        log_debug("Evapmail failed: No response", "red")
        return None
    token = r.json().get('token')
    if not token:
        log_debug("Evapmail failed: No token", "red")
        return None
    log_debug(f"Evapmail success: {r.json()['email']}", "green")
    return r.json()['email'], token

def get_code_evp(sess, token):
    headers = {'User-Agent': 'Dart/3.5 (dart:io)', 'authorization': f'Bearer {token}'}
    for _ in range(12):
        r = request_with_retry(sess, "get", 'https://api.evapmail.com/v1/messages/inbox', headers=headers)
        if r and 'Instagram' in r.text:
            code = str(r.json()[0]["subject"])[:6]
            log_debug(f"Code received from Evapmail: {code}", "green")
            return code
        time.sleep(3)
    log_debug("No code received from Evapmail", "red")
    return None

def get_email_mailtm(sess):
    log_debug("Trying Mail.tm...", "blue")
    domain = sess.get("https://api.mail.tm/domains").json()["hydra:member"][0]["domain"]
    address = f"{random_user(10)}@{domain}"
    password = "Passw0rd!"
    sess.post("https://api.mail.tm/accounts", json={"address": address, "password": password})
    token_resp = sess.post("https://api.mail.tm/token", json={"address": address, "password": password})
    if token_resp.status_code != 200:
        log_debug("Mail.tm failed: Token error", "red")
        return None
    token = token_resp.json()["token"]
    log_debug(f"Mail.tm success: {address}", "green")
    return address, token

def get_code_mailtm(sess, token):
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(12):
        msgs = sess.get("https://api.mail.tm/messages", headers=headers).json()["hydra:member"]
        if msgs:
            code = re.findall(r"\d{6}", sess.get(f"https://api.mail.tm/messages/{msgs[0]['id']}", headers=headers).json()["text"])[0]
            log_debug(f"Code received from Mail.tm: {code}", "green")
            return code
        time.sleep(3)
    log_debug("No code received from Mail.tm", "red")
    return None

# ===== إنشاء الحساب =====
async def create_account():
    for attempt in range(3):
        log_debug(f"Attempt {attempt+1} to create account...", "yellow")
        result = await asyncio.get_event_loop().run_in_executor(None, sync_create_account)
        if result:
            return result
    return None

def sync_create_account():
    sess = requests.Session()
    proxy = load_proxy()
    if proxy:
        try:
            sess.proxies = proxy
            sess.get("https://www.google.com", timeout=5)
            log_debug("Proxy working", "green")
        except:
            sess.proxies = {}
            log_debug("Proxy failed, using direct connection", "red")

    request_with_retry(sess, "get", "https://www.instagram.com/accounts/emailsignup/")
    csrftoken = sess.cookies.get_dict().get("csrftoken")
    if not csrftoken:
        log_debug("Failed to get CSRF token", "red")
        return None

    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Ig-App-Id": "936619743392459",
        "X-Csrftoken": csrftoken,
        "Referer": "https://www.instagram.com/accounts/emailsignup/",
    }

    email_services = [
        (get_email_guerrilla, get_code_guerrilla),
        (get_email_evp, get_code_evp),
        (get_email_mailtm, get_code_mailtm),
    ]

    for email_func, code_func in email_services:
        email_data = email_func(sess)
        if email_data:
            email, token = email_data
            code = code_func(sess, token)
            if code:
                username = random_user(12)
                machine_id = ''.join(random.choice(string.hexdigits) for _ in range(16))

                request_with_retry(sess, "post", "https://www.instagram.com/api/v1/accounts/send_verify_email/",
                                   headers=headers, data={"device_id": machine_id, "email": email})

                resp_code = request_with_retry(sess, "post", "https://www.instagram.com/api/v1/accounts/check_confirmation_code/",
                                               headers=headers, data={"code": code, "device_id": machine_id, "email": email})
                if not resp_code or "signup_code" not in resp_code.json():
                    log_debug("Instagram rejected code", "red")
                    continue

                sn = resp_code.json()["signup_code"]
                resp_final = request_with_retry(sess, "post", "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/",
                                                headers=headers, data={
                                                    "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:0:{PASSWORD}",
                                                    "day": "22", "email": email, "first_name": "DEMAN", "month": "8",
                                                    "username": username, "year": "1995",
                                                    "client_id": machine_id, "tos_version": "row",
                                                    "force_sign_up_code": sn,
                                                })
                if resp_final and resp_final.json().get("account_created"):
                    log_debug(f"Account created: {username}", "green")
                    return email, username, PASSWORD
    log_debug("All email services failed", "red")
    return None

# ===== بوت تيليجرام =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("إنشاء حساب", callback_data="new_account")]]
    await update.message.reply_text("👋 أهلاً بك في أداة الإنشاء\n⚡ Powered by DEMAN.STORE", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "new_account":
        msg = await query.message.reply_text("⏳ بدء الإنشاء...\n⚡ Powered by DEMAN.STORE")
        result = await create_account()
        if result:
            email, username, password = result
            await msg.edit_text(
                f"🎉 الحساب جاهز!\n\n📧 Email: `{email}`\n👤 Username: `{username}`\n🔑 Password: `{password}`\n\n⚡ Powered by DEMAN.STORE",
                parse_mode="Markdown"
            )
        else:
            await msg.edit_text("❌ فشل إنشاء الحساب بعد عدة محاولات.\n⚡ Powered by DEMAN.STORE")

# ===== تشغيل البوت =====
def main():
    app_telegram = Application.builder().token(TOKEN).build()
    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(CallbackQueryHandler(button_handler))
    app_telegram.run_polling()

if __name__ == "__main__":
    main()
