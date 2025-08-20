import os, json, time, re, requests

BASE_URL = "https://instavido.com"  # kendi domainin
TIMEOUT = 12

def ok(s):  print("✅", s)
def warn(s):print("⚠️", s)
def info(s):print("ℹ️", s)

def env_checks():
    print("\n[ENV]")
    img = os.getenv("IMG_PROXY_SECRET","")
    med = os.getenv("MEDIA_PROXY_SECRET","")
    if img and len(img) >= 32: ok("IMG_PROXY_SECRET var/uzun.")
    else: warn("IMG_PROXY_SECRET eksik veya kısa!")
    if med and len(med) >= 32: ok("MEDIA_PROXY_SECRET var/uzun.")
    else: warn("MEDIA_PROXY_SECRET eksik veya kısa!")
    sec = os.getenv("ENV","").lower() == "prod"
    if sec: ok("ENV=prod")
    else: info("ENV prod değil (lokalde normal).")

def headers_checks():
    print("\n[HTTP Headers]")
    r = requests.get(BASE_URL, timeout=TIMEOUT)
    need = {
        "Strict-Transport-Security":"HSTS",
        "X-Frame-Options":"SAMEORIGIN",
        "X-Content-Type-Options":"nosniff",
        "Referrer-Policy":"strict-origin-when-cross-origin",
        "Content-Security-Policy":"CSP",
        "Permissions-Policy":"Permissions-Policy",
        "Cross-Origin-Resource-Policy":"CORP",
        "Cross-Origin-Opener-Policy":"COOP",
    }
    for k,desc in need.items():
        if k in r.headers: ok(f"{k} ({desc}) mevcut.")
        else: warn(f"{k} ({desc}) eksik!")

def session_cookie_flags():
    print("\n[Session Cookie]")
    r = requests.get(BASE_URL, timeout=TIMEOUT)
    # Basit kontrol
    sc = False
    for c in r.cookies:
        if getattr(c, "secure", False):
            sc = True
    if sc: ok("Session cookie Secure (HttpOnly sunucu set eder).")
    else: warn("Session cookie Secure görünmüyor!")

def img_proxy_signed_test():
    print("\n[img_proxy imza testi]")
    # İmzasız dene → 403 bekliyoruz
    url = BASE_URL + "/img_proxy?url=https://i.imgur.com/mrPrxpV.jpeg"
    r = requests.get(url, timeout=TIMEOUT)
    if r.status_code == 403:
        ok("img_proxy imzasız istek reddedildi (403).")
    else:
        warn(f"img_proxy imzasız istek {r.status_code} döndü (403 olmalı).")

def referer_guard_test():
    print("\n[Referer/Origin Guard (opsiyonel)]")
    # Eğer korumayı eklediysen bu test 403 verecek.
    url = BASE_URL + "/proxy_download?url=https://example.com/x.mp4&fn=x.mp4"
    r = requests.get(url, timeout=TIMEOUT, headers={"Referer":"https://evil.example"})
    if r.status_code in (401,403):
        ok("proxy_download referer/origin guard çalışıyor.")
    else:
        info(f"proxy_download referer guard uygulanmamış olabilir (status={r.status_code}).")

def run_all():
    print("\n🔍 InstaVido Güvenlik Suite\n" + "="*50)
    env_checks()
    headers_checks()
    session_cookie_flags()
    img_proxy_signed_test()
    referer_guard_test()
    print("="*50 + "\n✅ Bitti.")

if __name__ == "__main__":
    run_all()
