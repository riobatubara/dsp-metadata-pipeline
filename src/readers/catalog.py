from __future__ import annotations

import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import text

from src.common.database import get_connection
from src.common.logging import logger


CATALOG_DIR = Path("catalog")

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
}


def calculate_checksum(file: Path) -> str:
    """Calculate SHA-256 checksum for a file."""

    sha256 = hashlib.sha256()

    with file.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def scan_catalog(
    catalog_dir: Path = CATALOG_DIR,
) -> List[Dict[str, Any]]:
    """
    Scan supported catalog files and check whether each file
    has already been processed.

    A file is considered previously processed when the same
    filename and checksum exist in audit.catalog_file_log.
    """

    if not catalog_dir.exists():
        raise FileNotFoundError(
            f"Catalog directory does not exist: {catalog_dir}"
        )

    if not catalog_dir.is_dir():
        raise NotADirectoryError(
            f"Catalog path is not a directory: {catalog_dir}"
        )

    files = sorted(
        file
        for file in catalog_dir.iterdir()
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        logger.warning(
            "No catalog files found in %s",
            catalog_dir,
        )
        return []

    scanned_files: List[Dict[str, Any]] = []

    with get_connection() as connection:
        for file in files:
            file_size = file.stat().st_size
            file_checksum = calculate_checksum(file)

            result = connection.execute(
                text(
                    """
                    SELECT 1
                    FROM audit.catalog_file_log
                    WHERE file_name = :file_name
                      AND file_checksum = :file_checksum
                    LIMIT 1
                    """
                ),
                {
                    "file_name": file.name,
                    "file_checksum": file_checksum,
                },
            )

            already_processed = result.scalar() is not None

            scanned_files.append(
                {
                    "file_name": file.name,
                    "file_path": str(file),
                    "file_size": file_size,
                    "file_checksum": file_checksum,
                    "already_processed": already_processed,
                }
            )

            logger.info(
                "Catalog file: name=%s size=%d checksum=%s processed=%s",
                file.name,
                file_size,
                file_checksum,
                already_processed,
            )

    logger.info(
        "Catalog scan completed: %d files",
        len(scanned_files),
    )

    return scanned_files


def normalize_text(value: object) -> str:
    """
    Normalize catalog text for matching.

    - Convert to lowercase
    - Remove leading/trailing whitespace
    - Remove non-alphanumeric characters
    - Preserve spaces in the actual value
    """

    if pd.isna(value):
        return ""

    value = str(value).lower().strip()

    return re.sub(r"[^a-z0-9 ]", "", value)


def dedup_key(value: str) -> str:
    """
    Create a comparison key.

    Spaces are removed only for deduplication.
    The original normalized value keeps its spaces.
    """
    return value.replace(" ", "")


def read_catalog(
    catalog_dir: Path = CATALOG_DIR,
) -> List[Dict[str, Any]]:
    """
    Read catalog files while preserving file boundaries.

    Each file contains its own metadata and normalized rows.
    """

    if not catalog_dir.exists():
        raise FileNotFoundError(
            f"Catalog directory does not exist: {catalog_dir}"
        )

    files = sorted(
        file
        for file in catalog_dir.iterdir()
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        logger.warning(
            "No catalog files found in %s",
            catalog_dir,
        )
        return []

    catalog_files: List[Dict[str, Any]] = []

    for file in files:
        logger.info("Reading catalog file: %s", file)

        dataframe = _read_file(file)

        dataframe.columns = [
            column.strip().lower().replace(" ", "_")
            for column in dataframe.columns
        ]

        required_columns = {
            "original_artist",
            "song_title",
        }

        missing_columns = required_columns - set(dataframe.columns)

        if missing_columns:
            raise ValueError(
                f"{file} is missing required columns: "
                f"{sorted(missing_columns)}"
            )

        dataframe = dataframe[
            ["original_artist", "song_title"]
        ].copy()

        dataframe["original_artist"] = (
            dataframe["original_artist"]
            .fillna("")
            .apply(normalize_text)
        )

        dataframe["song_title"] = (
            dataframe["song_title"]
            .fillna("")
            .apply(normalize_text)
        )

        dataframe = dataframe[
            dataframe["song_title"] != ""
        ]

        dataframe["_artist_key"] = (
            dataframe["original_artist"]
            .apply(dedup_key)
        )

        dataframe["_title_key"] = (
            dataframe["song_title"]
            .apply(dedup_key)
        )

        dataframe = dataframe[
            dataframe["_title_key"] != ""
        ]

        dataframe = dataframe.drop_duplicates(
            subset=[
                "_artist_key",
                "_title_key",
            ],
            keep="first",
        )

        rows = dataframe[
            ["original_artist", "song_title"]
        ].to_dict(orient="records")

        catalog_files.append(
            {
                "file_name": file.name,
                "file_path": str(file),
                "file_size": file.stat().st_size,
                "file_checksum": calculate_checksum(file),
                "rows": rows,
            }
        )

        logger.info(
            "Catalog file read: %s (%d rows)",
            file.name,
            len(rows),
        )

    logger.info(
        "Catalog reading completed: %d files",
        len(catalog_files),
    )

    return catalog_files


def _read_file(file: Path) -> pd.DataFrame:
    """Read a supported catalog file."""

    suffix = file.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file)

    raise ValueError(
        f"Unsupported catalog file format: {file}"
    )