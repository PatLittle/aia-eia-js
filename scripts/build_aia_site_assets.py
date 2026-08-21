#!/usr/bin/env python3
"""Prepare AIA site assets from the unified JSON Lines dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"JSONL line {line_number} is not an object")
            records.append(value)
    return records


def build_completed_aia_index(records: list[dict[str, Any]], output_path: Path) -> int:
    rows: list[dict[str, Any]] = []
    for record in records:
        derived = record.get("derived") or {}
        resource_url = str(record.get("resource_url") or "").strip()
        if not resource_url:
            continue
        rows.append(
            {
                "package_id": record.get("package_id", ""),
                "title_en": record.get("title_en", ""),
                "title_fr": record.get("title_fr", ""),
                "organization_en": record.get("organization_en", ""),
                "organization_fr": record.get("organization_fr", ""),
                "publication_date": record.get("metadata_created", ""),
                "aia_version": record.get("version", ""),
                "impact_level": derived.get("impact_level_label", ""),
                "dataset_url": record.get("dataset_url", ""),
                "resource_url": resource_url,
                "source": record.get("source", "published"),
            }
        )

    rows.sort(
        key=lambda row: (
            str(row.get("organization_en") or ""),
            str(row.get("title_en") or ""),
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(rows)


def build_legacy_report_redirect(output_path: Path) -> None:
    target = "./AnalysisReport"
    output_path.write_text(
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        "<title>AIA analysis</title></head><body>"
        f'<p><a href="{target}">Open the AIA analysis</a></p>'
        f"<script>location.replace({json.dumps(target)} + location.search + "
        "location.hash);</script></body></html>\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    args = parser.parse_args()

    records = read_jsonl(args.jsonl)
    asset_dir = args.public_dir / "aia-analysis-data"
    asset_dir.mkdir(parents=True, exist_ok=True)
    completed_count = build_completed_aia_index(
        records,
        asset_dir / "completed-aias.json",
    )
    build_legacy_report_redirect(args.public_dir / "aia_analysis_report.html")
    print(f"Prepared {completed_count} completed AIA links from the JSONL dataset.")


if __name__ == "__main__":
    main()
