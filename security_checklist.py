#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_checklist.py
Flask tabanlı instavido uygulaması için güvenlik denetim script'i.

Kullanım:
    $ python3 security_checklist.py
Opsiyonel:
    $ FLASK_APP=app.py python3 security_checklist.py
"""

import os
import re
import sys
import types
import importlib
import traceback
from contextlib import suppress

COLORS = {
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GRAY": "\033[90m",
}

def ctext(s, c):
    return f"{COLORS.get(c,'')}{s}{COLORS['RESET']}"

def status_line(label, status, detail=""):
    if status == "PASS":
        mark = ctext("PASS", "GREEN")
    elif status == "WARN":
        mark = ctext("WARN", "YELLOW")
    else:
        mark = ctext("FAIL", "RED")
    msg = f"{ctext('•', 'GRAY')} {ctext(label, 'BOLD')}  {mark}"
    if detail:
        msg += f"  {ctext(detail, 'GRAY')}"
    print(msg)

def try_import_app():
    """
    app.py içinden 'app' isimli Flask uygulamasını import etmeyi dener.
    Başarısız olursa FLASK_APP ortam değişkenine bakar.
    """
    candidates = []

    # 1) app.py aynı dizinde mi?
    if os.path.exists("app.py"):
        candidates.append(("app", "app"))

    # 2) FLASK_APP verilmişse
    env_app = os.environ.get("FLASK_APP")
    if env_app:
        mod = env_app.replace(".py", "").replace("/", ".").replace("\\", ".")
        candidates.append((mod, "app"))

    # 3) common: src.app, wsgi:application vs.
    candidates.append(("wsgi", "application"))

    last_err = None
    for mod_name, attr in candidates:
        with suppress(Exception):
            mod = importlib.import_module(mod_name)
            app = getattr(mod, attr)
            return app

        # doğrudan dosya yolu denenebilir
        if mod_name.endswith(".py") and os.path.exists(mod_name):
            spec = importlib.util.spec_from_file_location("app_auto", mod_name)
            if spec and spec.loader:
                m = importlib.util.module_from_spec(spec)
                with suppress(Exception):
                    spec.loader.exec_module(m)  # type: ignore
                    app = getattr(m, attr)
                    return app
    raise RuntimeError(f"Flask app import edilemedi. Son hata: {last_err}")

def check_secret_key(app):
    sk = getattr(app, "secret_key", None) or app.config.get("SECRET_KEY")
    if not sk:
        return ("FAIL", "SECRET_KEY boş.")
    if isinstance(sk, str) and len(sk) < 32:
        return ("WARN", "SECRET_KEY kısa (>=32 önerilir).")
    # default/development anahtarlarını yakalamaya çalış
    lowersk = (sk or "").lower()
    if "gizli" in lowersk or "secret" in lowersk or "test" in lowersk:
        return ("WARN", "SECRET_KEY üretim için şüpheli görünüyor.")
    return ("PASS", "")

def check_debug(app):
    if getattr(app, "debug", False):
        return ("FAIL", "DEBUG açık. Prod’da kapalı olmalı.")
    return ("PASS", "")

def check_session_cookies(app):
    cfg = app.config
    issues = []
    if not cfg.get("SESSION_COOKIE_SECURE", False):
        issues.append("SESSION_COOKIE_SECURE=False")
    if not cfg.get("SESSION_COOKIE_HTTPONLY", True):
        issues.append("SESSION_COOKIE_HTTPONLY=False")
    samesite = cfg.get("SESSION_COOKIE_SAMESITE", "Lax")
    if samesite not in ("Lax", "Strict"):
        issues.append(f"SESSION_COOKIE_SAMESITE={samesite!r}")
    if issues:
        return ("WARN", ", ".join(issues))
    return ("PASS", "")

def check_recaptcha_env():
    site = os.getenv("RECAPTCHA_SITE_KEY", "").strip()
    sec  = os.getenv("RECAPTCHA_SECRET", "").strip()
    if not site or not sec:
        return ("WARN", "reCAPTCHA anahtarları boş (RECAPTCHA_SITE_KEY, RECAPTCHA_SECRET).")
    return ("PASS", "")

def check_routes(app):
    # /__dbg_profile sadece debug’ta açık olmalı
    rules = {str(r.rule): r for r in app.url_map.iter_rules()}
    if "/__dbg_profile/<username>" in rules and not app.debug:
        return ("WARN", "/__dbg_profile üretimde açık görünüyor.")
    return ("PASS", "")

def check_security_headers(app):
    """
    Test client ile anasayfa isteği atıp standart başlıkları kontrol eder.
    """
    try:
        with app.test_client() as c:
            r = c.get("/", headers={"User-Agent": "SecCheck"})
            hdr = r.headers
    except Exception:
        # fallback: boş response gibi değerlendir
        hdr = {}

    reqs = {
        "Strict-Transport-Security": ("WARN", "HSTS yok. (prod https üstünde ekle)"),
        "X-Frame-Options": ("WARN", "X-Frame-Options yok. (SAMEORIGIN önerilir)"),
        "X-Content-Type-Options": ("WARN", "X-Content-Type-Options yok. (nosniff)"),
        "Referrer-Policy": ("WARN", "Referrer-Policy yok. (strict-origin-when-cross-origin önerilir)"),
        "Content-Security-Policy": ("WARN", "CSP yok. En azından img/media için kaynaklar kısıtlanmalı."),
    }
    worst = "PASS"
    notes = []
    for key, (sev, note) in reqs.items():
        if key not in hdr:
            worst = "FAIL" if sev == "FAIL" else ("WARN" if worst == "PASS" else worst)
            notes.append(note)

    if notes:
        return ("WARN", " | ".join(notes))
    return ("PASS", "")

def check_img_proxy_rules(app):
    """
    img_proxy’nin domain whitelist’i var mı? (route fonksiyon adına göre kaba kontrol)
    """
    view_funcs = app.view_functions
    f = view_funcs.get("img_pxy") or view_funcs.get("img_proxy")
    if not f:
        return ("WARN", "img_proxy route’u bulunamadı (varsa adı farklı).")
    src = (f.__code__.co_consts or ())
    txt = " ".join([s for s in src if isinstance(s, str)])
    # basit bir whitelisting ipucu arayalım
    if re.search(r"ALLOWED|WHITELIST|cdninstagram|fbcdn", txt, re.IGNORECASE):
        return ("PASS", "")
    return ("WARN", "img_proxy içinde domain whitelist görünmüyor (SSRF riski).")

def check_download_proxy(app):
    vf = app.view_functions
    if "proxy_download" in vf:
        return ("PASS", "")
    return ("WARN", "proxy_download route’u yok (indir linki yeni sekme açabilir).")

def check_rate_limit_backend():
    # Redis var mı? Yoksa dosya tabanlı mı?
    has_redis_url = bool(os.getenv("REDIS_URL") or os.getenv("INSTAVIDO_REDIS_URL"))
    if has_redis_url:
        # redis-py kurulu mu?
        try:
            import redis  # noqa: F401
            return ("PASS", "REDIS_URL var ve redis-py import edilebiliyor.")
        except Exception:
            return ("WARN", "REDIS_URL var ama redis-py import edilemedi (pip install redis).")
    else:
        # dosya tabanlı limiter uyarısı
        return ("WARN", "Rate limit dosya tabanlı görünüyor (eşzamanlı yükte kırılgan). Redis önerilir.")

def check_robots(app):
    try:
        with app.test_client() as c:
            r = c.get("/robots.txt")
            if r.status_code == 200 and b"User-agent" in r.data:
                return ("PASS", "")
            return ("WARN", "robots.txt eksik veya boş.")
    except Exception:
        return ("WARN", "robots.txt kontrolü yapılamadı.")

def main():
    try:
        app = try_import_app()
    except Exception as e:
        print(ctext("Flask app import hatası:", "RED"), e)
        traceback.print_exc()
        sys.exit(2)

    print(ctext("InstaVido Güvenlik Checklist", "BLUE"), ctext("(rapor)", "GRAY"))
    print(ctext("=".ljust(48, "="), "GRAY"))

    checks = [
        ("SECRET_KEY",           check_secret_key(app)),
        ("DEBUG",                check_debug(app)),
        ("Session Cookie Flags", check_session_cookies(app)),
        ("reCAPTCHA Env",        check_recaptcha_env()),
        ("Routes",               check_routes(app)),
        ("Security Headers",     check_security_headers(app)),
        ("img_proxy Whitelist",  check_img_proxy_rules(app)),
        ("proxy_download",       check_download_proxy(app)),
        ("Rate Limit Backend",   check_rate_limit_backend()),
        ("robots.txt",           check_robots(app)),
    ]
    worst_exit = 0
    for label, (st, detail) in checks:
        status_line(label, st, detail)
        worst_exit = max(worst_exit, 1 if st == "WARN" else (2 if st == "FAIL" else 0))

    print(ctext("=".ljust(48, "="), "GRAY"))
    if worst_exit == 0:
        print(ctext("Özet: Tüm temel kontroller geçti. 👍", "GREEN"))
    elif worst_exit == 1:
        print(ctext("Özet: İyileştirme gereken noktalar var. 🟡", "YELLOW"))
    else:
        print(ctext("Özet: Kritik eksikler mevcut. 🔴", "RED"))
    sys.exit(worst_exit)

if __name__ == "__main__":
    main()
