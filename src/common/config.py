import os
from dataclasses import dataclass

from dotenv import load_dotenv



# How to use
# from src.common.config import settings

# print(settings.postgres_host)
# print(settings.spotify_client_id)


# Load variables from .env
load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Application
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # PostgreSQL
    db_host: str = os.getenv("DB_HOST", "postgres")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "music_metadata")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "postgres")

    # Spotify
    spotify_client_id: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")

    # YouTube
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")

    # Google Sheets
    google_sheet_id: str = os.getenv("GOOGLE_SHEET_ID", "")
    google_credentials_path: str = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS",
        "",
    )


settings = Settings()