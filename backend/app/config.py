from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://aruser:arpassword@localhost:5432/ardb"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8 hours

    anthropic_api_key: str = ""

    gmail_client_id: str = ""
    gmail_client_secret: str = ""

    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    outlook_tenant_id: str = ""

    upload_dir: str = "/app/uploads"

    class Config:
        env_file = ".env"


settings = Settings()
