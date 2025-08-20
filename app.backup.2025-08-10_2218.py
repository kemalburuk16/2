# app.py
from seo_instavido.seo_utils import get_meta
from adminpanel.views import admin_bp
import adminpanel  # admin_bp ve tüm admin route'larını yükler (views, ads_views)
import os, re, json, time, io, logging, requests
from typing import Optional, Dict, Any, Tuple, List
from session_logger import log_session_use, notify_download, update_session_counters
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, Response, send_file, jsonify
)
from flask_session import Session
from flask_babelex import Babel, _
from adminpanel.blacklist_admin import blacklist_admin_bp

# --- ENTEGRE --- #
from session_logger import log_session_use, notify_download

# ===================== Güvenlik & reCAPTCHA & Limitler =====================

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "").strip()
RECAPTCHA_SECRET   = os.getenv("RECAPTCHA_SECRET", "").strip()

RATE_FILE = "/var/www/instavido/.rate_limits.json"
os.makedirs(os.path.dirname(RATE_FILE), exist_ok=True)
if not os.path.exists(RATE_FILE):
    with open(RATE_FILE, "w") as f:
        json.dump({}, f)

class SimpleLimiter:
    """
    Dakika başına max ve burst limiti uygular.
    Döner: (allowed: bool, need_captcha: bool)
    """
    def __init__(self, window_seconds=60, max_requests=60, burst=80):
        self.window = window_seconds
        self.max = max_requests
        self.burst = burst

    def hit(self, key: str):
        now = int(time.time())
        try:
            with open(RATE_FILE, "r+") as f:
                data = json.load(f)
                arr = data.get(key, [])
                arr = [t for t in arr if t > now - self.window]
                arr.append(now)
                data[key] = arr
                f.seek(0)
                json.dump(data, f)
                f.truncate()
            count = len(arr)
            if count > self.burst:
                return (False, True)   # captcha duvarı
            if count > self.max:
                return (False, False)  # kısa blok
            return (True, False)
        except Exception:
            return (True, False)

limiter = SimpleLimiter(window_seconds=60, max_requests=60, burst=80)

# Kara liste dosyası
BLACKLIST_PATH = "/var/www/instavido/adminpanel/data/blacklist.json"

def _load_blacklist():
    if not os.path.exists(BLACKLIST_PATH):
        return {"profiles": [], "links": []}
    try:
        with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"profiles": [], "links": []}

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _is_blocked(target: str) -> bool:
    if not target:
        return False
    bl = _load_blacklist()
    t = _norm(target)
    profs = [_norm(x) for x in bl.get("profiles", [])]
    links  = [_norm(x) for x in bl.get("links", [])]
    return t in profs or t in links

def _recaptcha_verify(token: str, remote_ip: str) -> bool:
    if not (RECAPTCHA_SECRET and token):
        return False
    try:
        r = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": RECAPTCHA_SECRET, "response": token, "remoteip": remote_ip},
            timeout=10
        )
        j = r.json()
        return bool(j.get("success"))
    except Exception:
        return False

def _ensure_gate(lang):
    if not session.get("gate_passed"):
        if not request.path.startswith(f"/{lang}/gate"):
            nxt = request.url
            return redirect(url_for("gate", lang=lang, next=nxt))
    return None

def _ensure_not_blacklisted():
    target = session.get("last_target", "")
    if _is_blocked(target):
        return render_template("policies/blocked.html", target=target), 200
    return None

def _enforce_rate_limit(suffix=""):
    now = time.time()
    if session.get("captcha_ok_until", 0) > now:
        return None
    ip  = (request.headers.get("X-Forwarded-For", request.remote_addr) or "0.0.0.0").split(",")[0].strip()
    key = f"ip:{ip}{suffix}"
    allowed, need_captcha = limiter.hit(key)
    if allowed:
        return None
    if need_captcha:
        return render_template("policies/captcha_wall.html", sitekey=RECAPTCHA_SITE_KEY), 429
    return (_("Too many requests. Please slow down."), 429)

# =============================================================================

# ---- Sabitler --------------------------------------------------------------
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
BLOCKED_COOKIES_PATH = os.path.join(BASE_DIR, "blocked_cookies.json")
SESSION_IDX_PATH = os.path.join(BASE_DIR, "session_index.txt")
SESSIONS_PATH = os.path.join(BASE_DIR, "sessions.json")
SESSION_DIR   = os.path.join(BASE_DIR, ".flask_session")
IG_APP_ID     = "1217981644879628"
UA_MOBILE     = "Instagram 298.0.0.0.0 Android"
UA_DESKTOP    = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---- Flask & Babel ---------------------------------------------------------
app = Flask(__name__)
app.secret_key = 'instavido-süper-gizli-key-2024'
app.config.update(
    SESSION_TYPE        = "filesystem",
    SESSION_FILE_DIR    = SESSION_DIR,
    SESSION_PERMANENT   = True,
    SESSION_USE_SIGNER  = True,
    SESSION_COOKIE_NAME = "instavido_session",
)
os.makedirs(SESSION_DIR, exist_ok=True)
Session(app)
app.url_map.strict_slashes = False

# --- Ads runtime (server-side fallback) ---
try:
    from ads_manager import ad_html as _ad_func
    app.jinja_env.globals.update(ad_html=_ad_func, get_ad=_ad_func)
except Exception:
    pass

# Logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.DEBUG)

app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(BASE_DIR, "translations")
babel = Babel(app)
LANGUAGES = ['en', 'tr', 'hi', 'de', 'fr', 'ko', 'ar', 'es']
app.jinja_env.globals.update(LANGUAGES=LANGUAGES)

# --------------------------------------------------------------------------- #
#  DİL SEÇİMİ                                                                 #
# --------------------------------------------------------------------------- #
@babel.localeselector
def get_locale():
    segments = request.path.strip('/').split('/')
    if segments and segments[0] in LANGUAGES:
        return segments[0]
    if request.view_args and 'lang' in request.view_args and request.view_args['lang'] in LANGUAGES:
        return request.view_args['lang']
    if request.args.get('lang') in LANGUAGES:
        return request.args.get('lang')
    return 'en'

# --- DİL VE META, MENÜ, OTOMATİK SEO CONTEXT ---
PAGE_ROUTES = [
    ('index', 'index.html'),
    ('video', 'video.html'),
    ('photo', 'photo.html'),
    ('reels', 'reels.html'),
    ('igtv', 'igtv.html'),
    ('story', 'story.html'),
    ('privacy', 'privacy.html'),
    ('terms', 'terms.html'),
    ('contact', 'contact.html'),
]

@app.context_processor
def inject_globals():
    lang = get_locale()
    try:
        page = request.endpoint if request.endpoint in dict(PAGE_ROUTES) else "index"
        meta = get_meta(page, lang)
    except Exception:
        meta = {}
    nav_links = [
        {
            'endpoint': page,
            'url': url_for(page, lang=lang),
            'name': _(page.capitalize())
        }
        for page, tmpl in PAGE_ROUTES
        if page not in ('privacy', 'terms', 'contact')
    ]
    return dict(meta=meta,
                nav_links=nav_links,
                get_locale=get_locale,
                LANGUAGES=LANGUAGES,
                RECAPTCHA_SITE_KEY=RECAPTCHA_SITE_KEY)

# >>> MEDIA STATE TEMİZLEYİCİ
def _clear_media_state():
    for k in [
        "video_url","image_urls","thumbnail_url","raw_comments","video_title",
        "stories","username",
        "from_story","from_idx","from_video","from_fotograf","from_reels","from_igtv","from_load",
        "download_error"
    ]:
        session.pop(k, None)

@app.before_request
def _refresh():
    session.permanent = True
    now  = time.time()
    last = session.get("last", now)
    if now - last > 900:
        session.clear()
    session["last"] = now
    try:
        if request.cookies.get("age_ok") == "1":
            session["gate_passed"] = True
    except Exception:
        pass

# ----------------------------- Gate Route ------------------------------
@app.route("/<lang>/gate", methods=["GET","POST"])
def gate(lang):
    nxt = request.args.get("next") or request.form.get("next") or url_for("index", lang=lang)
    if request.method == "POST":
        if request.form.get("age13") == "on" and request.form.get("terms") == "on":
            session["gate_passed"] = True
            resp = redirect(nxt)
            try:
                resp.set_cookie(
                    "age_ok", "1",
                    max_age=60*60*24*365,
                    secure=True,
                    samesite="Lax"
                )
            except Exception:
                pass
            return resp
    return render_template("policies/gate.html", lang=lang, next=nxt)

# ------------------------- reCAPTCHA Doğrulama -------------------------
@app.route("/captcha/verify", methods=["POST"])
def captcha_verify():
    token = request.form.get("g-recaptcha-response", "") or request.form.get("recaptcha_token", "")
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()
    if RECAPTCHA_SECRET and _recaptcha_verify(token, ip):
        session["captcha_ok_until"] = time.time() + 60*30
        nxt = request.form.get("next") or url_for("index", lang=get_locale())
        return redirect(nxt)
    return render_template("policies/captcha_wall.html", sitekey=RECAPTCHA_SITE_KEY), 400

# --------------------------------------------------------------------------- #
#  Yardımcılar                                                                #
# --------------------------------------------------------------------------- #
def block_session(sessionid, duration_sec=1800):
    now = time.time()
    blocked_until = now + duration_sec
    entry = {"sessionid": sessionid, "blocked_until": blocked_until}
    lst = []
    if os.path.exists(BLOCKED_COOKIES_PATH):
        with open(BLOCKED_COOKIES_PATH, encoding="utf-8") as f:
            try:
                lst = json.load(f)
            except:
                lst = []
    lst = [b for b in lst if b.get("blocked_until", 0) > now]
    if sessionid not in [b.get("sessionid") for b in lst]:
        lst.append(entry)
    with open(BLOCKED_COOKIES_PATH, "w", encoding="utf-8") as f:
        json.dump(lst, f, indent=2)

def _cookie_pool():
    if not os.path.exists(SESSIONS_PATH):
        return []
    with open(SESSIONS_PATH, encoding="utf-8") as f:
        sessions = json.load(f)
    blocked_ids = set()
    now = time.time()
    if os.path.exists(BLOCKED_COOKIES_PATH):
        with open(BLOCKED_COOKIES_PATH, encoding="utf-8") as f:
            for entry in json.load(f):
                if entry.get("blocked_until", 0) > now:
                    blocked_ids.add(entry.get("sessionid"))
    pool = [
        s for s in sessions
        if s.get("status", "active") == "active"
        and s.get("sessionid") not in blocked_ids
        and s.get("session_key") is not None
    ]
    pool.sort(key=lambda s: int(s["session_key"]))
    return pool

def get_next_session():
    pool = _cookie_pool()
    if not pool:
        return None
    idx = 0
    if os.path.exists(SESSION_IDX_PATH):
        try:
            with open(SESSION_IDX_PATH, "r") as f:
                idx = int(f.read().strip())
        except Exception:
            idx = 0
    idx = (idx + 1) % len(pool)
    with open(SESSION_IDX_PATH, "w") as f:
        f.write(str(idx))
    return pool[idx]

def _build_headers(extra: Optional[Dict[str, str]] = None, html: bool=False) -> Dict[str, str]:
    h = {
        "User-Agent": UA_DESKTOP if html else UA_MOBILE,
        "X-IG-App-ID": IG_APP_ID if not html else "936619743392459",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/"
    }
    if html:
        h.pop("X-IG-App-ID", None)
        h["Sec-Fetch-Mode"] = "navigate"
        h["Sec-Fetch-Dest"] = "document"
    if extra: h.update(extra)
    return h

def _http_get(url: str, cookies: Optional[Dict[str, str]]=None, html: bool=False, timeout: int=12):
    return requests.get(url, headers=_build_headers(html=html), cookies=cookies or {}, timeout=timeout)

# --------------------------------------------------------------------------- #
#  PROFILE Yardımcıları                                                       #
# --------------------------------------------------------------------------- #
def _parse_username_or_url(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    m = re.search(r"(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)(?:/)?$", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_.]{2,30}", s):
        return s
    return None

def _extract_video_url_from_gql(j: dict) -> Optional[str]:
    info = (
        j.get("data", {}).get("xdt_shortcode_media")
        or j.get("data", {}).get("shortcode_media") or {}
    )
    if not info:
        return None

    if (info.get("__typename", "").lower().endswith("video")):
        return (info.get("video_url")
                or (info.get("video_resources") or [{}])[0].get("src"))

    if "sidecar" in (info.get("__typename", "").lower()):
        for edge in info.get("edge_sidecar_to_children", {}).get("edges", []):
            node = edge.get("node", {})
            if node.get("__typename", "").lower().endswith("video"):
                return (node.get("video_url")
                        or (node.get("video_resources") or [{}])[0].get("src"))
    return None

def _extract_object_from(text: str, key: str) -> Optional[dict]:
    """
    text içinde '"<key>":{' veya '[' ile başlayan JSON’u
    parantez sayarak güvenli çıkarır. Döner: { key: ... } sözlüğü.
    """
    try:
        anchor = f'"{key}":'
        i = text.find(anchor)
        if i == -1:
            return None
        j = i + len(anchor)
        while j < len(text) and text[j] not in "{[":
            j += 1
        if j >= len(text):
            return None
        open_char = text[j]
        close_char = "}" if open_char == "{" else "]"
        depth, k = 0, j
        while k < len(text):
            c = text[k]
            if c == open_char:
                depth += 1
            elif c == close_char:
                depth -= 1
                if depth == 0:
                    blob = text[i:k+1]  # '"key":{...}' veya '"key":[...]'
                    js = "{" + blob + "}"
                    js = js.replace("\\u0026", "&").replace("\\/", "/")
                    return json.loads(js)
            k += 1
        return None
    except Exception as ex:
        logging.exception(f"_extract_object_from error: {ex}")
        return None

def _profile_html_fallback(username: str):
    """
    Cookie yoksa: https://www.instagram.com/<username>/ HTML’inden
    edge_owner_to_timeline_media’yı brace‑count ile çek.
    Döner: (profile_dict, posts_list, reels_list)
    """
    try:
        url = f"https://www.instagram.com/{username}/"
        r = _http_get(url, html=True)
        if r.status_code != 200:
            return None, [], []

        html = r.text

        avatar = None
        mava = re.search(r'"profile_pic_url_hd"\s*:\s*"([^"]+)"', html)
        if mava:
            avatar = mava.group(1).encode('utf-8').decode('unicode_escape')

        obj = _extract_object_from(html, "edge_owner_to_timeline_media")
        if not obj:
            return None, [], []

        media = obj.get("edge_owner_to_timeline_media", {})
        edges = (media.get("edges") or [])[:24]

        posts, reels = [], []
        for e in edges:
            node = (e or {}).get("node", {}) or {}
            is_video = bool(node.get("is_video"))
            display = node.get("display_url") or node.get("thumbnail_src") or ""
            caption = ""
            try:
                cap_edges = (node.get("edge_media_to_caption", {}).get("edges") or [])
                if cap_edges:
                    caption = (cap_edges[0].get("node", {}) or {}).get("text", "")
            except Exception:
                pass

            likes = (
                (node.get("edge_liked_by", {}) or {}).get("count")
                or (node.get("edge_media_preview_like", {}) or {}).get("count")
                or 0
            )
            comments = (node.get("edge_media_to_comment", {}) or {}).get("count", 0)
            views = (node.get("video_view_count") if is_video else 0) or 0
            ts = node.get("taken_at_timestamp") or 0

            item = {
                "type": "video" if is_video else "image",
                "url": display,
                "thumb": display,
                "caption": (caption or "")[:160],
                "download_url": display,
                "like_count": int(likes or 0),
                "comment_count": int(comments or 0),
                "view_count": int(views or 0),
                "timestamp": int(ts or 0)
            }
            posts.append(item)
            if is_video:
                reels.append(item)

        profile = {
            "username": username,
            "full_name": "",
            "avatar": avatar,
            "followers": 0,
            "following": 0,
            "posts_count": len(posts),
            "bio": "",
            "external_url": f"https://instagram.com/{username}"
        }

        return (profile, posts, reels)
    except Exception as ex:
        logging.exception(f"_profile_html_fallback error for {username}: {ex}")
        return None, [], []

def _get_uid(username: str) -> Optional[str]:
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    for s in _cookie_pool():
        ck = {k: s.get(k, "") for k in ("sessionid", "ds_user_id", "csrftoken")}
        try:
            r = requests.get(url, headers=_build_headers(), cookies=ck, timeout=10)
            if r.status_code == 200 and "user" in r.text:
                return r.json()["data"]["user"]["id"]
        except Exception:
            continue
    try:
        r = _http_get(f"https://www.instagram.com/{username}/", html=True)
        m = re.search(r'"profilePage_(\d+)"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def _get_profile_data(username: str):
    """
    Profil üst bilgileri + ilk medya sayfaları (post'lar) getirir.
    Cookie başarısızsa HTML fallback devreye girer → posts & reels dolar.
    """
    uid = _get_uid(username)

    user = None
    posts, reels = [], []
    profile = None

    pool = _cookie_pool()
    if pool:
        try:
            url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
            for s in pool:
                ck = {k: s.get(k, "") for k in ("sessionid", "ds_user_id", "csrftoken")}
                r = requests.get(url, headers=_build_headers(), cookies=ck, timeout=10)
                if r.status_code == 200 and "user" in r.text:
                    user = r.json()["data"]["user"]
                    break
        except Exception:
            user = None

    if user:
        profile = {
            "username": user.get("username"),
            "full_name": user.get("full_name") or "",
            "avatar": user.get("profile_pic_url_hd") or user.get("profile_pic_url"),
            "followers": user.get("edge_followed_by", {}).get("count", 0),
            "following": user.get("edge_follow", {}).get("count", 0),
            "posts_count": user.get("edge_owner_to_timeline_media", {}).get("count", 0),
            "bio": (user.get("biography") or "").strip(),
            "external_url": user.get("external_url") or f"https://instagram.com/{user.get('username','')}"
        }

        edges = (user.get("edge_owner_to_timeline_media", {}).get("edges") or [])[:24]
        for e in edges:
            node = e.get("node", {}) or {}
            sc = node.get("shortcode")
            is_video = bool(node.get("is_video"))
            display = node.get("display_url") or node.get("thumbnail_src") or ""
            caption = ""
            try:
                caption = (node.get("edge_media_to_caption", {}).get("edges") or [{}])[0].get("node", {}).get("text", "")
            except Exception:
                pass

            likes = (
                node.get("edge_liked_by", {}).get("count") or
                node.get("edge_media_preview_like", {}).get("count") or 0
            )
            comments = (node.get("edge_media_to_comment", {}).get("count") or 0)
            views = (node.get("video_view_count") if is_video else 0) or 0
            ts = node.get("taken_at_timestamp") or 0

            item = {
                "type": "video" if is_video else "image",
                "url": display,
                "thumb": display,
                "caption": (caption or "")[:160],
                "download_url": display,
                "like_count": int(likes or 0),
                "comment_count": int(comments or 0),
                "view_count": int(views or 0),
                "timestamp": int(ts or 0)
            }

            if is_video and sc:
                gql = _gql_url(sc)
                data, _sused = _fetch_media(gql)
                vurl = _extract_video_url_from_gql(data or {}) if data else None
                if vurl:
                    item["url"] = vurl
                    item["download_url"] = vurl
                reels.append(item)

            posts.append(item)

    if not posts:
        prof_fb, posts_fb, reels_fb = _profile_html_fallback(username)
        if prof_fb:
            profile = profile or prof_fb
        posts = posts or posts_fb
        reels = reels or reels_fb

    stories = []
    if uid:
        st_raw, _sess = _get_stories(uid)
        if st_raw:
            for it in st_raw:
                stories.append({
                    "type": it.get("type"),
                    "url": it.get("media_url"),
                    "thumb": it.get("thumb"),
                    "caption": ""
                })

    highlights = _get_highlights(uid) if uid else []
    if not highlights:
        highlights = []

    if not profile:
        profile = {
            "username": username,
            "full_name": "",
            "avatar": None,
            "followers": 0,
            "following": 0,
            "posts_count": len(posts),
            "bio": "",
            "external_url": f"https://instagram.com/{username}"
        }

    sections = {
        "posts": posts,
        "stories": stories,
        "highlights": highlights,
        "reels": reels or [i for i in posts if i.get("type") == "video"]
    }
    return profile, sections

# --------------------------------------------------------------------------- #
#  STORY İşlevleri                                                            #
# --------------------------------------------------------------------------- #
def _get_stories(uid: str):
    pool = _cookie_pool()
    pool_len = len(pool)
    if pool_len == 0:
        return None, None

    endpoints = [
        f"https://i.instagram.com/api/v1/feed/reels_media/?reel_ids={uid}",
        f"https://i.instagram.com/api/v1/feed/user/{uid}/reel_media/"
    ]

    last_key = None
    if os.path.exists(SESSION_IDX_PATH):
        with open(SESSION_IDX_PATH, "r") as f:
            last_key = f.read().strip()
    keys = [s["session_key"] for s in pool]
    idx = 0
    if last_key and last_key in keys:
        idx = (keys.index(last_key) + 1) % len(pool)

    for offset in range(pool_len):
        real_idx = (idx + offset) % pool_len
        s = pool[real_idx]
        for url in endpoints:
            ck = {
                "sessionid":  s.get("sessionid", ""),
                "ds_user_id": s.get("ds_user_id", ""),
                "csrftoken":  s.get("csrftoken", "")
            }
            headers = _build_headers({"X-CSRFToken": ck["csrftoken"]})
            try:
                r = requests.get(url, headers=headers, cookies=ck, timeout=10)
                if r.status_code == 200:
                    j = r.json()
                    items = []
                    if "reels_media" in j:
                        items = j["reels_media"][0].get("items", [])
                    else:
                        items = j.get("items", [])
                    if not items:
                        continue
                    stories = []
                    for it in items:
                        thumb = it.get("image_versions2", {}) \
                                  .get("candidates", [{}])[0] \
                                  .get("url", "")
                        if "video_versions" in it:
                            media_url = it["video_versions"][0]["url"]
                            typ = "video"
                        elif "image_versions2" in it:
                            media_url = it["image_versions2"]["candidates"][0]["url"]
                            typ = "image"
                        else:
                            continue
                        stories.append({
                            "media_url": media_url,
                            "thumb": thumb,
                            "type": typ
                        })
                    if stories:
                        with open(SESSION_IDX_PATH, "w") as f:
                            f.write(s["session_key"])
                        return stories, s
                else:
                    block_session(ck["sessionid"])
                    app.logger.error(f"Story session blocked: {s.get('user')} ({ck['sessionid']}) - Status: {r.status_code}")
            except Exception as e:
                block_session(ck["sessionid"])
                app.logger.error(f"Story session exception: {s.get('user')} ({ck['sessionid']}) - {str(e)}")
    if pool:
        with open(SESSION_IDX_PATH, "w") as f:
            next_idx = (idx + 1) % len(pool)
            f.write(pool[next_idx]["session_key"])
    return None, None

def _get_highlights(uid: str):
    """
    Kullanıcının highlight tray listesini alır ve her highlight içindeki öğelerden
    (yükü azaltmak için) ilk 3 medyayı düz listeye açar.
    """
    pool = _cookie_pool()
    if not pool or not uid:
        return []

    tray_url = f"https://i.instagram.com/api/v1/highlights/{uid}/highlights_tray/"
    items_all = []
    used_session_key = None

    for s in pool:
        ck = {
            "sessionid":  s.get("sessionid", ""),
            "ds_user_id": s.get("ds_user_id", ""),
            "csrftoken":  s.get("csrftoken", "")
        }
        try:
            r = requests.get(tray_url, headers=_build_headers(), cookies=ck, timeout=10)
            if r.status_code == 200 and "tray" in r.text:
                tray = r.json().get("tray", [])[:12]
                used_session_key = s.get("session_key")
                for t in tray:
                    hid = t.get("id") or t.get("reel_id")
                    if not hid:
                        continue
                    rm_url = f"https://i.instagram.com/api/v1/feed/reels_media/?reel_ids=highlight:{hid}"
                    try:
                        rr = requests.get(rm_url, headers=_build_headers(), cookies=ck, timeout=10)
                        if rr.status_code == 200:
                            j = rr.json()
                            reels_media = (j.get("reels_media") or [])
                            if not reels_media:
                                continue
                            media_items = (reels_media[0].get("items") or [])[:3]
                            for it in media_items:
                                thumb = it.get("image_versions2", {}).get("candidates", [{}])[0].get("url", "")
                                if "video_versions" in it:
                                    media_url = it["video_versions"][0].get("url", "")
                                    typ = "video"
                                elif "image_versions2" in it:
                                    media_url = it["image_versions2"]["candidates"][0].get("url", "")
                                    typ = "image"
                                else:
                                    continue
                                items_all.append({
                                    "type": typ,
                                    "url": media_url,
                                    "thumb": thumb
                                })
                    except Exception:
                        continue
                break
        except Exception:
            continue

    if used_session_key and pool:
        try:
            with open(SESSION_IDX_PATH, "w") as f:
                f.write(used_session_key)
        except Exception:
            pass
    return items_all


def test_sessions():
    if not os.path.exists(SESSIONS_PATH):
        print("sessions.json yok")
        return
    with open(SESSIONS_PATH) as f:
        sessions = json.load(f)
    for s in sessions:
        ck = {k: s.get(k,"") for k in ("sessionid","ds_user_id","csrftoken")}
        try:
            r = requests.get("https://i.instagram.com/api/v1/accounts/current_user/", cookies=ck, timeout=10)
            print(f"{s.get('user')}: {r.status_code}")
        except Exception as e:
            print(f"{s.get('user')}: ERROR {e}")

# --------------------------------------------------------------------------- #
#  STANDART MEDYA (reel / video / fotoğraf / igtv)                            #
# --------------------------------------------------------------------------- #
def _extract_sc(url: str):
    m = re.search(r"/(reel|p|tv)/([A-Za-z0-9_-]{5,})", url)
    if not m:
        path = re.sub(r"https?://(?:www\.)?instagr\.am", "", url)
        m = re.search(r"/(reel|p|tv)/([A-Za-z0-9_-]{5,})", path)
    return m.group(2) if m else None

def _gql_url(sc: str):
    v = json.dumps({
        "shortcode": sc,
        "fetch_tagged_user_count": None,
        "hoisted_comment_id": None,
        "hoisted_reply_id": None
    })
    return ("https://www.instagram.com/graphql/query/"
            f"?doc_id=8845758582119845&variables={v}")

def _process_media(j: dict):
    info = (
        j.get("data",{}).get("xdt_shortcode_media")
        or j.get("data",{}).get("shortcode_media") or {}
    )
    if not info:
        return False

    typ = info.get("__typename","").lower()
    vurl, iurls = None, []

    if typ.endswith("video"):
        vurl = info.get("video_url") or (info.get("video_resources") or [{}])[0].get("src")
        session["video_url"] = vurl
    elif typ.endswith("image"):
        img = info.get("display_url") or (info.get("display_resources") or [{}])[-1].get("src")
        if img and not img.endswith(".heic"):
            iurls = [img]
        session["image_urls"] = iurls
    elif "sidecar" in typ:
        for edge in info.get("edge_sidecar_to_children",{}).get("edges",[]):
            node = edge.get("node",{})
            if node.get("__typename","").lower().endswith("video"):
                vurl = node.get("video_url") or (node.get("video_resources") or [{}])[0].get("src")
            else:
                iu = node.get("display_url") or (node.get("display_resources") or [{}])[-1].get("src")
                if iu and not iu.endswith(".heic"):
                    iurls.append(iu)
        session["video_url"]  = vurl
        session["image_urls"] = iurls

    session["thumbnail_url"] = (
        info.get("thumbnail_src")
        or (info.get("display_resources") or [{}])[0].get("src")
    )
    raw_title = (
        (info.get("edge_media_to_caption",{}).get("edges") or [{}])[0]
        .get("node",{}).get("text","")
    ) or info.get("owner",{}).get("username") or "instagram"
    title = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_title)[:50]
    session["video_title"] = title

    comments = [
        f"{e['node']['owner']['username']}: {e['node']['text']}"
        for e in info.get("edge_media_to_parent_comment",{}).get("edges",[])
    ]
    session["raw_comments"] = json.dumps(comments[:40])
    return bool(session.get("video_url") or session.get("image_urls"))

def _fetch_media(gql: str):
    pool = _cookie_pool()
    if not pool:
        return None, None
    last_key = None
    if os.path.exists(SESSION_IDX_PATH):
        with open(SESSION_IDX_PATH, "r") as f:
            last_key = f.read().strip()
    keys = [s["session_key"] for s in pool]
    idx = 0
    if last_key and last_key in keys:
        idx = (keys.index(last_key) + 1) % len(pool)
    for offset in range(len(pool)):
        real_idx = (idx + offset) % len(pool)
        s = pool[real_idx]
        ck = {k: s.get(k, "") for k in ("sessionid", "ds_user_id", "csrftoken")}
        try:
            r = requests.get(gql, headers=_build_headers(), cookies=ck, timeout=10)
            if r.status_code == 200 and ("shortcode_media" in r.text or "xdt_shortcode_media" in r.text):
                with open(SESSION_IDX_PATH, "w") as f:
                    f.write(s["session_key"])
                return r.json(), s
            else:
                block_session(ck["sessionid"])
                app.logger.error(f"Media session blocked: {s.get('user')} ({ck['sessionid']}) - Status: {r.status_code}")
        except Exception as e:
            block_session(ck["sessionid"])
            app.logger.error(f"Media session exception: {s.get('user')} ({ck['sessionid']}) - {str(e)}")
    if pool:
        with open(SESSION_IDX_PATH, "w") as f:
            next_idx = (idx + 1) % len(pool)
            f.write(pool[next_idx]["session_key"])
    return None, None

# --------------------------------------------------------------------------- #
#  Flow Yardımcısı                                                            #
# --------------------------------------------------------------------------- #
def _media_flow(template: str, flag: str, lang=None):
    try:
        _clear_media_state()

        url = request.form.get("instagram_url","").strip()
        if not url:
            return render_template(template, error=_("Please enter a link."), lang=lang)

        session["last_target"] = url

        sc = _extract_sc(url)
        if not sc:
            return render_template(template, error=_("Enter a valid Instagram link."), lang=lang)

        data, used_session = _fetch_media(_gql_url(sc))
        if not data or not _process_media(data):
            return render_template(template, error=_("Media could not be retrieved, please try again."), lang=lang)

        if used_session:
            session["sessionid"] = used_session.get("sessionid", "")

        session[flag] = True
        return redirect(url_for("loading", lang=lang))

    except Exception:
        app.logger.exception("Media flow error")
        return render_template(template, error=_("Media could not be retrieved, please try again."), lang=lang)

# --------------------------------------------------------------------------- #
#  ROUTER’lar                                                                 #
# --------------------------------------------------------------------------- #
@app.errorhandler(404)
def not_found(e):
    lang = get_locale()
    return render_template("404.html", lang=lang), 404

# <<< ÖNEMLİ: "/" route TEK >>> #
@app.route("/", methods=["GET", "POST"])
def root():
    """
    - Varsayılan İngilizce içerik / üzerinde.
    - İlk gelişte tarayıcı diline göre /<dil>/ yönlendirmesi (tek seferlik).
    """
    if request.method == "POST":
        _clear_media_state()
        return index(lang="en")

    if not request.referrer:
        browser_lang = request.accept_languages.best_match(LANGUAGES)
        if browser_lang and browser_lang != "en":
            return redirect(url_for("index", lang=browser_lang), code=302)

    meta = get_meta("index", "en")
    return render_template("index.html", lang="en", meta=meta)

@app.route("/<lang>/", methods=["GET", "POST"])
def index(lang=None):
    if lang not in LANGUAGES:
        return redirect("/", code=302)

    meta = get_meta("index", lang)

    if request.method == "POST":
        _clear_media_state()

        raw_url = (request.form.get("instagram_url") or "").strip()
        if not raw_url:
            return render_template("index.html",
                                   error=_("Please enter a link."),
                                   lang=lang, meta=meta)

        url = raw_url.split('?')[0].rstrip('/')
        session["last_target"] = url

        if "/stories/" in url:
            mh = re.search(r"(?:instagram\.com|instagr\.am)/stories/highlights/(\d+)", url)
            if mh:
                uid = f"highlight:{mh.group(1)}"
                uname = "highlight"
            else:
                m2 = re.search(r"(?:instagram\.com|instagr\.am)/stories/([A-Za-z0-9_.]+)", url)
                uname = m2.group(1) if m2 else None

            if not uname:
                return render_template("index.html",
                                       error=_("Enter a valid story link."),
                                       lang=lang, meta=meta)

            uid = _get_uid(uname)
            if not uid:
                return render_template("index.html",
                                       error=_("User info could not be retrieved."),
                                       lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("index.html",
                                       error=_("No active story found."),
                                       lang=lang, meta=meta)

            session["stories"] = stories
            session["username"] = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        uname = _parse_username_or_url(url)
        if uname:
            return redirect(url_for("profile_view", lang=lang, username=uname))

        return _media_flow("index.html", "from_idx", lang=lang)

    return render_template("index.html", lang=lang, meta=meta)

@app.route('/<path:path>', methods=["GET", "POST"])
def catch_all_root(path):
    lang_match = re.fullmatch(r'[a-z]{2}', path.strip('/'))
    if lang_match:
        lang = path.strip('/')
        if lang in LANGUAGES:
            return redirect(url_for("index", lang=lang))
    lang = get_locale() if get_locale() in LANGUAGES else "en"
    return render_template("404.html", lang=lang), 404

# ---------------------------- LOADING / DOWNLOAD -----------------------------

@app.route("/loading", defaults={"lang": "en"})
@app.route("/<lang>/loading")
def loading(lang):
    r = _ensure_gate(lang)
    if r: return r
    r = _ensure_not_blacklisted()
    if r: return r
    r = _enforce_rate_limit(suffix=":loading")
    if r: return r

    if session.get("from_story"):
        session["from_story"] = False
        session["from_load"]  = True
        return render_template("loading.html", lang=lang)
    flags = ["from_idx","from_video","from_fotograf","from_reels","from_igtv"]
    for f in flags:
        if session.get(f):
            session[f] = False
            session["from_load"] = True
            return render_template("loading.html", lang=lang)
    return redirect(url_for("index", lang=lang))

@app.route("/download", defaults={"lang": "en"})
@app.route("/<lang>/download")
def download(lang):
    r = _ensure_gate(lang)
    if r: return r
    r = _ensure_not_blacklisted()
    if r: return r
    r = _enforce_rate_limit(suffix=":download")
    if r: return r

    if not session.get("from_load"):
        return redirect(url_for("index", lang=lang))
    session["from_load"] = False

    sessionid = session.get("sessionid", "")
    username = session.get("username", "") or session.get("user", "")
    if not username and sessionid:
        try:
            with open(SESSIONS_PATH, encoding="utf-8") as f:
                all_sessions = json.load(f)
            for s in all_sessions:
                if s.get("sessionid") == sessionid:
                    username = s.get("user", "")
                    break
        except Exception:
            pass

    if sessionid or username:
        log_session_use(sessionid, "success")
        notify_download(username)
        if sessionid:
            update_session_counters(sessionid, "success")

    if session.get("stories"):
        return render_template("story_list.html",
                               stories=session["stories"],
                               username=session.get("username",""),
                               lang=lang)

    vurl  = session.get("video_url")
    imgs  = session.get("image_urls", []) or []
    poster = session.get("thumbnail_url", "")

    downloads = []
    if vurl:
        downloads.append({
            "url": vurl,
            "label": _("MP4"),
            "type": "video",
            "thumb": poster
        })
    for i, im in enumerate(imgs):
        downloads.append({
            "url": im,
            "label": f"IMG {i+1}",
            "type": "image",
            "thumb": im
        })

    media = {
        "kind": ("video" if vurl else ("post" if downloads else None)),
        "downloads": downloads,
        "poster": poster
    }

    raw_comments = session.get("raw_comments")
    try:
        comments = json.loads(raw_comments) if raw_comments else []
    except Exception:
        comments = []

    return render_template("download.html",
        video_url     = vurl,
        image_urls    = imgs,
        thumbnail_url = poster,
        comments      = comments,
        media         = media,
        lang=lang
    )

@app.route("/photo_download/<int:i>")
def photo_dl(i):
    r = _enforce_rate_limit(suffix=":photo")
    if r: return r

    try:
        imgs = session.get("image_urls", [])
        if 0 <= i < len(imgs):
            rqs = requests.get(imgs[i], stream=True, timeout=10)
            sessionid = session.get("sessionid", "")
            username = session.get("username", "") or session.get("user", "")
            if not username and sessionid:
                try:
                    with open(SESSIONS_PATH, encoding="utf-8") as f:
                        all_sessions = json.load(f)
                    for s in all_sessions:
                        if s.get("sessionid") == sessionid:
                            username = s.get("user", "")
                            break
                except Exception:
                    pass

            if sessionid or username:
                log_session_use(sessionid, "success")
                notify_download(username)
                if sessionid:
                    update_session_counters(sessionid, "success")
            return Response(
                (c for c in rqs.iter_content(65536) if c),
                content_type=rqs.headers.get("Content-Type","image/jpeg"),
                headers={"Content-Disposition":f"attachment; filename=image_{i+1}.jpg"}
            )
    except Exception:
        app.logger.exception(f"Error in photo_dl index={i}")
        sessionid = session.get("sessionid", "")
        if sessionid:
            update_session_counters(sessionid, "fail")
    return redirect(url_for("index"))

@app.route("/direct_download")
def direct_dl():
    r = _enforce_rate_limit(suffix=":video")
    if r: return r

    try:
        url  = session.get("video_url")
        name = session.get("video_title","instagram_video") + ".mp4"
        if not url:
            return render_template("download.html",
                                   error=_("Video URL not found."),
                                   media={"downloads":[], "kind":None, "poster":""})
        rqs = requests.get(
            url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.instagram.com/"},
            stream=True, timeout=10
        )
        if rqs.status_code != 200:
            raise RuntimeError
        sessionid = session.get("sessionid", "")
        username = session.get("username", "") or session.get("user", "")
        if not username and sessionid:
            try:
                with open(SESSIONS_PATH, encoding="utf-8") as f:
                    all_sessions = json.load(f)
                for s in all_sessions:
                    if s.get("sessionid") == sessionid:
                        username = s.get("user", "")
                        break
            except Exception:
                pass

        if sessionid or username:
            log_session_use(sessionid, "success")
            notify_download(username)
            if sessionid:
                update_session_counters(sessionid, "success")
        return Response(
            (c for c in rqs.iter_content(65536) if c),
            content_type=rqs.headers.get("Content-Type","video/mp4"),
            headers={"Content-Disposition":f"attachment; filename={name}"}
        )
    except Exception:
        app.logger.exception("Error in direct_dl")
        sessionid = session.get("sessionid", "")
        if sessionid:
            log_session_use(sessionid, "fail")
            update_session_counters(sessionid, "fail")
        return render_template("download.html",
                               error=_("Error occurred during download."),
                               media={"downloads":[], "kind":None, "poster":""})

@app.route("/img_proxy")
def img_pxy():
    u = request.args.get("url","")
    if not u:
        return "URL parametresi eksik", 400
    try:
        r = requests.get(u, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        return send_file(io.BytesIO(r.content),
                         mimetype=r.headers.get("Content-Type","image/jpeg"))
    except Exception as e:
        return f"Proxy hatası: {e}", 500

# kısa yollar
@app.route("/video", defaults={"lang": "en"}, methods=["GET", "POST"])
@app.route("/<lang>/video", methods=["GET", "POST"])
def video(lang):
    meta = get_meta("video", lang)
    if request.method == "POST":
        _clear_media_state()

        raw_url = request.form.get("instagram_url", "").strip()
        if not raw_url:
            return render_template("video.html", error=_("Please enter a link."), lang=lang, meta=meta)

        url = raw_url.split('?')[0].rstrip('/')
        session["last_target"] = url

        if "/stories/" in url:
            mh = re.search(r"(?:instagram\.com|instagr\.am)/stories/highlights/(\d+)", url)
            if mh:
                uid = f"highlight:{mh.group(1)}"
                uname = "highlight"
            else:
                m2 = re.search(r"(?:instagram\.com|instagr\.am)/stories/([A-Za-z0-9_.]+)", url)
                uname = m2.group(1) if m2 else None

            if not uname:
                return render_template("video.html", error=_("Enter a valid story link."), lang=lang, meta=meta)

            uid = _get_uid(uname)
            if not uid:
                return render_template("video.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("video.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        mprof = re.search(r"(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)$", url)
        if mprof:
            uname = mprof.group(1)
            uid = _get_uid(uname)
            if not uid:
                return render_template("video.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("video.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        return _media_flow("video.html", "from_video", lang=lang)

    return render_template("video.html", lang=lang, meta=meta)

@app.route("/photo", defaults={"lang": "en"}, methods=["GET", "POST"])
@app.route("/<lang>/photo", methods=["GET", "POST"])
def photo(lang):
    meta = get_meta("photo", lang)
    if request.method == "POST":
        _clear_media_state()

        raw_url = request.form.get("instagram_url", "").strip()
        if not raw_url:
            return render_template("photo.html", error=_("Please enter a link."), lang=lang, meta=meta)

        url = raw_url.split('?')[0].rstrip('/')
        session["last_target"] = url

        if "/stories/" in url:
            mh = re.search(r"(?:instagram\.com|instagr\.am)/stories/highlights/(\d+)", url)
            if mh:
                uid = f"highlight:{mh.group(1)}"
                uname = "highlight"
            else:
                m2 = re.search(r"(?:instagram\.com|instagr\.am)/stories/([A-Za-z0-9_.]+)", url)
                uname = m2.group(1) if m2 else None

            if not uname:
                return render_template("photo.html", error=_("Enter a valid story link."), lang=lang, meta=meta)

            uid = _get_uid(uname)
            if not uid:
                return render_template("photo.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("photo.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        mprof = re.search(r"(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)$", url)
        if mprof:
            uname = mprof.group(1)
            uid = _get_uid(uname)
            if not uid:
                return render_template("photo.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("photo.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        return _media_flow("photo.html", "from_fotograf", lang=lang)

    return render_template("photo.html", lang=lang, meta=meta)

@app.route("/reels", defaults={"lang": "en"}, methods=["GET", "POST"])
@app.route("/<lang>/reels", methods=["GET", "POST"])
def reels(lang):
    meta = get_meta("reels", lang)
    if request.method == "POST":
        _clear_media_state()

        raw_url = request.form.get("instagram_url", "").strip()
        if not raw_url:
            return render_template("reels.html", error=_("Please enter a link."), lang=lang, meta=meta)

        url = raw_url.split('?')[0].rstrip('/')
        session["last_target"] = url

        if "/stories/" in url:
            mh = re.search(r"(?:instagram\.com|instagr\.am)/stories/highlights/(\d+)", url)
            if mh:
                uid = f"highlight:{mh.group(1)}"
                uname = "highlight"
            else:
                m2 = re.search(r"(?:instagram\.com|instagr\.am)/stories/([A-Za-z0-9_.]+)", url)
                uname = m2.group(1) if m2 else None

            if not uname:
                return render_template("reels.html", error=_("Enter a valid story link."), lang=lang, meta=meta)

            uid = _get_uid(uname)
            if not uid:
                return render_template("reels.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("reels.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        mprof = re.search(r"(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)$", url)
        if mprof:
            uname = mprof.group(1)
            uid = _get_uid(uname)
            if not uid:
                return render_template("reels.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("reels.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        return _media_flow("reels.html", "from_reels", lang=lang)

    return render_template("reels.html", lang=lang, meta=meta)

@app.route("/igtv", defaults={"lang": "en"}, methods=["GET", "POST"])
@app.route("/<lang>/igtv", methods=["GET", "POST"])
def igtv(lang):
    meta = get_meta("igtv", lang)
    if request.method == "POST":
        _clear_media_state()

        raw_url = request.form.get("instagram_url", "").strip()
        if not raw_url:
            return render_template("igtv.html", error=_("Please enter a link."), lang=lang, meta=meta)

        url = raw_url.split('?')[0].rstrip('/')
        session["last_target"] = url

        if "/stories/" in url:
            mh = re.search(r"(?:instagram\.com|instagr\.am)/stories/highlights/(\d+)", url)
            if mh:
                uid = f"highlight:{mh.group(1)}"
                uname = "highlight"
            else:
                m2 = re.search(r"(?:instagram\.com|instagr\.am)/stories/([A-Za-z0-9_.]+)", url)
                uname = m2.group(1) if m2 else None

            if not uname:
                return render_template("igtv.html", error=_("Enter a valid story link."), lang=lang, meta=meta)

            uid = _get_uid(uname)
            if not uid:
                return render_template("igtv.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("igtv.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        mprof = re.search(r"(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)$", url)
        if mprof:
            uname = mprof.group(1)
            uid = _get_uid(uname)
            if not uid:
                return render_template("igtv.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

            stories, used_session = _get_stories(uid)
            if not stories:
                return render_template("igtv.html", error=_("No active story found."), lang=lang, meta=meta)

            session["stories"]    = stories
            session["username"]   = uname
            session["from_story"] = True
            if used_session:
                session["sessionid"] = used_session.get("sessionid", "")
            return redirect(url_for("loading", lang=lang))

        return _media_flow("igtv.html", "from_igtv", lang=lang)

    return render_template("igtv.html", lang=lang, meta=meta)

@app.route("/story", defaults={"lang": "en"}, methods=["GET", "POST"])
@app.route("/<lang>/story", methods=["GET", "POST"])
def story(lang):
    meta = get_meta("story", lang)
    if request.method == "POST":
        _clear_media_state()

        raw_url = request.form.get("instagram_url", "").strip()
        if not raw_url:
            return render_template("story.html", error=_("Please enter a link."), lang=lang, meta=meta)

        url = raw_url.split('?')[0].rstrip('/')

        session["last_target"] = url

        if "/stories/" in url:
            mh = re.search(
                r"(?:instagram\.com|instagr\.am)/stories/highlights/(\d+)",
                url
            )
            if mh:
                uid = f"highlight:{mh.group(1)}"
                uname = "highlight"
            else:
                m2 = re.search(
                    r"(?:instagram\.com|instagr\.am)/stories/([A-Za-z0-9_.]+)",
                    url
                )
                uname = m2.group(1) if m2 else None

            if not uname:
                return render_template("story.html", error=_("Enter a valid story link."), lang=lang, meta=meta)

        else:
            mprof = re.search(r"(?:instagram\.com|instagr\.am)/([A-Za-z0-9_.]+)$", url)
            if not mprof:
                return render_template("story.html", error=_("Enter a valid profile or story link."), lang=lang, meta=meta)
            uname = mprof.group(1)

        uid = _get_uid(uname)
        if not uid:
            return render_template("story.html", error=_("User info could not be retrieved."), lang=lang, meta=meta)

        stories, used_session = _get_stories(uid)
        if not stories:
            return render_template("story.html", error=_("No active story found."), lang=lang, meta=meta)

        session["stories"]    = stories
        session["username"]   = uname
        session["from_story"] = True
        if used_session:
            session["sessionid"] = used_session.get("sessionid", "")
        return redirect(url_for("loading", lang=lang))

    return render_template("story.html", lang=lang, meta=meta)

@app.route("/story-download/<int:i>")
def story_download(i):
    try:
        stories = session.get("stories", [])
        if not stories or i < 0 or i >= len(stories):
            return "Story not found", 404

        story = stories[i]
        media_url = story.get("media_url")
        if not media_url:
            return "Media URL not found", 404

        ext = "mp4" if story.get("type") == "video" else "jpg"

        import requests
        r = requests.get(media_url, stream=True)
        r.raise_for_status()

        return Response(
            r.iter_content(chunk_size=8192),
            content_type="video/mp4" if ext == "mp4" else "image/jpeg",
            headers={
                "Content-Disposition": f'attachment; filename=story_{i}.{ext}'
            }
        )

    except Exception as e:
        app.logger.error(f"Story download error: {e}")
        return "Download error", 500


@app.route("/profile", defaults={"lang": "en"}, methods=["GET", "POST"])
@app.route("/<lang>/profile", methods=["GET", "POST"])
def profile_search(lang):
    """
    Basit arama girişi: username/URL alır, /<lang>/u/<username> detay sayfasına yönlendirir.
    """
    r = _ensure_gate(lang)
    if r: return r
    r = _ensure_not_blacklisted()
    if r: return r
    r = _enforce_rate_limit(suffix=":profile_search")
    if r: return r

    if request.method == "POST":
        raw = (request.form.get("instagram_url") or "").strip()
        uname = _parse_username_or_url(raw)
        if not uname:
            return render_template("index.html",
                                   error=_("Enter a valid profile username or URL."),
                                   lang=lang)
        session["last_target"] = f"https://instagram.com/{uname}"
        return redirect(url_for("profile_view", lang=lang, username=uname))
    return render_template("profile.html", profile=None, sections=None, lang=lang)

@app.route("/u/<username>", defaults={"lang": "en"})
@app.route("/<lang>/u/<username>")
def profile_view(lang, username):
    r = _ensure_gate(lang)
    if r: return r
    r = _ensure_not_blacklisted()
    if r: return r
    r = _enforce_rate_limit(suffix=":profile_view")
    if r: return r

    uname = _parse_username_or_url(username)
    if not uname:
        return render_template("profile.html",
                               profile=None, sections=None,
                               error=_("Enter a valid profile username or URL."),
                               lang=lang)

    session["last_target"] = f"https://instagram.com/{uname}"

    try:
        profile, sections = _get_profile_data(uname)
        if not profile:
            return render_template("profile.html",
                                   profile=None, sections=None,
                                   error=_("User info could not be retrieved."),
                                   lang=lang)
        return render_template("profile.html", profile=profile, sections=sections, lang=lang)
    except Exception:
        app.logger.exception("Profile view error")
        return render_template("profile.html",
                               profile=None, sections=None,
                               error=_("Profile could not be loaded, please try again."),
                               lang=lang)

# -------------------------- DEBUG: Profil Teşhis --------------------------
# İş bitince kaldırabilirsiniz.
@app.route("/__dbg_profile/<username>")
def __dbg_profile(username):
    try:
        p, s = _get_profile_data(username)
        return jsonify({
            "ok": True,
            "username": username,
            "posts": len(s.get("posts", [])),
            "reels": len(s.get("reels", [])),
            "stories": len(s.get("stories", [])),
            "highlights": len(s.get("highlights", [])),
        })
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)}), 500

@app.route("/privacy-policy", defaults={"lang": "en"})
@app.route("/<lang>/privacy-policy")
def privacy(lang="en"):
    meta = get_meta("privacy", lang)
    return render_template("privacy.html", lang=lang, meta=meta)

@app.route("/terms", defaults={"lang": "en"})
@app.route("/<lang>/terms")
def terms(lang="en"):
    meta = get_meta("terms", lang)
    return render_template("terms.html", lang=lang, meta=meta)

@app.route("/contact", defaults={"lang": "en"})
@app.route("/<lang>/contact")
def contact(lang="en"):
    meta = get_meta("contact", lang)
    return render_template("contact.html", lang=lang, meta=meta)

app.register_blueprint(admin_bp, url_prefix='/srdr-proadmin')
from adminpanel.blacklist_admin import blacklist_admin_bp
app.register_blueprint(blacklist_admin_bp)

@app.route('/robots.txt')
def robots_txt():
    return send_file('robots.txt', mimetype='text/plain')

@app.route('/cookie-policy')
def cookie_policy():
    return render_template('cookie_policy.html')

# --- Ana Uygulama Çalıştırıcı --- #
if __name__ == "__main__":
    # Lokal test için:
    # test_sessions()
    app.run(debug=True)
