#!/usr/bin/env python3
"""Prepare generated AIA report assets for the Vue application."""

import argparse
import csv
import json
import re
from pathlib import Path


def build_completed_aia_index(csv_path: Path, output_path: Path) -> int:
    with csv_path.open(encoding="utf-8-sig", newline="") as source:
        rows = [
            {
                "package_id": row.get("package_id", ""),
                "title": row.get("package_title_en", ""),
                "organization": row.get("organization_en", ""),
                "publication_date": row.get("publication_date", ""),
                "aia_version": row.get("aia_version", ""),
                "impact_level": row.get("impact_level", ""),
                "dataset_url": row.get("dataset_url", ""),
                "resource_url": row.get("resource_url", ""),
            }
            for row in csv.DictReader(source)
            if row.get("resource_url", "").strip()
            and row.get("has_usable_json", "").lower() == "true"
        ]

    rows.sort(key=lambda row: (row["organization"], row["title"]))
    output_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(rows)


def namespace_report_css(css: str) -> str:
    def prefix_block(match: re.Match[str]) -> str:
        selectors, declarations = match.groups()
        prefixed = []
        for selector in selectors.split(","):
            selector = selector.strip()
            if selector in {":root", "body"}:
                prefixed.append(".analysis-report")
            elif selector.startswith("@"):
                prefixed.append(selector)
            else:
                prefixed.append(f".analysis-report {selector}")
        return f"{', '.join(prefixed)} {{{declarations}}}"

    return re.sub(r"([^{}]+)\{([^{}]*)\}", prefix_block, css)


def build_report_fragment(report_path: Path, output_path: Path) -> None:
    report_html = report_path.read_text(encoding="utf-8")
    style_match = re.search(r"<style[^>]*>(.*?)</style>", report_html, re.I | re.S)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", report_html, re.I | re.S)
    if not body_match:
        raise ValueError("The generated report does not contain a body element.")

    css = namespace_report_css(style_match.group(1)) if style_match else ""
    fragment = (
        f"<style>{css}</style>\n"
        f'<article class="analysis-report">{body_match.group(1).strip()}</article>\n'
    )
    output_path.write_text(fragment, encoding="utf-8")


def build_legacy_report_redirect(output_path: Path) -> None:
    target = "./AnalysisReport"
    output_path.write_text(
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={target}">'
        "<title>AIA analysis report</title></head><body>"
        f'<p><a href="{target}">Open the AIA analysis report</a></p>'
        f"<script>location.replace({json.dumps(target)} + location.search + "
        "location.hash);</script></body></html>\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--public-dir", type=Path, required=True)
    args = parser.parse_args()

    asset_dir = args.public_dir / "aia-analysis-data"
    asset_dir.mkdir(parents=True, exist_ok=True)
    completed_count = build_completed_aia_index(
        args.report_dir / "aia_report_assessments.csv",
        asset_dir / "completed-aias.json",
    )
    build_report_fragment(
        args.report_dir / "aia_analysis_report.html",
        asset_dir / "aia-analysis-report-content.html",
    )
    build_legacy_report_redirect(args.public_dir / "aia_analysis_report.html")
    print(f"Prepared {completed_count} completed AIA links and the report page.")


if __name__ == "__main__":
    main()
