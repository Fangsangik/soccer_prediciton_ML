from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DB_PATH: str = "data/football.duckdb"
    FOOTBALL_DATA_API_KEY: str = ""
    API_FOOTBALL_KEY: str = ""
    FPL_API_BASE: str = "https://fantasy.premierleague.com/api"
    MOCK_DATA: bool = True
    API_PORT: int = 8000


settings = Settings()
