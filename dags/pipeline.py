from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.common.logging import logger
from src.readers.catalog import read_catalog, scan_catalog
from src.repositories.catalog import mark_catalog_file_processed


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

    files_to_process = context["ti"].xcom_pull(
        task_ids="scan_catalog",
    )

    if not files_to_process:
        logger.info("No new catalog files to process.")
        return

    logger.info(
        "Processing %d catalog file(s)",
        len(files_to_process),
    )

    for catalog_file in files_to_process:
        file_name = catalog_file["file_name"]
        file_path = Path(catalog_file["file_path"])

        logger.info(
            "Processing catalog file: %s",
            file_name,
        )

        # Read this catalog file exactly once.
        rows = read_catalog(file_path)

        logger.info(
            "Catalog file %s produced %d rows",
            file_name,
            len(rows),
        )

        # ---------------------------------------------------------
        # Spotify extraction
        # ---------------------------------------------------------

        # extract_spotify(rows)

        # ---------------------------------------------------------
        # YouTube extraction
        # ---------------------------------------------------------

        # extract_youtube(rows)

        # ---------------------------------------------------------
        # Only mark the file as processed after BOTH extractors
        # have completed successfully.
        # ---------------------------------------------------------

        mark_catalog_file_processed(
            file_name=catalog_file["file_name"],
            file_size=catalog_file["file_size"],
            file_checksum=catalog_file["file_checksum"],
        )

        logger.info(
            "Catalog file marked as processed: %s",
            file_name,
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

    scan_catalog_operator >> extract_catalog_operator