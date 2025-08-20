import os, redis

def get_redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

def get_redis_client():
    return redis.from_url(
        get_redis_url(),
        decode_responses=False,
        health_check_interval=30,
        socket_timeout=2,
        socket_connect_timeout=2,
    )
