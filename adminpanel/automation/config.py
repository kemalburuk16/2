# adminpanel/automation/config.py
"""
Configuration settings for Instagram automation system
"""
import os
from datetime import timedelta

# Automation settings
AUTOMATION_ENABLED = os.getenv("AUTOMATION_ENABLED", "true").lower() == "true"
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "true").lower() == "true"

# Activity limits (per session per day)
DAILY_LIKES_LIMIT = int(os.getenv("DAILY_LIKES_LIMIT", "50"))
DAILY_FOLLOWS_LIMIT = int(os.getenv("DAILY_FOLLOWS_LIMIT", "20"))
DAILY_UNFOLLOWS_LIMIT = int(os.getenv("DAILY_UNFOLLOWS_LIMIT", "15"))
DAILY_COMMENTS_LIMIT = int(os.getenv("DAILY_COMMENTS_LIMIT", "10"))
DAILY_STORIES_LIMIT = int(os.getenv("DAILY_STORIES_LIMIT", "30"))

# Timing configuration (in seconds)
MIN_ACTION_DELAY = int(os.getenv("MIN_ACTION_DELAY", "3"))
MAX_ACTION_DELAY = int(os.getenv("MAX_ACTION_DELAY", "8"))
SESSION_TIMEOUT = int(os.getenv("SESSION_TIMEOUT", "300"))

# Activity scheduling
ACTIVITY_INTERVAL = timedelta(hours=int(os.getenv("ACTIVITY_INTERVAL_HOURS", "2")))
SESSION_REFRESH_INTERVAL = timedelta(hours=int(os.getenv("SESSION_REFRESH_HOURS", "6")))

# Browser configuration
CHROME_OPTIONS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-extensions",
    "--disable-plugins",
    "--disable-images",
    "--disable-javascript",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-popup-blocking",
    "--disable-translate",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=TranslateUI",
    "--disable-web-security",
    "--disable-features=VizDisplayCompositor"
]

if HEADLESS_MODE:
    CHROME_OPTIONS.extend([
        "--headless",
        "--disable-gpu",
        "--window-size=1920,1080"
    ])

# Comment templates for human-like interaction
COMMENT_TEMPLATES = [
    "Harika! 👏", "Çok güzel ❤️", "Süper! 🔥",
    "Muhteşem paylaşım", "Tebrikler! 🎉", "Bayıldım! 😍",
    "Mükemmel!", "Çok beğendim 👍", "Harika bir paylaşım",
    "Süpersin! ⭐", "Ne güzel! 💖", "Tebrik ederim!",
    "👌", "💯", "🙌", "Amazing!", "Great!", "Nice!",
    "Love it!", "Perfect!", "Awesome!", "Beautiful!",
    "Incredible!", "Fantastic!", "Wonderful!", "Stunning!"
]

# Hashtags for explore browsing
EXPLORE_HASHTAGS = [
    "photography", "art", "nature", "travel", "food",
    "fashion", "fitness", "lifestyle", "music", "design",
    "türkiye", "istanbul", "ankara", "izmir", "sanat",
    "doğa", "seyahat", "yemek", "moda", "spor"
]

# User agent strings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

# Proxy configuration (if needed)
PROXY_ENABLED = os.getenv("PROXY_ENABLED", "false").lower() == "true"
PROXY_LIST = os.getenv("PROXY_LIST", "").split(",") if os.getenv("PROXY_LIST") else []

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/automation.log")

# Anti-detection settings
VIEWPORT_SIZES = [
    (1920, 1080),
    (1366, 768),
    (1440, 900),
    (1280, 720)
]

# Activity weights (probability of each action)
ACTIVITY_WEIGHTS = {
    "like": 0.4,
    "story_view": 0.3,
    "profile_visit": 0.15,
    "explore": 0.1,
    "comment": 0.03,
    "follow": 0.02
}