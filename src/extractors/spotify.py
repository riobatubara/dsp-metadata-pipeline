from __future__ import annotations

from typing import Any, Dict, List, Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from src.common.config import settings
from src.common.logging import logger


class SpotifyClient:
    """Client for Spotify authentication and track metadata."""

    def __init__(self) -> None:
        if not settings.spotify_client_id:
            raise ValueError("SPOTIFY_CLIENT_ID is not configured.")

        if not settings.spotify_client_secret:
            raise ValueError("SPOTIFY_CLIENT_SECRET is not configured.")

        self.client = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=settings.spotify_client_id,
                client_secret=settings.spotify_client_secret,
            )
        )

    def search_track(
        self,
        original_artist: str,
        song_title: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search Spotify for tracks using artist and title."""

        if not song_title or not song_title.strip():
            raise ValueError("song_title is required.")

        query_parts = [f'track:"{song_title.strip()}"']

        if original_artist and original_artist.strip():
            query_parts.insert(
                0,
                f'artist:"{original_artist.strip()}"',
            )

        response = self.client.search(
            q=" ".join(query_parts),
            type="track",
            limit=limit,
        )

        tracks = response.get("tracks") or {}

        if not isinstance(tracks, dict):
            return []

        items = tracks.get("items") or []

        if not isinstance(items, list):
            return []

        logger.info(
            "Spotify search completed: artist=%s title=%s results=%d",
            original_artist,
            song_title,
            len(items),
        )

        return items
