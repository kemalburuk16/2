# Gunicorn configuration file for InstaVido production deployment
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50

# Restart workers after this many requests, with up to 50 random
# requests added to prevent workers from restarting at the same time
preload_app = True

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "instavido"

# Server mechanics
daemon = False
pidfile = "/tmp/instavido.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if certificates are available)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment variables
raw_env = [
    'FLASK_ENV=production',
    'SECRET_KEY=' + os.environ.get('SECRET_KEY', 'CHANGE_THIS_IN_PROD'),
    'IMG_PROXY_SECRET=' + os.environ.get('IMG_PROXY_SECRET', ''),
    'MEDIA_PROXY_SECRET=' + os.environ.get('MEDIA_PROXY_SECRET', ''),
]

# Graceful shutdown timeout
graceful_timeout = 30

# Enable automatic worker restart
reload = False

# Performance tuning
sendfile = True

# Enable keep-alive connections
reuse_port = True if hasattr(os, 'SO_REUSEPORT') else False