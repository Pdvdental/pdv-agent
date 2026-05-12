from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # Chatwoot
    chatwoot_base_url: str
    chatwoot_account_id: int = 1
    chatwoot_inbox_id: int
    chatwoot_api_access_token: str
    chatwoot_hmac_token: str
    chatwoot_bot_user_id: int

    # Google Calendar
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    google_calendar_id: str = "primary"

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # App
    clinic_name: str = "PDV Policlínica Dental del Vallès"
    clinic_phone_human: str = "+34677523665"
    timezone: str = "Europe/Madrid"
    slot_duration_minutes: int = 30
    working_hours_start: str = "09:00"
    working_hours_end: str = "20:00"
    working_days: str = "1,2,3,4"  # Lun-Jue (ISO: 1=lunes)
    internal_api_token: str
    log_level: str = "INFO"

    # Meta webhook diagnostic proxy (optional)
    meta_proxy_verify_token: str = ""
    meta_proxy_app_secret: str = ""
    meta_proxy_forward_url: str = ""

    # Direct WhatsApp handler bypass (Chatwoot worker bypass)
    direct_handler_enabled: bool = False
    meta_graph_token: str = ""
    meta_phone_number_id: str = ""
    meta_graph_api_version: str = "v19.0"
    escalation_alert_phone: str = ""  # E.164 with +, e.g. +34677523665

    @property
    def working_days_list(self) -> list[int]:
        return [int(d) for d in self.working_days.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()