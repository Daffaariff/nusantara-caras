from pydantic.v1 import BaseSettings

class AppConfig(BaseSettings):
    OPENAI_MODEL_NAME: str
    OPENAI_API_KEY: str
    
    class Config:
        env_file = ".env"

settings = AppConfig()