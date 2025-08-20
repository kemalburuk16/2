import json
import random
import os

SESSIONS_PATH = "sessions.json"

def generate_session_key(existing_keys):
    while True:
        key = ''.join(random.choices('0123456789', k=8))
        if key not in existing_keys:
            return key

def main():
    if not os.path.exists(SESSIONS_PATH):
        print("sessions.json bulunamadı!")
        return

    with open(SESSIONS_PATH, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    # Var olan anahtarları topla
    existing_keys = {s.get("session_key") for s in sessions if "session_key" in s}
    existing_keys.discard(None)

    changed = False
    for s in sessions:
        if "session_key" not in s or not s["session_key"]:
            key = generate_session_key(existing_keys)
            s["session_key"] = key
            existing_keys.add(key)
            changed = True

    if changed:
        with open(SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
        print("Eksik session_key'ler eklendi ve dosya güncellendi.")
    else:
        print("Tüm session'larda zaten session_key mevcut. Değişiklik yapılmadı.")

if __name__ == "__main__":
    main()
