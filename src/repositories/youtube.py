from __future__ import annotations

from sqlalchemy import text
from typing import Any, Dict

from src.common.database import get_connection
from src.common.logging import logger


class YoutubeRepository:
    """Persist youTube metadata into database."""

    def upsert_youtube_metadata(
        self,
        metadata: Dict[str, Any],
    ) -> None:
        """Upsert YouTube channel and video metadata."""

        try:
            with get_connection() as connection:
                channel_id = metadata.get("channel_id")

                if channel_id:
                    connection.execute(
                        text(
                            """
                            INSERT INTO core.youtube_channel (
                                channel_id,
                                channel_name
                            )
                            VALUES (
                                :channel_id,
                                :channel_name
                            )
                            ON CONFLICT (channel_id)
                            DO UPDATE SET
                                channel_name = EXCLUDED.channel_name,
                                updated_at = NOW()
                            """
                        ),
                        {
                            "channel_id": channel_id,
                            "channel_name": metadata.get("channel_name"),
                        },
                    )

                connection.execute(
                    text(
                        """
                        INSERT INTO core.youtube_video (
                            video_id,
                            channel_id,
                            video_title,
                            normalized_video_title,
                            song_title,
                            normalized_song_title,
                            artist_name,
                            normalized_artist_name,
                            published_at
                        )
                        VALUES (
                            :video_id,
                            :channel_id,
                            :video_title,
                            :normalized_video_title,
                            :song_title,
                            :normalized_song_title,
                            :artist_name,
                            :normalized_artist_name,
                            :published_at
                        )
                        ON CONFLICT (video_id)
                        DO UPDATE SET
                            channel_id = EXCLUDED.channel_id,
                            video_title = EXCLUDED.video_title,
                            normalized_video_title =
                                EXCLUDED.normalized_video_title,
                            song_title = EXCLUDED.song_title,
                            normalized_song_title =
                                EXCLUDED.normalized_song_title,
                            artist_name = EXCLUDED.artist_name,
                            normalized_artist_name =
                                EXCLUDED.normalized_artist_name,
                            published_at = EXCLUDED.published_at,
                            updated_at = NOW()
                        """
                        ),
                        {
                            "video_id": metadata.get("video_id"),
                            "channel_id": channel_id,
                            "video_title": metadata.get("video_title"),
                            "normalized_video_title": metadata.get(
                                "normalized_video_title"
                            ),
                            "song_title": metadata.get("song_title"),
                            "normalized_song_title": metadata.get(
                                "normalized_song_title"
                            ),
                            "artist_name": metadata.get("original_artist"),
                            "normalized_artist_name": metadata.get(
                                "normalized_artist"
                            ),
                            "published_at": metadata.get("published_at"),
                        },
                    )

            logger.info(
                "YouTube metadata persisted: video_id=%s",
                metadata.get("video_id"),
            )

        except Exception:
            logger.exception(
                "Failed to persist YouTube metadata."
            )
            raise