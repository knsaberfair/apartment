import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.environ.get("APARTMENT_ENV", "production").lower()
DATABASE_PATH = Path(os.environ.get("APARTMENT_DB_PATH", BASE_DIR / "app.db"))
DEFAULT_JWT_SECRET = "apartment-dev-secret-change-me"
JWT_SECRET_KEY = os.environ.get("APARTMENT_JWT_SECRET", DEFAULT_JWT_SECRET)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("APARTMENT_TOKEN_EXPIRE_MINUTES", "480"))
AUTH_COOKIE_NAME = os.environ.get("APARTMENT_AUTH_COOKIE_NAME", "apartment_auth")
AUTH_COOKIE_PATH = os.environ.get("APARTMENT_AUTH_COOKIE_PATH", "/")
AUTH_COOKIE_SAMESITE = os.environ.get("APARTMENT_AUTH_COOKIE_SAMESITE", "lax").lower()
AUTH_COOKIE_SECURE = os.environ.get("APARTMENT_AUTH_COOKIE_SECURE", str(APP_ENV == "production")).lower() == "true"
AUTH_COOKIE_MAX_AGE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60
ALLOW_DEMO_ROLE_HEADER = os.environ.get("APARTMENT_ALLOW_DEMO_ROLE_HEADER", "false").lower() == "true"
ENABLE_DEMO_SEED = os.environ.get("APARTMENT_ENABLE_DEMO_SEED", str(APP_ENV in {"development", "test"})).lower() == "true"
WECHAT_APP_ID = os.environ.get("APARTMENT_WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.environ.get("APARTMENT_WECHAT_APP_SECRET", "")
WECHAT_MOCK_LOGIN = os.environ.get("APARTMENT_WECHAT_MOCK_LOGIN", str(APP_ENV in {"development", "test"})).lower() == "true"

if APP_ENV not in {"development", "test"} and JWT_SECRET_KEY == DEFAULT_JWT_SECRET:
    raise RuntimeError("APARTMENT_JWT_SECRET must be configured outside development/test environments")

if APP_ENV not in {"development", "test"} and ALLOW_DEMO_ROLE_HEADER:
    raise RuntimeError("APARTMENT_ALLOW_DEMO_ROLE_HEADER is only allowed in development/test environments")

if APP_ENV == "production" and ENABLE_DEMO_SEED:
    raise RuntimeError("APARTMENT_ENABLE_DEMO_SEED must be false in production")

if APP_ENV not in {"development", "test"} and WECHAT_MOCK_LOGIN:
    raise RuntimeError("APARTMENT_WECHAT_MOCK_LOGIN must be false outside development/test")
