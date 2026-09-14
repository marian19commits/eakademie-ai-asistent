
import os


class Config:
    APP_NAME = os.getenv("APP_NAME", "AI asistent")
    VERSION = os.getenv("VERSION", "v1.0")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    RELATIVE_URL = os.getenv("RELATIVE_URL", "")
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY", "")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
    AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01")

