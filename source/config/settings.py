from dotenv import load_dotenv
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Optional
from loguru import logger

# Load .env file
env_path = Path(__file__).parent / ".env"
logger.debug
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    APP_NAME: str = "Nusantara CaRas"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Database config
    DATABASE_URL: Optional[str] = None
    DATABASE_NAME: Optional[str] = None
    DATABASE_USER: Optional[str] = None
    DATABASE_PASS: Optional[str] = None
    DATABASE_HOST: Optional[str] = None
    DATABASE_PORT: Optional[int] = None

    # API keys
    SEALION_API_KEY: Optional[str] = None

    SEALION_MODEL_NAME: Optional[str] = None
    SEALION_BASE_URL: Optional[str] = None
    
    MEDGEMMA_MODEL_NAME: Optional[str] = None
    MEDGEMMA_BASE_URL: Optional[str] = None

    SAGEMAKER_ENDPOINT: Optional[str] = None

    # Allowed origins (for CORS)
    ALLOWED_HOSTS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
logger.debug(f"Database URL: {settings.SAGEMAKER_ENDPOINT}")

