#!/usr/bin/env bash
# backup_instavido.sh
# Tek komutla /var/www/instavido projesinin güvenli yedeğini alır.
# - venv, cache, pyc, log, .git vb. hariç
# - /home/srdr/instavido_backups altına zaman damgalı arşiv üretir
# - manifest + sha256 checksum yazar
# Kullanım:
#   bash tools/backup_instavido.sh            # FULL (varsayılan)
#   bash tools/backup_instavido.sh lite       # HAFİF (kritik dosyalar)
#   BACKUP_ROOT=/path bash tools/backup...    # farklı hedef klasör

set -euo pipefail

PROJECT_DIR="/var/www/instavido"
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Hata: $PROJECT_DIR yok."
  exit 1
fi

MODE="${1:-full}"                # full | lite
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${BACKUP_ROOT:-/home/srdr/instavido_backups}"
TARGET_DIR="$BACKUP_ROOT"
ARCHIVE_BASENAME="instavido-$MODE-$TS"
ARCHIVE_PATH="$TARGET_DIR/${ARCHIVE_BASENAME}.tar.gz"
CHECKSUM_PATH="$TARGET_DIR/${ARCHIVE_BASENAME}.sha256"
MANIFEST_PATH="$TARGET_DIR/${ARCHIVE_BASENAME}.manifest.txt"

mkdir -p "$TARGET_DIR"

# --- Dahil/Haric kuralları ---
# FULL: tüm proje (belirtilen hariçler dışında)
# LITE: kritik dosyalar (app.py, sessions.json, adminpanel, templates, önemli json'lar)
EXCLUDES=(
  'instavido/venv'
  'instavido/.flask_session'
  'instavido/__pycache__'
  'instavido/*.pyc'
  'instavido/*.log'
  'instavido/.git'
  'instavido/node_modules'
  'instavido/ads_cache'
  'instavido/.DS_Store'
)

# LITE mod için dahil listesi
LITE_INCLUDE=(
  "instavido/app.py"
  "instavido/adminpanel"
  "instavido/templates"
  "instavido/static"                 # statik dosyalar (varsa değerli)
  "instavido/utils"                  # yeni ekleyeceğimiz yardımcılar
  "instavido/sessions.json"
  "instavido/blocked_cookies.json"
  "instavido/session_index.txt"
  "instavido/.rate_limits.json"
  "instavido/robots.txt"
  "instavido/requirements.txt"
)

echo "======== INSTAVIDO BACKUP ========"
echo "Tarih         : $TS"
echo "Mod           : $MODE"
echo "Proje         : $PROJECT_DIR"
echo "Hedef klasör  : $TARGET_DIR"
echo "Arşiv         : $ARCHIVE_PATH"
echo "Manifest      : $MANIFEST_PATH"
echo "Checksum      : $CHECKSUM_PATH"
echo "==================================="

cd /var/www

# --- Arşivi oluştur ---
if [[ "$MODE" == "lite" ]]; then
  # LITE: sadece seçili yollar
  # Önce dosyaların var olduğundan emin olalım (yoksa atla)
  INCLUDE_EXISTING=()
  for path in "${LITE_INCLUDE[@]}"; do
    if [[ -e "$path" ]]; then
      INCLUDE_EXISTING+=("$path")
    fi
  done
  if [[ ${#INCLUDE_EXISTING[@]} -eq 0 ]]; then
    echo "Uyarı: LITE modda dahil edilecek dosya bulunamadı."
  fi
  tar -czf "$ARCHIVE_PATH" "${INCLUDE_EXISTING[@]}"
else
  # FULL: tüm proje, EXCLUDES hariç
  TAR_ARGS=( "-czf" "$ARCHIVE_PATH" )
  for ex in "${EXCLUDES[@]}"; do
    TAR_ARGS+=( "--exclude=$ex" )
  done
  TAR_ARGS+=( "instavido" )
  tar "${TAR_ARGS[@]}"
fi

# --- Manifest oluştur ---
{
  echo "INSTAVIDO BACKUP MANIFEST"
  echo "Timestamp : $TS"
  echo "Mode      : $MODE"
  echo "Project   : $PROJECT_DIR"
  echo "Archive   : $ARCHIVE_PATH"
  echo
  echo "---- İlk 200 dosya ----"
  tar -tzf "$ARCHIVE_PATH" | head -n 200
  echo "-----------------------"
} > "$MANIFEST_PATH"

# --- SHA256 üret ---
sha256sum "$ARCHIVE_PATH" | tee "$CHECKSUM_PATH" >/dev/null

# --- Özet bilgi ---
SIZE_HUMAN="$(ls -lh "$ARCHIVE_PATH" | awk '{print $5}')"
echo
echo "✅ Yedek tamam: $ARCHIVE_PATH  ($SIZE_HUMAN)"
echo "📝 Manifest   : $MANIFEST_PATH"
echo "🔒 SHA256     : $CHECKSUM_PATH"
echo
echo "İlk içerik önizleme:"
head -n 20 "$MANIFEST_PATH"
