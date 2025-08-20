import os
import re
import requests
from urllib.parse import urljoin

BASE_URL = "https://instavido.com"  # Buraya kendi domainini yaz
EXPECTED_HEADERS = {
    "Strict-Transport-Security": "HSTS",
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "CSP",
}

def check_env_keys():
    img_key = os.environ.get("IMG_PROXY_SECRET")
    media_key = os.environ.get("MEDIA_PROXY_SECRET")
    if img_key and len(img_key) >= 32:
        print("✅ ENV: IMG_PROXY_SECRET güvenli.")
    else:
        print("⚠️ ENV: IMG_PROXY_SECRET eksik veya kısa!")
    if media_key and len(media_key) >= 32:
        print("✅ ENV: MEDIA_PROXY_SECRET güvenli.")
    else:
        print("⚠️ ENV: MEDIA_PROXY_SECRET eksik veya kısa!")

def check_headers():
    resp = requests.get(BASE_URL, timeout=10)
    for header, desc in EXPECTED_HEADERS.items():
        if header in resp.headers:
            print(f"✅ {header} ({desc}) mevcut.")
        else:
            print(f"⚠️ {header} ({desc}) eksik!")

def check_img_proxy():
    test_url = BASE_URL + "/img_proxy?url=https://i.imgur.com/mrPrxpV.jpeg"
    resp = requests.get(test_url, timeout=10)
    if resp.status_code == 403:
        print("✅ img_proxy imzasız istek reddedildi (SSRF koruması aktif).")
    elif resp.status_code == 200:
        print("⚠️ img_proxy imzasız istek hala çalışıyor! (Acil sertleştirme lazım)")
    else:
        print(f"ℹ️ img_proxy farklı yanıt döndü: {resp.status_code}")

def check_session_cookie():
    resp = requests.get(BASE_URL, timeout=10)
    cookie_flags_ok = False
    for cookie in resp.cookies:
        if cookie.secure and cookie.has_nonstandard_attr("HttpOnly"):
            cookie_flags_ok = True
    if cookie_flags_ok:
        print("✅ Session cookie Secure+HttpOnly.")
    else:
        print("⚠️ Session cookie flags eksik!")

def run_all():
    print("\n🔍 Tam Kapsamlı InstaVido Güvenlik Testi\n" + "="*50)
    check_env_keys()
    check_headers()
    check_img_proxy()
    check_session_cookie()
    print("="*50 + "\n✅ Test tamamlandı.")

if __name__ == "__main__":
    run_all()
