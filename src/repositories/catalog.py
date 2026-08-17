from __future__ import annotations

from sqlalchemy import text

from src.common.database import get_connection


def mark_catalog_file_processed(
    file_name: str,
    file_size: int,
    file_checksum: str,
) -> None:
    """
    Mark a catalog file as successfully processed.

    A file is uniquely identified by:
        file_name + file_checksum
    """

    with get_connection() as connection:
        connection.execute(
            text(
                """
                INSERT INTO audit.catalog_file_log (
                    file_id,
                    file_name,
                    file_size,
                    file_checksum,
                    processed_at
                )
                VALUES (
                    gen_random_uuid(),
                    :file_name,
                    :file_size,
                    :file_checksum,
                    NOW()
                )
                ON CONFLICT (file_name, file_checksum)
                DO NOTHING
                """
            ),
            {
                "file_name": file_name,
                "file_size": file_size,
                "file_checksum": file_checksum,
            },
        )