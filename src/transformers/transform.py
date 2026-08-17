from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

def _clean_text(value: Any) -> Optional[str]:
    """Normalize text values."""

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _clean_timestamp(value: Any) -> Optional[datetime]:
    """Normalize an ISO-8601 timestamp to UTC."""

    value = _clean_text(value)

    if not value:
        return None

    try:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return timestamp.astimezone(timezone.utc)

    except (TypeError, ValueError):
        return None


def _normalize_text(value: Optional[str]) -> str:
    """Normalize text for matching and deduplication."""

    if not value:
        return ""

    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)

    return value


def _normalize_isrc(value: Optional[str]) -> Optional[str]:
    """Normalize an ISRC value."""

    if not value:
        return None

    return re.sub(r"[\s-]", "", value.strip().upper())


def _standardize_date(date_string: str) -> bool:
    """
    Standardizes a partial or full date string (YYYY, YYYY-MM, or YYYY-MM-DD) 
    into YYYY-MM-DD. Returns None if the string is corrupt or invalid.
    """
    if not date_string or not isinstance(date_string, str):
        return None
        
    date_string = date_string.strip()
    parts = date_string.split("-")
    
    try:
        # Case 1: Full YYYY-MM-DD
        if len(parts) == 3:
            year, month, day = parts
            # Validate real calendar date
            parsed_date = datetime(int(year), int(month), int(day))
            return parsed_date.strftime("%Y-%m-%d")
            
        # Case 2: Partial YYYY-MM (e.g., "2024-12") -> Pad day to 01
        elif len(parts) == 2:
            year, month = parts
            parsed_date = datetime(int(year), int(month), 1)
            return parsed_date.strftime("%Y-%m-01")
            
        # Case 3: Partial YYYY (e.g., "2024") -> Pad month and day to 01-01
        elif len(parts) == 1 and len(date_string) == 4:
            year = parts[0]
            parsed_date = datetime(int(year), 1, 1)
            return parsed_date.strftime("%Y-01-01")
            
    except (ValueError, TypeError):
        return None
        
    return None


def clean_spotify_metadata(
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Clean Spotify metadata before database loading."""

    spotify_metadata = {
        "artist": {},
        "album": {},
        "song": {},
        "song_isrc": {}
    }

    album_info = metadata.get("album", {})

    artist_info = album_info.get("artists")
    for artist in artist_info:
        artist_id = artist.get("id")
        artist_name = artist.get("name")
        if artist_id and artist_id not in spotify_metadata["artist"]:
            spotify_metadata["artist"] = {
                "artist_id": _clean_text(artist_id),
                "artist_name": _clean_text(artist_name),
                "normalized_name": _normalize_text(artist_name)
            }

    album_id = album_info.get("id")
    release_date = album_info.get("release_date")
    if album_id and album_id not in spotify_metadata["album"]:
        spotify_metadata["album"] = {
            "album_id": _clean_text(album_id),
            "album_name": _clean_text(album_info.get("name")),
            "normalize_album_name": _normalize_text(album_info.get("name")),
            "release_date": _standardize_date(release_date)
            # create clean date
        }

    song_id = metadata.get("id")
    if song_id:
        recording_title = metadata.get("name")
        spotify_metadata["song"] = {
            "song_id": _clean_text(song_id),
            "recording_title": _clean_text(recording_title),
            "normalized_title": _normalize_text(recording_title),
            "release_date": _standardize_date(release_date),
            "album_id": album_id
        }

    isrc_code = metadata.get("external_ids", {}).get("isrc")
    if song_id and isrc_code:
        spotify_metadata["song_isrc"] = _normalize_isrc(isrc_code)

    return spotify_metadata


def clean_youtube_metadata(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Clean and standardize YouTube search metadata."""

    video = payload.get("id") or {}
    snippet = payload.get("snippet") or {}

    original_artist = _clean_text(
        payload.get("original_artist")
    )

    song_title = _clean_text(
        payload.get("song_title")
    )

    video_id = _clean_text(video.get("videoId"))

    channel_id = _clean_text(snippet.get("channelId"))
    channel_name = _clean_text(snippet.get("channelTitle"))
    video_title = _clean_text(snippet.get("title"))
    published_at = _clean_timestamp(snippet.get("publishedAt"))

    return {
        "video_id": video_id,
        "channel_id": channel_id,
        "channel_name": channel_name,
        "video_title": video_title,
        "original_artist": original_artist,
        "song_title": song_title,
        "original_artist": original_artist,
        "song_title": song_title,
        "normalized_video_title": _normalize_text(video_title),
        "normalized_artist": _normalize_text(original_artist),
        "normalized_song_title": _normalize_text(song_title),
        "published_at": published_at,
    }

