from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.common.logging import logger


CATALOG_DIR = Path("catalog")

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
}


def read_catalog(
    catalog_dir: Path = CATALOG_DIR,
) -> List[Dict[str, str]]:
    """
    Read all supported catalog files from the catalog directory.

    Every scheduled run reads the current contents of the directory.
    The catalog is used only as input for Spotify and YouTube searches.
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

    rows: List[Dict[str, str]] = []

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
            .astype(str)
            .str.strip()
        )

        dataframe["song_title"] = (
            dataframe["song_title"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        dataframe = dataframe[
            (dataframe["original_artist"] != "")
            & (dataframe["song_title"] != "")
        ]

        rows.extend(
            dataframe.to_dict(orient="records")
        )

    logger.info(
        "Catalog reading completed: %d rows from %d files",
        len(rows),
        len(files),
    )

    return rows


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