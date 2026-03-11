from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Pergefood AI Smart ERP"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "pergefood-super-secret-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    DATABASE_URL: str = "mssql+pymssql://ant14yaklimacom_pergefood:134Sel.115cuk@31.186.11.164/ant14yaklimacom_"

    # OCR
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    # AI Model storage path
    ML_MODELS_DIR: str = "app/ml/models"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
