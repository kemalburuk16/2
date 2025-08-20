import json
import os
import datetime

NOTIF_LOG = "/var/www/instavido/adminpanel/data/notif_log.json"
SESSION_LOG = "/var/www/instavido/adminpanel/data/session_use_log.json"
SESSIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.json")

def update_session_counters(sessionid, result="success"):
    print(">>> update_session_counters ÇAĞRILDI:", sessionid, result)
    # sessionid parametresi zorunlu!
    if not sessionid:
        return
    if not os.path.exists(SESSIONS_PATH):
        return
    with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
        sessions = json.load(f)
    updated = False
    for s in sessions:
        if s.get("sessionid") == sessionid:
            # SAYAÇLAR: Alan adları dosyadaki ile birebir aynı olmalı!
            s["last_used"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if result == "success":
                s["success_count"] = s.get("success_count", 0) + 1
            elif result == "fail":
                s["fail_count"] = s.get("fail_count", 0) + 1
            updated = True
            break
    if updated:
        with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

def log_session_use(sessionid, status):
    if not os.path.exists(SESSION_LOG):
        with open(SESSION_LOG, "w") as f:
            json.dump([], f)

    try:
        with open(SESSION_LOG, "r") as f:
            data = json.load(f)
    except:
        data = []

    data.append({
        "sessionid": sessionid,
        "status": status,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

    with open(SESSION_LOG, "w") as f:
        json.dump(data[-500:], f, indent=2)  # sadece son 500 log

def notify_download(username):
    notif = {
        "message": f"✅ Kullanıcı {username} üzerinden indirme yapıldı.",
        "user": username,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    if not os.path.exists(NOTIF_LOG):
        with open(NOTIF_LOG, "w") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    try:
        with open(NOTIF_LOG, "r") as f:
            data = json.load(f)
    except:
        data = []

    data.append(notif)
    with open(NOTIF_LOG, "w") as f:
        json.dump(data[-100:], f, ensure_ascii=False, indent=2)  # son 100 bildirim
