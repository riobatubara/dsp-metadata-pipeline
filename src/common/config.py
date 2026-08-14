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
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "music_metadata")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")

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