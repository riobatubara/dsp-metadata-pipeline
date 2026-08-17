from __future__ import annotations

from sqlalchemy import text
from typing import Any, Dict, Optional

from src.common.database import get_connection
from src.common.logging import logger


class SpotifyRepository:
    """Persist spotify metadata into database."""

    def upsert_spotify_metadata(
        self,
        metadata: Dict[str, Any],
    ) -> int:
        """Upsert a Spotify track and its related entities.
        """

        connection = get_connection()

        try:
            with get_connection() as connection:
                artist = metadata.get("artist")
                album = metadata.get("album")
                song = metadata.get("song")

                artist_id = artist.get("artist_id")
                album_id = album.get("album_id")
                isrc = metadata.get("song_isrc")
                release_date = album.get("release_date")

                self._upsert_artist(
                    connection,
                    artist_id,
                    artist_name=artist["artist_name"],
                    normalized_name=artist["normalized_name"],
                )

                self._upsert_album(
                    connection,
                    album_id,
                    album_name=album.get("album_name"),
                    normalize_album_name=album.get("normalize_album_name"),
                    release_date=release_date,
                )

                song_id = self._upsert_song(
                    connection,
                    recording_title=song["recording_title"],
                    normalized_title=song["normalized_title"],
                    release_date=release_date,
                    album_id=album_id,
                )

                if artist_id and song_id:
                    self._upsert_song_artist(
                        connection,
                        song_id,
                        artist_id
                    )

                    spotify_track_id = self._upsert_spotify_track(
                        connection,
                        song_id
                    )

                    if song_id and spotify_track_id and isrc:
                        self._upsert_song_isrc(
                            connection,
                            song_id,
                            isrc,
                            spotify_track_id
                        )

            logger.info(
                "Spotify metadata persisted: artist_id=%s, album_id=%s, isrc=%s, release_date=%s",
                artist_id,
                album_id,
                isrc,
                release_date,
            )

        except Exception:
            logger.exception("Failed to persist Spotify metadata.")
            raise


    @staticmethod
    def _upsert_artist(
        connection: Any,
        artist_id: str,
        artist_name: str,
        normalized_name: str,
    ) -> int:
        """create an artist."""

        connection.execute(
            text(
                """
                INSERT INTO core.artist (
                    artist_id,
                    artist_name,
                    normalized_name
                )
                VALUES (
                    :artist_id,
                    :artist_name,
                    :normalized_name
                )
                ON CONFLICT (artist_id)
                DO NOTHING
                """
            ),
            {
                "artist_id": artist_id,
                "artist_name": artist_name,
                "normalized_name": normalized_name,
            },
        )


    @staticmethod
    def _upsert_album(
        connection: Any,
        album_id: str,
        album_name: str,
        normalize_album_name: Optional[str],
        release_date: Optional[Any],
    ) -> Optional[int]:
        """create an album."""

        if not album_name:
            return None

        connection.execute(
            text(
                """
                INSERT INTO core.album (
                    album_id,
                    album_name,
                    normalize_album_name,
                    release_date
                )
                VALUES (
                    :album_id,
                    :album_name,
                    :normalize_album_name,
                    :release_date
                )
                ON CONFLICT (album_id)
                DO NOTHING
                """
            ),
            {
                "album_id": album_id,
                "album_name": album_name,
                "normalize_album_name": normalize_album_name,
                "release_date": release_date,
            },
        )


    @staticmethod
    def _upsert_song(
        connection: Any,
        recording_title: str,
        normalized_title: str,
        release_date: Optional[Any],
        album_id: str,
    ) -> int:
        """create a song."""

        result  = connection.execute(
            text(
                """
                INSERT INTO core.song (
                    recording_title,
                    normalized_title,
                    release_date,
                    album_id
                )
                VALUES (
                    :recording_title,
                    :normalized_title,
                    :release_date,
                    :album_id
                )
                ON CONFLICT (normalized_title, album_id) 
                DO UPDATE SET recording_title = EXCLUDED.recording_title
                RETURNING song_id
                """
            ),
            {
                "recording_title":recording_title,
                "normalized_title":normalized_title,
                "release_date":release_date,
                "album_id":album_id,
            },
        )

        row = result.scalar_one_or_none()
        return row if row else None


    @staticmethod
    def _upsert_song_artist(
        connection: Any,
        song_id: str,
        artist_id: str,
    ) -> int:
        """create a song_artist."""

        connection.execute(
            text(
                """
                INSERT INTO core.song_artist (
                    song_id,
                    artist_id
                )
                VALUES (
                    :song_id,
                    :artist_id
                )
                ON CONFLICT (song_id, artist_id) 
                DO NOTHING
                """
            ),
            {
                "song_id":song_id,
                "artist_id":artist_id,
            },
        )


    @staticmethod
    def _upsert_spotify_track(
        connection: Any,
        song_id: str,
    ) -> int:
        """create a spotify_track."""

        result = connection.execute(
            text(
                """
                INSERT INTO core.spotify_track (
                    song_id
                )
                VALUES (
                    :song_id
                )
                ON CONFLICT (song_id) 
                DO UPDATE SET song_id = EXCLUDED.song_id
                RETURNING spotify_track_id
                """
            ),
            {
                "song_id":song_id,
            },
        )

        row = result.scalar_one_or_none()
        return row if row else None


    @staticmethod
    def _upsert_song_isrc(
        connection: Any,
        song_id: str,
        isrc: str,
        spotify_track_id: str,
    ) -> int:
        """create a song_isrc."""

        connection.execute(
            text(
                """
                INSERT INTO core.song_isrc (
                    song_id,
                    isrc,
                    spotify_track_id
                )
                VALUES (
                    :song_id,
                    :isrc,
                    :spotify_track_id
                )
                ON CONFLICT (song_id, isrc) 
                DO NOTHING
                """
            ),
            {
                "song_id":song_id,
                "isrc":isrc,
                "spotify_track_id":spotify_track_id,
            },
        )
