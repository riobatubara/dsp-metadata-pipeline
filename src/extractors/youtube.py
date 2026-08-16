from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build

from src.common.config import settings
from src.common.logging import logger


YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"


class YouTubeClient:
    """Client for YouTube Data API v3 using google-api-python-client."""

    def __init__(self, min_request_interval: float = 1.0) -> None:
        if not settings.youtube_api_key:
            raise ValueError("YOUTUBE_API_KEY is not configured.")

        self.min_request_interval = min_request_interval
        self._last_request_at: Optional[float] = None

        self.youtube = build(
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            developerKey=settings.youtube_api_key,
            cache_discovery=False,
        )


    def search_videos(
        self,
        original_artist: Optional[str],
        song_title: str,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search YouTube for music videos matching artist and title."""

        if not song_title or not song_title.strip():
            raise ValueError("song_title is required.")

        song_title = song_title.strip()

        artist = (
            original_artist.strip()
            if isinstance(original_artist, str)
            and original_artist.strip()
            else None
        )

        query = f"{artist} {song_title}" if artist else song_title

        self._wait_for_rate_limit()

        response = (
            self.youtube.search()
            .list(
                part="snippet",
                q=query,
                type="video",
                videoCategoryId="10",
                regionCode="ID",
                maxResults=max_results,
            )
            .execute(num_retries=3)
        )

        self._last_request_at = time.monotonic()

        items: List[Dict[str, Any]] = []

        for item in response.get("items", []):
            snippet = item.get("snippet") or {}
            video_title = snippet.get("title") or ""

            cleaned_title = re.sub(r"[^\w\s\-]", "", video_title)
            cleaned_title = re.sub(r"\s+", " ", cleaned_title).strip()

            if song_title.lower() in cleaned_title.lower():
                items.append(item)

        logger.info(
            "YouTube search completed: artist=%s title=%s results=%d",
            original_artist,
            song_title,
            len(items),
        )

        return items


    def close(self) -> None:
        """Close the underlying HTTP connection."""

        http = getattr(self.youtube, "_http", None)

        if http is not None and hasattr(http, "close"):
            http.close()


    def __enter__(self) -> "YouTubeClient":
        return self


    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()
