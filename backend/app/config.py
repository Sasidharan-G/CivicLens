from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CivicLens API"
    environment: str = "development"
    database_url: str = "sqlite:///./civiclens.db"
    jwt_secret_key: str = "development-only-change-me"
    jwt_expire_minutes: int = 1440
    refresh_token_expire_days: int = 30
    cors_origins: str = "http://localhost:5173"
    upload_dir: str = "uploads"
    max_upload_mb: int = 8
    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_vision_model: str = "gpt-4o-mini"
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    sentry_dsn: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@civiclens.local"
    smtp_use_tls: bool = True
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:admin@civiclens.local"
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str = "v21.0"
    internal_jobs_secret: str | None = None
    closed_media_retention_days: int = 730
    app_base_url: str = "http://localhost:5173"
    geocoding_enabled: bool = True
    geocoding_user_agent: str = "CivicLens/1.0 admin@civiclens.local"
    geocoding_cache_days: int = 30
    rate_limit_default: str = "120/minute"
    trust_proxy_headers: bool = False
    similarity_radius_m: float = 300
    similarity_threshold: float = 0.42
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def readiness(self) -> tuple[list[str], list[str]]:
        errors:list[str]=[];warnings:list[str]=[]
        if not self.is_production:return errors,warnings
        if self.database_url.startswith("sqlite"):errors.append("Production DATABASE_URL must use PostgreSQL")
        if len(self.jwt_secret_key)<32 or "change-me" in self.jwt_secret_key or "development" in self.jwt_secret_key:errors.append("JWT_SECRET_KEY must be a strong production secret")
        if not self.origins or any("localhost" in origin or not origin.startswith("https://") for origin in self.origins):errors.append("CORS_ORIGINS must contain production HTTPS origins only")
        if not self.app_base_url.startswith("https://") or "localhost" in self.app_base_url:errors.append("APP_BASE_URL must be the production HTTPS frontend URL")
        if not all([self.cloudinary_cloud_name,self.cloudinary_api_key,self.cloudinary_api_secret]):errors.append("Cloudinary credentials are required for durable production media")
        if not self.smtp_host or not self.smtp_from_email:errors.append("SMTP settings are required for production account email")
        if not self.internal_jobs_secret or len(self.internal_jobs_secret)<24:errors.append("INTERNAL_JOBS_SECRET must contain at least 24 characters")
        if not self.sentry_dsn:warnings.append("SENTRY_DSN is not configured")
        if "example.com" in self.geocoding_user_agent or "local" in self.geocoding_user_agent:warnings.append("GEOCODING_USER_AGENT should identify the production operator")
        return errors,warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
