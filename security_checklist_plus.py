#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_checklist_plus.py
InstaVido için genişletilmiş güvenlik denetimi.

Kullanım:
    $ python3 security_checklist_plus.py
"""

import os
import re
import sys
import stat
import json
import importlib
import traceback
from contextlib import suppress
from urllib.parse import urlparse

# ===== Pretty print helpers =====
COLORS = {
    "RESET": "\033[0m", "BOLD": "\033[1m",
    "GREEN": "\033[92m", "YELLOW": "\033[93m", "RED": "\033[91m",
    "BLUE": "\033[94m", "CYAN": "\033[96m", "GRAY": "\033[90m",
}
def ctext(s, c): return f"{COLORS.get(c,'')}{s}{COLORS['RESET']}"
def status_line(label, status, detail=""):
    mark = {"PASS":"GREEN","WARN":"YELLOW","FAIL":"RED"}[status]
    msg = f"{ctext('•','GRAY')} {ctext(label,'BOLD')}  {ctext(status,mark)}"
    if detail: msg += f"  {ctext(detail,'GRAY')}"
    print(msg)

# ===== Load Flask app =====
def try_import_app():
    candidates = []
    if os.path.exists("app.py"): candidates.append(("app", "app"))
    env_app = os.environ.get("FLASK_APP")
    if env_app:
        mod = env_app.replace(".py","").replace("/",".").replace("\\",".")
        candidates.append((mod, "app"))
    candidates.append(("wsgi", "application"))
    last_err = None
    for mod_name, attr in candidates:
        with suppress(Exception):
            mod = importlib.import_module(mod_name)
            app = getattr(mod, attr)
            return app
        if mod_name.endswith(".py") and os.path.exists(mod_name):
            spec = importlib.util.spec_from_file_location("app_auto", mod_name)
            if spec and spec.loader:
                m = importlib.util.module_from_spec(spec)
                with suppress(Exception):
                    spec.loader.exec_module(m) # type: ignore
                    app = getattr(m, attr)
                    return app
    raise RuntimeError(f"Flask app import edilemedi. Son hata: {last_err}")

# ===== Basic checks =====
def check_secret_key(app):
    sk = getattr(app, "secret_key", None) or app.config.get("SECRET_KEY")
    if not sk: return ("FAIL","SECRET_KEY boş.")
    if isinstance(sk,str) and len(sk) < 32: return ("WARN","SECRET_KEY kısa (>=32 önerilir).")
    # çok basit zayıflık tespiti
    low = (sk or "").lower()
    if any(x in low for x in ["secret","gizli","test","dev","key","password"]):
        return ("WARN","SECRET_KEY üretim için şüpheli görünüyor.")
    return ("PASS","")

def check_session_cookies(app):
    cfg = app.config
    issues = []
    if not cfg.get("SESSION_COOKIE_SECURE", False):
        issues.append("SESSION_COOKIE_SECURE=False")
    if not cfg.get("SESSION_COOKIE_HTTPONLY", True):
        issues.append("SESSION_COOKIE_HTTPONLY=False")
    samesite = cfg.get("SESSION_COOKIE_SAMESITE")
    if samesite not in ("Lax","Strict"):
        issues.append(f"SESSION_COOKIE_SAMESITE={samesite!r}")
    lifetime = cfg.get("PERMANENT_SESSION_LIFETIME")
    if lifetime and hasattr(lifetime,'total_seconds') and lifetime.total_seconds()<900:
        issues.append("PERMANENT_SESSION_LIFETIME < 15dk (fazla kısa olabilir)")
    return ("PASS","") if not issues else ("WARN", ", ".join(issues))

def check_security_headers_bulk(app):
    """
    Birden çok sayfada temel güvenlik başlıklarını kontrol eder.
    """
    targets = ["/", "/video", "/photo", "/reels", "/story"]
    missing = set()
    try:
        with app.test_client() as c:
            for path in targets:
                r = c.get(path, headers={"User-Agent":"SecCheck"})
                hdr = r.headers or {}
                needed = [
                    "Strict-Transport-Security",
                    "X-Frame-Options",
                    "X-Content-Type-Options",
                    "Referrer-Policy",
                    "Content-Security-Policy",
                    "Permissions-Policy",
                    "Cross-Origin-Resource-Policy",
                    "Cross-Origin-Opener-Policy",
                ]
                for h in needed:
                    if h not in hdr: missing.add(h)
    except Exception:
        return ("WARN","test_client çalışmadı (başlıklar ölçülemedi)")
    if missing:
        detail = "Eksik başlıklar: " + ", ".join(sorted(missing))
        return ("WARN", detail)
    return ("PASS","")

def check_routes_guard(app):
    """
    Bazı kritik route'ların akış guard'ları çalışıyor mu?
    /download -> from_load olmadan 200 dönmemeli (redirect olmalı)
    """
    try:
        with app.test_client() as c:
            r = c.get("/download")
            if r.status_code in (301,302,303,307,308):
                return ("PASS","/download uygun şekilde yönlendiriyor")
            if r.status_code == 200:
                return ("WARN","/download 200 döndü (akış guard'ı zayıf olabilir)")
            return ("PASS", f"/download status={r.status_code}")
    except Exception:
        return ("WARN","/download kontrolü yapılamadı")

def check_img_proxy_static(app):
    """
    img_proxy fonksiyonunda whitelist ve timeout var mı? (statik analiz)
    """
    vf = app.view_functions
    f = vf.get("img_pxy") or vf.get("img_proxy")
    if not f:
        return ("WARN","img_proxy route'u bulunamadı.")
    src_consts = f.__code__.co_consts or ()
    text = " ".join([s for s in src_consts if isinstance(s,str)])
    # ipuçları
    whitelist = bool(re.search(r"ALLOWED|WHITELIST|cdninstagram|fbcdn|instagram\.f", text, re.I))
    timeout   = bool(re.search(r"timeout\s*=\s*\d+", text))
    if whitelist and timeout:
        return ("PASS","whitelist/timeout izleri bulundu (manuel doğrula)")
    if whitelist and not timeout:
        return ("WARN","whitelist izi var; timeout izi yok")
    if not whitelist and timeout:
        return ("WARN","timeout var; whitelist yok (SSRF riski)")
    return ("WARN","whitelist/timeout izi yok (SSRF riski)")

def check_rate_limit_backend():
    has_redis = bool(os.getenv("REDIS_URL") or os.getenv("INSTAVIDO_REDIS_URL"))
    if has_redis:
        with suppress(Exception):
            import redis  # noqa
            return ("PASS","REDIS_URL set ve redis-py import edilebiliyor.")
        return ("WARN","REDIS_URL set ama redis-py import edilemiyor (pip install redis).")
    # dosya tabanlı ise dosya boyutu & izin bak
    rate_file = "/var/www/instavido/.rate_limits.json"
    if os.path.exists(rate_file):
        st = os.stat(rate_file)
        # 10MB'den büyükse uyar
        if st.st_size > 10*1024*1024:
            return ("WARN", f".rate_limits.json çok büyük ({st.st_size//1024}KB) — leak/temizlik gerekebilir.")
        # world-writable?
        if bool(st.st_mode & stat.S_IWOTH):
            return ("WARN",".rate_limits.json world-writable (izin sıkılaştır)")
    return ("WARN","Rate limit dosya tabanlı görünüyor. Redis önerilir.")

def check_session_dir(app):
    sessdir = app.config.get("SESSION_FILE_DIR")
    if not sessdir:
        return ("WARN","SESSION_FILE_DIR set değil (filesystem session kullanmıyor olabilirsiniz)")
    if not os.path.isdir(sessdir):
        return ("WARN", f"SESSION_FILE_DIR yok: {sessdir}")
    st = os.stat(sessdir)
    if bool(st.st_mode & stat.S_IWOTH):
        return ("WARN", f"{sessdir} world-writable (izinleri 750/700 yap)")
    return ("PASS","")

def check_files_permissions():
    issues=[]
    paths = [
        "./sessions.json", "./blocked_cookies.json",
        "/var/www/instavido/.rate_limits.json"
    ]
    for p in paths:
        if not os.path.exists(p): continue
        st=os.stat(p)
        if bool(st.st_mode & stat.S_IWOTH):
            issues.append(f"{p} world-writable")
        if st.st_size > 20*1024*1024:
            issues.append(f"{p} çok büyük ({st.st_size//1024}KB)")
    return ("PASS","") if not issues else ("WARN", "; ".join(issues))

def check_robots(app):
    try:
        with app.test_client() as c:
            r = c.get("/robots.txt")
            if r.status_code==200 and b"User-agent" in r.data:
                return ("PASS","")
            return ("WARN","robots.txt eksik/boş görünüyor")
    except Exception:
        return ("WARN","robots.txt kontrolü yapılamadı")

def main():
    try:
        app = try_import_app()
    except Exception as e:
        print(ctext("Flask app import hatası:","RED"), e)
        traceback.print_exc()
        sys.exit(2)

    print(ctext("InstaVido Genişletilmiş Güvenlik Checklist","BLUE"), ctext("(rapor)","GRAY"))
    print(ctext("=".ljust(64, "="), "GRAY"))

    checks = [
        ("SECRET_KEY",              check_secret_key(app)),
        ("Session Cookie Flags",    check_session_cookies(app)),
        ("Security Headers (çoklu)",check_security_headers_bulk(app)),
        ("/download kapı kontrolü", check_routes_guard(app)),
        ("img_proxy (statik analiz)",check_img_proxy_static(app)),
        ("Rate Limit Backend",      check_rate_limit_backend()),
        ("Session Dir izinleri",    check_session_dir(app)),
        ("Dosya izin/boyut",        check_files_permissions()),
        ("robots.txt",              check_robots(app)),
    ]

    worst=0
    for label,(st,detail) in checks:
        status_line(label, st, detail)
        worst=max(worst, 2 if st=="FAIL" else (1 if st=="WARN" else 0))

    print(ctext("=".ljust(64, "="), "GRAY"))
    if   worst==0: print(ctext("Özet: Temel + genişletilmiş kontroller temiz görünüyor. 👍","GREEN"))
    elif worst==1: print(ctext("Özet: İyileştirme gereken noktalar var. 🟡","YELLOW"))
    else:          print(ctext("Özet: Kritik eksikler mevcut. 🔴","RED"))
    sys.exit(worst)

if __name__ == "__main__":
    main()
