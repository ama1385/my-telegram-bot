import requests, random, string, time, re

PROXY_FILE = "proxy.txt"

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
