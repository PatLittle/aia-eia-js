#!/usr/bin/env python3
"""Discover new PDF-only AIAs and recover them before the Pages data build."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from build_aia_jsonl import build_session, package_search_all


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    targets_path = root / "scripts/aia_pdf_recovery_targets.json"
    with tempfile.TemporaryDirectory(prefix="aia-refresh-") as temporary:
        temporary_dir = Path(temporary)
        summary_path = temporary_dir / "summary.json"
        subprocess.run(
            [sys.executable, str(root / "scripts/build_aia_jsonl.py"),
             "--output", str(temporary_dir / "results.jsonl"),
             "--summary-output", str(summary_path)],
            cwd=root, check=True,
        )
        missing = set(json.loads(summary_path.read_text())["missing_package_ids"])
        if not missing:
            print("All catalogue assessments already have usable published or recovered JSON.")
            return

        targets = json.loads(targets_path.read_text(encoding="utf-8"))
        known = {target["package_id"] for target in targets}
        for package in package_search_all(build_session()):
            if package["id"] in missing and package["id"] not in known:
                title = package.get("title_translated") or {}
                targets.append({
                    "package_id": package["id"],
                    "title": title.get("en") or package.get("title") or package["id"],
                    "expected_locales": ["en", "fr"],
                })

        candidate_path = temporary_dir / "targets.json"
        candidate_path.write_text(json.dumps(targets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        subprocess.run(
            [sys.executable, str(root / "scripts/recover_aia_json_from_pdfs.py"),
             "--targets", str(candidate_path),
             "--debug-dir", str(root / "recovery_debug")],
            cwd=root, check=True,
        )
        # Save newly discovered targets only after recovery and the bilingual control pass.
        targets_path.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
