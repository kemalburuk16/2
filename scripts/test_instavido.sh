#!/usr/bin/env bash
# test_instavido.sh

BASE_URL="${1:-https://instavido.com}"
COOKIE_JAR="/tmp/instavido_test.cookie"

echo "🔎 Testler başlıyor: $BASE_URL"
rm -f "$COOKIE_JAR"

# ---- 1) Redis health
# ---- 1) Redis health
BODY=$(curl -s "$BASE_URL/_health/redis")
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/_health/redis")
echo "➡️  /_health/redis [HTTP ${CODE}] ${BODY}"
if [[ "$CODE" == "200" && "$BODY" == *'"ok":true'* ]]; then
  echo "✅ Redis health PASS"
else
  echo "❌ Redis health FAIL"
fi

# ---- 2) Session set/get
SET_CODE=$(curl -s -o /dev/null -w "%{http_code}" -c "$COOKIE_JAR" "$BASE_URL/_session_test")
echo "➡️  /_session_test [HTTP ${SET_CODE}] (cookie kaydedildi)"
GET_BODY=$(curl -s -b "$COOKIE_JAR" "$BASE_URL/_session_get")
GET_CODE=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_JAR" "$BASE_URL/_session_get")
echo "➡️  /_session_get [HTTP ${GET_CODE}] ${GET_BODY}"
if [[ "$GET_CODE" == "200" && "$GET_BODY" == *'"hello":"world"'* ]]; then
  echo "✅ Session (set/get) PASS"
else
  echo "❌ Session (set/get) FAIL"
fi

# ---- 3) Rate limit testi (isteğe bağlı kısa deneme)
RL_OK=0
for i in {1..11}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/_limit_test")
  if [[ "$CODE" == "429" ]]; then
    RL_OK=1
    break
  fi
done
if [[ "$RL_OK" == "1" ]]; then
  echo "✅ Rate limit tetiklendi (429 görüldü)"
else
  echo "ℹ️  Rate limit tetiklenemedi (daha yüksek istek gerekebilir)"
fi
