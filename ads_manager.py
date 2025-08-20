# -*- coding: utf-8 -*-
# /var/www/instavido/ads_manager.py
import os, json, time, tempfile, re
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADS_DIR  = os.path.join(BASE_DIR, "ads")
ADS_FILE = os.path.join(ADS_DIR, "ads_config.json")

DEFAULT_CONFIG = {
    "updated_at": int(time.time()),
    "interstitial": {"enabled": True, "min_after_first": 2, "max_after_first": 5, "cooldown_minutes": 30},
    "slots": {
        "header_top":        {"active": True,  "label": "Header Top (üst şerit)",      "html": "<div class='ad ad-header'>[Header Ad]</div>"},
        "below_header":      {"active": True,  "label": "Header Altı Geniş",           "html": "<div class='ad ad-below-header'>[Below Header Ad]</div>"},
        "sidebar_left":      {"active": False, "label": "Sol Sidebar",                  "html": "<div class='ad ad-left'>[Left Ad]</div>"},
        "sidebar_right":     {"active": True,  "label": "Sağ Sidebar",                  "html": "<div class='ad ad-right'>[Right Ad]</div>"},
        "download_inline":   {"active": True,  "label": "Download İç İçi",             "html": "<div class='ad ad-inline'>[Inline Ad]</div>"},
        "modal_fullscreen":  {"active": True,  "label": "Tam Ekran Modal",              "html": "<div class='ad ad-modal'>[Fullscreen Interstitial]</div>"},
        # Bazı şablonlar iki ayrı anahtar bekliyor; boşa düşmemesi için ekliyoruz
        "bottom_bar":          {"active": False, "label": "Alt Sabit Çubuk",           "html": "<div>[Bottom Bar Ad]</div>"},
        "bottom_bar_desktop":  {"active": False, "label": "Alt Çubuk (Desktop)",       "html": "<div>[Bottom Bar Desktop]</div>"},
        "bottom_bar_mobile":   {"active": False, "label": "Alt Çubuk (Mobile)",        "html": "<div>[Bottom Bar Mobile]</div>"},
        "inline_ad":         {"active": False, "label": "Yorum Arası",                  "html": "<div>[Inline Ad]</div>"},
        "sticky_side":       {"active": False, "label": "Yapışkan Sağ/Sol",             "html": "<div>[Sticky Side Ad]</div>"},
        "top_banner":        {"active": False, "label": "Navbar Altı Banner",           "html": "<div>[Top Banner Ad]</div>"},
        "floating_button":   {"active": False, "label": "Kayan Buton",                  "html": "<button>[Open Ad]</button>"},
    },
}

def _atomic_write(path: str, data: Dict[str, Any]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".ads_cfg_", dir=os.path.dirname(path))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        if os.path.exists(path):
            try:
                with open(path, "rb") as src, open(path + ".bak", "wb") as bak:
                    bak.write(src.read()); bak.flush(); os.fsync(bak.fileno())
            except Exception:
                pass
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

def _safe_read(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # yedekten dön
        try:
            with open(path + ".bak", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            _atomic_write(path, cfg)
            return cfg
        except Exception:
            cfg = DEFAULT_CONFIG.copy()
            cfg["updated_at"] = int(time.time())
            _atomic_write(path, cfg)
            return cfg

def ensure_store():
    os.makedirs(ADS_DIR, exist_ok=True)
    if not os.path.exists(ADS_FILE):
        _atomic_write(ADS_FILE, DEFAULT_CONFIG)

def _migrate(cfg: Dict[str, Any]) -> Dict[str, Any]:
    slots = cfg.setdefault("slots", {})
    for k, v in DEFAULT_CONFIG["slots"].items():
        if k not in slots:
            slots[k] = v
    if "interstitial" not in cfg:
        cfg["interstitial"] = DEFAULT_CONFIG["interstitial"]
    return cfg

def load_config() -> Dict[str, Any]:
    ensure_store()
    cfg = _safe_read(ADS_FILE)
    before = set(cfg.get("slots", {}).keys())
    cfg = _migrate(cfg)
    after = set(cfg.get("slots", {}).keys())
    if after != before:
        save_config(cfg)
    return cfg

def save_config(cfg: Dict[str, Any]):
    cfg["updated_at"] = int(time.time())
    _atomic_write(ADS_FILE, cfg)

def list_slots() -> List[str]:
    return sorted(load_config().get("slots", {}).keys())

def get_slot(key: str) -> Dict[str, Any] | None:
    return load_config().get("slots", {}).get(key)

def set_slot(key: str, html: str, active: bool, label: str | None = None):
    cfg = load_config()
    slot = cfg.setdefault("slots", {}).setdefault(key, {"active": False, "label": key, "html": ""})
    slot["active"] = bool(active)
    if label is not None:
        slot["label"] = label
    slot["html"] = html or ""
    save_config(cfg)

def toggle_slot(key: str, active: bool):
    cfg = load_config()
    if key in cfg.get("slots", {}):
        cfg["slots"][key]["active"] = bool(active)
        save_config(cfg)

def delete_slot(key: str):
    cfg = load_config()
    if key in cfg.get("slots", {}):
        del cfg["slots"][key]
        save_config(cfg)

def set_interstitial(enabled: bool, min_after_first: int, max_after_first: int, cooldown_minutes: int):
    cfg = load_config()
    cfg["interstitial"] = {
        "enabled": bool(enabled),
        "min_after_first": int(min_after_first),
        "max_after_first": int(max_after_first),
        "cooldown_minutes": int(cooldown_minutes),
    }
    save_config(cfg)

# Basit key doğrulayıcı (harf, rakam, altçizgi)
KEY_RE = re.compile(r"^[a-z0-9_]+$", re.I)
def valid_key(key: str) -> bool:
    return bool(key) and bool(KEY_RE.fullmatch(key))
