from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from sqlalchemy import text

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.extractors.spotify import SpotifyClient
from src.extractors.youtube import YouTubeClient

from src.common.logging import logger
from src.common.database import get_connection
from src.readers.catalog import read_catalog, scan_catalog
from src.repositories.catalog import mark_catalog_file_processed

from src.repositories.spotify import SpotifyRepository
from src.repositories.youtube import YoutubeRepository
from src.transformers.transform import (
    clean_spotify_metadata,
    clean_youtube_metadata,
)


def create_ingestion(source_name: str) -> str:
    ingestion_id = str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute(
            text("""
                INSERT INTO audit.ingestion_log (
                    ingestion_id,
                    source_name,
                    started_at,
                    status
                )
                VALUES (:ingestion_id, :source_name, :started_at, 'RUNNING')
            """),
            {
                "ingestion_id": ingestion_id,
                "source_name": source_name,
                "started_at": datetime.now(timezone.utc),
            },
        )
    return ingestion_id


def finish_ingestion(
    ingestion_id: str,
    status: str,
    records_read: int,
    records_written: int,
    error_message: str | None = None,
) -> None:
    with get_connection() as connection:
        connection.execute(
            text("""
                UPDATE audit.ingestion_log
                SET completed_at = :completed_at,
                    status = :status,
                    records_read = :records_read,
                    records_written = :records_written,
                    error_message = :error_message
                WHERE ingestion_id = :ingestion_id
            """),
            {
                "completed_at": datetime.now(timezone.utc),
                "status": status,
                "records_read": records_read,
                "records_written": records_written,
                "error_message": error_message,
                "ingestion_id": ingestion_id,
            },
        )


def extract_spotify(
    catalog: list[dict[str, str]],
) -> str:
    ingestion_id = create_ingestion("spotify")

    records_written = 0

    try:
        spotify = SpotifyClient()

        with get_connection() as connection:
            for row in catalog:
                results = spotify.search_track(
                    original_artist=row.get("original_artist"),
                    song_title=row.get("song_title"),
                )

                for track in results:
                    connection.execute(
                        text(
                            """
                            INSERT INTO raw.spotify (
                                ingestion_id,
                                original_artist,
                                song_title,
                                track_id,
                                response_json
                            )
                            VALUES (
                                :ingestion_id,
                                :original_artist,
                                :song_title,
                                :track_id,
                                CAST(:response_json AS JSONB)
                            )
                            """
                        ),
                        {
                            "ingestion_id": ingestion_id,
                            "original_artist": "8 ball",
                            "song_title": "bertahan hidup",
                            "track_id": track.get("id"),
                            "response_json": json.dumps(track),
                        },
                    )
                
                    records_written += 1
                
        finish_ingestion(
            ingestion_id,
            "SUCCESS",
            len(catalog),
            records_written,
        )

        logger.info(
            "Spotify extraction completed: ingestion_id=%s "
            "records_read=%d records_written=%d",
            ingestion_id,
            len(catalog),
            records_written,
        )

        return ingestion_id
                
    except Exception as exc:
        finish_ingestion(
            ingestion_id,
            "FAILED",
            1,
            records_written,
            str(exc),
        )
        raise


def extract_youtube(
    catalog: list[dict[str, str]],
) -> str:
    ingestion_id = create_ingestion("youtube")

    records_written = 0

    try:
        youtube = YouTubeClient()

        with get_connection() as connection:
            for row in catalog:
                results = youtube.search_videos(
                    original_artist=row.get("original_artist"),
                    song_title=row.get("song_title"),
                )

                for result in results:
                    video_id = result.get("id", {}).get("videoId")

                    if not video_id:
                        continue

                    connection.execute(
                        text(
                            """
                            INSERT INTO raw.youtube (
                                ingestion_id,
                                original_artist,
                                song_title,
                                video_id,
                                response_json
                            )
                            VALUES (
                                :ingestion_id,
                                :original_artist,
                                :song_title,
                                :video_id,
                                CAST(:response_json AS JSONB)
                            )
                            """
                        ),
                        {
                            "ingestion_id": ingestion_id,
                            "original_artist": "8 ball",
                            "song_title": "bertahan hidup",
                            "video_id": video_id,
                            "response_json": json.dumps(result),
                        },
                    )
    
                    records_written += 1
                    
        finish_ingestion(
            ingestion_id,
            "SUCCESS",
            len(catalog),
            records_written,
        )

        logger.info(
            "YouTube extraction completed: ingestion_id=%s "
            "records_read=%d records_written=%d",
            ingestion_id,
            len(catalog),
            records_written,
        )

        return ingestion_id
        
    except Exception as exc:
        finish_ingestion(
            ingestion_id,
            "FAILED",
            1,
            records_written,
            str(exc),
        )
        raise


def scan_catalog_task(**context: Any) -> list[dict[str, Any]]:
    """
    Find catalog files that have not been processed yet.

    Only file metadata is returned through XCom.
    Catalog rows are never pushed to XCom.
    """

    files_to_process = scan_catalog()

    logger.info(
        "Catalog scan found %d file(s) to process",
        len(files_to_process),
    )

    for catalog_file in files_to_process:
        logger.info(
            "File ready for processing: %s",
            catalog_file["file_name"],
        )

    return files_to_process


def extract_catalog(**context: Any) -> None:
    """
    Process each new catalog file.

    Each file is read exactly once. The resulting rows are then
    passed directly to Spotify and YouTube extraction.
    """

    ti = context["ti"]

    files_to_process = context["ti"].xcom_pull(
        task_ids="scan_catalog",
    )

    if not files_to_process:
        logger.info("No new catalog files to process.")
        return

    spotify_ingestion_ids: list[str] = []
    youtube_ingestion_ids: list[str] = []

    for catalog_file in files_to_process:
        file_name = catalog_file["file_name"]
        file_path = Path(catalog_file["file_path"])

        logger.info(
            "Processing catalog file: %s",
            file_name,
        )

        # Read this catalog file exactly once.
        catalog = read_catalog(file_path)

        logger.info(
            "Catalog file %s produced %d rows",
            file_name,
            len(catalog),
        )

        spotify_ingestion_id = extract_spotify(catalog)
        youtube_ingestion_id = extract_youtube(catalog)

        spotify_ingestion_ids.append(
            spotify_ingestion_id
        )

        youtube_ingestion_ids.append(
            youtube_ingestion_id
        )

    ti.xcom_push(
        key="spotify_ingestion_ids",
        value=spotify_ingestion_ids,
    )

    ti.xcom_push(
        key="youtube_ingestion_ids",
        value=youtube_ingestion_ids,
    )

    logger.info(
        "Catalog extraction completed: spotify=%d youtube=%d",
        len(spotify_ingestion_ids),
        len(youtube_ingestion_ids),
    )


def transform_and_load(**context: Any) -> None:
    """
    Transform and load all Spotify and YouTube extraction results.
    """

    ti = context["ti"]

    spotify_ingestion_ids = ti.xcom_pull(
        task_ids="extract_catalog",
        key="spotify_ingestion_ids",
    ) or []

    youtube_ingestion_ids = ti.xcom_pull(
        task_ids="extract_catalog",
        key="youtube_ingestion_ids",
    ) or []

    spotifyRepository = SpotifyRepository()
    youtubeRepository = YoutubeRepository()

    spotify_records_processed = 0
    youtube_records_processed = 0

    with get_connection() as connection:
        # Spotify
        for ingestion_id in spotify_ingestion_ids:
            cursor = connection.execute(
                text("""
                    SELECT
                        original_artist,
                        song_title,
                        response_json
                    FROM raw.spotify
                    WHERE ingestion_id = :ingestion_id
                    ORDER BY raw_id
                """),
                {"ingestion_id": ingestion_id}
            )
            spotify_rows = cursor.fetchall()

            for row in spotify_rows:
                payload = row.response_json

                payload["original_artist"] = row.original_artist
                payload["song_title"] = row.song_title

                metadata = clean_spotify_metadata(payload)

                logger.info(
                    "Spotify metadata before upsert: %s",
                    metadata,
                )

                spotifyRepository.upsert_spotify_metadata(metadata)

                spotify_records_processed += 1


        # YouTube
        for ingestion_id in youtube_ingestion_ids:
            cursor = connection.execute(
                text("""
                    SELECT
                        original_artist,
                        song_title,
                        response_json
                    FROM raw.youtube
                    WHERE ingestion_id = :ingestion_id
                    ORDER BY raw_id
                """),
                {"ingestion_id": ingestion_id}
            )
            youtube_rows = cursor.fetchall()
                        
            for row in youtube_rows:
                payload = row.response_json

                payload["original_artist"] = row.original_artist
                payload["song_title"] = row.song_title

                metadata = clean_youtube_metadata(payload)
                
                logger.info(
                    "YouTube metadata before upsert: %s",
                    metadata,
                )

                youtubeRepository.upsert_youtube_metadata(metadata)

                youtube_records_processed += 1

    logger.info(
        "Transformation completed: spotify=%d youtube=%d",
        spotify_records_processed,
        youtube_records_processed,
    )


def mark_catalog_files_processed(**context: Any) -> None:
    """
    Mark catalog files as processed only after extraction
    and transformation have succeeded.
    """

    ti = context["ti"]

    files_to_process = ti.xcom_pull(
        task_ids="scan_catalog",
    )

    if not files_to_process:
        logger.info("No catalog files to mark as processed.")
        return

    for catalog_file in files_to_process:
        mark_catalog_file_processed(
            file_name=catalog_file["file_name"],
            file_size=catalog_file["file_size"],
            file_checksum=catalog_file["file_checksum"],
        )

        logger.info(
            "Catalog file marked as processed: %s",
            catalog_file["file_name"],
        )

with DAG(
    dag_id="etl_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["catalog"],
) as dag:

    scan_catalog_operator = PythonOperator(
        task_id="scan_catalog",
        python_callable=scan_catalog_task,
    )

    extract_catalog_operator = PythonOperator(
        task_id="extract_catalog",
        python_callable=extract_catalog,
    )

    transform_and_load_operator = PythonOperator(
        task_id="transform_and_load",
        python_callable=transform_and_load,
    )

    mark_catalog_files_processed_operator = PythonOperator(
        task_id="mark_catalog_files_processed",
        python_callable=mark_catalog_files_processed,
    )

    # scan_catalog_operator >> extract_catalog_operator
    (
        scan_catalog_operator
        >> extract_catalog_operator
        >> transform_and_load_operator
        >> mark_catalog_files_processed_operator
    )