from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://leadgen:leadgen@localhost:5432/leadgen"

    google_places_api_key: str = ""

    # "places" or "outscraper" — swap without touching company_finder.py
    company_discovery_provider: str = "outscraper"
    outscraper_api_key: str = ""
    serpapi_api_key: str = ""

    hunter_api_key: str = ""

    odoo_url: str = ""
    odoo_db: str = ""
    odoo_username: str = ""
    odoo_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
