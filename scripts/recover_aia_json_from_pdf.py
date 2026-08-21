#!/usr/bin/env python3
"""Reconstruct saved AIA JSON files from published AIA result PDFs.

The AIA web application saves a compact SurveyFile object containing:
    version, currentPage, data, translationsOnResult

This script downloads AIA packages from open.canada.ca, identifies the English
and French AIA result PDFs (excluding peer-review/summary documents), extracts
question/answer text, maps displayed answers back to the raw SurveyJS values in
the matching version of survey-enfr.json, and writes loadable SurveyFile JSON.

A known-good CBSA package (CRES/ReportIn) containing both PDF and JSON is used as
a regression control.  The control report is written to the debug directory so
GitHub Actions can enforce reconstruction quality before publishing results.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import fitz  # PyMuPDF
import requests
from rapidfuzz import fuzz

CKAN_API = "https://open.canada.ca/data/api/3/action/package_show?id={}"
CONTROL_PACKAGE_ID = "eaeb269c-6ac5-4429-a5aa-1fcc07c77933"
CONTROL_JSON_RESOURCE_ID = "dd83f660-f2c3-4de1-a953-2174e07401f8"
CURRENT_VERSION = "v1.0.1"
USER_AGENT = "aia-eia-js PDF JSON recovery/1.0 (+https://github.com/PatLittle/aia-eia-js)"
QUESTION_TYPES = {
    "text",
    "comment",
    "radiogroup",
    "dropdown",
    "checkbox",
    "boolean",
}
CHOICE_TYPES = {"radiogroup", "dropdown", "checkbox", "boolean"}
TEXT_TYPES = {"text", "comment"}
EXCLUDE_PDF_TERMS = (
    "peer review",
    "peer-review",
    "peer_review",
    "plain language",
    "executive summary",
    "review report",
    "examen par les pairs",
    "resume analytique",
    "résumé analytique",
    "resume en langage",
    "résumé en langage",
)
FRENCH_HINTS = (
    "-fr.",
    "-fr-",
    "_fr.",
    "_fre.",
    "french",
    "francais",
    "français",
    "levaluation",
    "l-evaluation",
    "resultats-de",
    "resultats_",
    "indicateur-de",
    "outil-de",
    "gestion-des-cotisations",
)
ENGLISH_HINTS = ("-en.", "-en-", "_en.", "english")
MODIFIER_RE = re.compile(r"^\[\s*(?:Modifier|Modificateur)\s*:\s*[+-]?\d+\s*\]$", re.I)
SECTION_RE = re.compile(r"^\s*Section\s+\d+(?:\.\d+)?\s*:", re.I)
NUMBERED_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.+?)\s*$")
TAG_RE = re.compile(r"<[^>]+>")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")


@dataclass
class Question:
    name: str
    qtype: str
    title_en: str
    title_fr: str
    choices: list[dict[str, str]]
    order: int
    panel_path: tuple[str, ...]


@dataclass
class Match:
    line_index: int
    question: Question
    score: float
    title_lines: int
    printed_number: int


class RecoveryError(RuntimeError):
    pass


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def get_json(s: requests.Session, url: str) -> Any:
    response = s.get(url, timeout=90)
    response.raise_for_status()
    return response.json()


def get_bytes(s: requests.Session, url: str) -> bytes:
    response = s.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def package_show(s: requests.Session, package_id: str) -> dict[str, Any]:
    payload = get_json(s, CKAN_API.format(package_id))
    if not payload.get("success"):
        raise RecoveryError(f"CKAN package_show failed for {package_id}")
    return payload["result"]


def clean_display(value: Any, locale: str = "en") -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        if locale == "fr":
            value = value.get("fr") or value.get("default") or value.get("en") or ""
        else:
            value = value.get("default") or value.get("en") or value.get("fr") or ""
    value = str(value)
    value = html.unescape(value)
    value = MARKDOWN_LINK_RE.sub(r"\1", value)
    value = TAG_RE.sub(" ", value)
    return re.sub(r"\s+", " ", value).strip()


def norm(value: Any) -> str:
    text = clean_display(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def version_norm(value: str) -> str:
    value = str(value or "").strip().lower()
    value = value.replace("version", "").strip()
    value = value.lstrip("v")
    if value.startswith("."):
        value = value[1:]
    return value


def walk_elements(elements: Iterable[dict[str, Any]], parents: tuple[str, ...] = ()) -> Iterable[tuple[dict[str, Any], tuple[str, ...]]]:
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        name = str(element.get("name") or "")
        child_parents = parents + ((name,) if name else ())
        if element.get("type") == "panel":
            yield from walk_elements(element.get("elements") or [], child_parents)
        else:
            yield element, parents
            if element.get("elements"):
                yield from walk_elements(element.get("elements") or [], child_parents)


def choice_records(element: dict[str, Any]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for choice in element.get("choices") or []:
        if isinstance(choice, dict):
            raw = choice.get("value")
            if raw is None:
                raw = clean_display(choice.get("text"), "en")
            text = choice.get("text", raw)
            records.append(
                {
                    "value": str(raw),
                    "en": clean_display(text, "en"),
                    "fr": clean_display(text, "fr"),
                }
            )
        else:
            records.append({"value": str(choice), "en": str(choice), "fr": str(choice)})
    return records


def schema_questions(schema: dict[str, Any]) -> list[Question]:
    out: list[Question] = []
    order = 0
    for page in schema.get("pages") or []:
        page_name = str(page.get("name") or "")
        for element, parents in walk_elements(page.get("elements") or [], (page_name,)):
            qtype = str(element.get("type") or "")
            name = str(element.get("name") or "")
            title = element.get("title")
            if qtype not in QUESTION_TYPES or not name or title is None:
                continue
            out.append(
                Question(
                    name=name,
                    qtype=qtype,
                    title_en=clean_display(title, "en"),
                    title_fr=clean_display(title, "fr"),
                    choices=choice_records(element),
                    order=order,
                    panel_path=parents,
                )
            )
            order += 1
    return out


def load_schemas(s: requests.Session, repo_root: Path) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    current = json.loads((repo_root / "src" / "survey-enfr.json").read_text(encoding="utf-8"))
    schemas[version_norm(CURRENT_VERSION)] = {"version": CURRENT_VERSION, "definition": current, "source": "local"}

    manifest_path = repo_root / "src" / "generated" / "surveyVersions.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest:
        version = entry["version"]
        try:
            definition = get_json(s, entry["sourceUrl"])
        except Exception as exc:  # keep current schema usable if a tag is temporarily unavailable
            print(f"WARNING: could not fetch survey schema {version}: {exc}", file=sys.stderr)
            continue
        schemas[version_norm(version)] = {"version": version, "definition": definition, "source": entry["sourceUrl"]}
    return schemas


def pdf_resource_score(resource: dict[str, Any], locale: str) -> int:
    if str(resource.get("format") or "").upper() != "PDF":
        return -10_000
    hay = " ".join([str(resource.get("name") or ""), str(resource.get("url") or "")]).lower()
    if any(term in hay for term in EXCLUDE_PDF_TERMS):
        return -5_000
    score = 10
    if "algorithmic impact" in hay or "aia" in hay or "incidence algorithmique" in hay or "eia" in hay:
        score += 20
    fr = any(hint in hay for hint in FRENCH_HINTS)
    en = any(hint in hay for hint in ENGLISH_HINTS)
    if locale == "en":
        score += 35 if en else 0
        score -= 80 if fr else 0
    else:
        score += 35 if fr else 0
        score -= 80 if en else 0
    return score


def choose_pdf_resource(package: dict[str, Any], locale: str) -> dict[str, Any] | None:
    candidates = sorted(
        package.get("resources") or [],
        key=lambda r: pdf_resource_score(r, locale),
        reverse=True,
    )
    if not candidates or pdf_resource_score(candidates[0], locale) < 0:
        return None
    if locale == "fr" and pdf_resource_score(candidates[0], locale) < 35:
        return None
    return candidates[0]


def choose_json_resource(package: dict[str, Any], resource_id: str | None = None) -> dict[str, Any] | None:
    for r in package.get("resources") or []:
        if resource_id and r.get("id") == resource_id:
            return r
    for r in package.get("resources") or []:
        if str(r.get("format") or "").upper() == "JSON":
            return r
    return None


def extract_pdf(pdf_bytes: bytes) -> tuple[str, list[str]]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [page.get_text("text", sort=True) for page in doc]
    return "\n".join(pages), pages


def detect_version(text: str, schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    patterns = [
        r"(?:AIA|Algorithmic Impact Assessment)?\s*Version\s*[:\-]?\s*v?([0-9]+(?:\.[0-9A-Za-z]+){1,3})",
        r"Version\s*[:\-]?\s*v?([0-9]+(?:\.[0-9A-Za-z]+){1,3})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            key = version_norm(match.group(1))
            if key in schemas:
                return schemas[key]
    # If the PDF omits a version line, title coverage is a reliable fallback.
    text_n = norm(text)
    ranked: list[tuple[int, str]] = []
    for key, schema in schemas.items():
        questions = schema_questions(schema["definition"])
        sample = [q for q in questions if len(norm(q.title_en)) >= 20]
        hits = sum(1 for q in sample if norm(q.title_en) in text_n)
        ranked.append((hits, key))
    ranked.sort(reverse=True)
    if not ranked:
        raise RecoveryError("No AIA survey schemas are available")
    return schemas[ranked[0][1]]


def candidate_title_score(question_title: str, lines: list[str], start: int, max_lines: int = 7) -> tuple[float, int]:
    target = norm(question_title)
    if not target:
        return 0.0, 1
    best_score = 0.0
    best_k = 1
    chunks: list[str] = []
    for k in range(1, min(max_lines, len(lines) - start) + 1):
        chunks.append(lines[start + k - 1])
        candidate = norm(" ".join(chunks))
        if not candidate:
            continue
        ratio = fuzz.ratio(target, candidate)
        partial = fuzz.partial_ratio(target, candidate)
        token = fuzz.token_set_ratio(target, candidate)
        score = max(ratio, 0.92 * partial, 0.96 * token)
        if candidate == target:
            score = 100.0
        elif candidate.startswith(target) or target.startswith(candidate):
            score = max(score, 96.0)
        if score > best_score:
            best_score, best_k = score, k
    return best_score, best_k


def find_question_matches(text: str, questions: list[Question], locale: str) -> list[Match]:
    lines = [line.rstrip() for line in text.replace("\r", "").split("\n")]
    candidates: list[Match] = []
    last_order = -1
    for i, line in enumerate(lines):
        numbered = NUMBERED_RE.match(line)
        if not numbered:
            continue
        title_first = numbered.group(2)
        virtual = lines[:]
        virtual[i] = title_first
        # Prefer survey order, but allow a modest backwards window because some
        # versions move non-scored questions between panels.
        if last_order < 0:
            pool = questions
        else:
            pool = [q for q in questions if q.order >= max(0, last_order - 4)]
        best: tuple[float, int, Question] | None = None
        for q in pool:
            qtitle = q.title_fr if locale == "fr" else q.title_en
            score, k = candidate_title_score(qtitle, virtual, i)
            if best is None or score > best[0]:
                best = (score, k, q)
        if best and best[0] >= 79.0:
            # Avoid mapping the same schema question twice because a numbered
            # list in an answer can occasionally resemble a short title.
            if candidates and best[2].name == candidates[-1].question.name:
                continue
            candidates.append(
                Match(
                    line_index=i,
                    question=best[2],
                    score=best[0],
                    title_lines=best[1],
                    printed_number=int(numbered.group(1)),
                )
            )
            last_order = best[2].order
    return candidates


def is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if MODIFIER_RE.match(stripped):
        return True
    if SECTION_RE.match(stripped):
        return True
    if stripped.lower() in {
        "project details",
        "risk questions and answers",
        "mitigation questions and answers",
        "questions and answers",
        "question and answer",
    }:
        return True
    if re.match(r"^Page\s+\d+(?:\s+of\s+\d+)?$", stripped, re.I):
        return True
    return False


def answer_lines(text: str, matches: list[Match], index: int) -> list[str]:
    lines = [line.rstrip() for line in text.replace("\r", "").split("\n")]
    current = matches[index]
    start = current.line_index + current.title_lines
    end = matches[index + 1].line_index if index + 1 < len(matches) else len(lines)
    out = lines[start:end]
    # Drop section labels / score modifiers but retain blank lines so free-text
    # paragraph structure is not completely flattened.
    out = [line for line in out if not is_noise_line(line)]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def fuzzy_choice_score(answer: str, choice: str) -> float:
    a, c = norm(answer), norm(choice)
    if not a or not c:
        return 0.0
    if c == a:
        return 100.0
    if re.search(r"(?:^|\n|\s)" + re.escape(c) + r"(?:$|\n|\s)", a):
        return 99.0
    return max(fuzz.ratio(a, c), fuzz.partial_ratio(a, c), fuzz.token_set_ratio(a, c))


def parse_value(question: Question, lines: list[str], locale: str) -> Any:
    answer = "\n".join(lines).strip()
    if question.qtype in TEXT_TYPES:
        # Remove a trailing modifier if text extraction placed it on the next line.
        return answer
    if question.qtype == "checkbox":
        selected: list[str] = []
        answer_n = norm(answer)
        for choice in question.choices:
            label = choice[locale] or choice["en"]
            label_n = norm(label)
            if label_n and (label_n in answer_n or fuzzy_choice_score(answer, label) >= 93):
                selected.append(choice["value"])
        return selected
    if question.choices:
        scored = []
        for choice in question.choices:
            label = choice[locale] or choice["en"]
            scored.append((fuzzy_choice_score(answer, label), choice["value"], label))
        scored.sort(reverse=True, key=lambda row: row[0])
        if scored and scored[0][0] >= 70:
            return scored[0][1]
    if question.qtype == "boolean":
        a = norm(answer)
        if a.startswith("yes") or a.startswith("oui"):
            return True
        if a.startswith("no") or a.startswith("non"):
            return False
    return None


def reconstruct(text: str, schema: dict[str, Any], locale: str) -> tuple[dict[str, Any], dict[str, Any]]:
    questions = schema_questions(schema)
    matches = find_question_matches(text, questions, locale)
    data: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {
        "matched_questions": len(matches),
        "schema_questions": len(questions),
        "matches": [],
        "unresolved": [],
    }
    for idx, match in enumerate(matches):
        lines = answer_lines(text, matches, idx)
        value = parse_value(match.question, lines, locale)
        diagnostics["matches"].append(
            {
                "number": match.printed_number,
                "name": match.question.name,
                "type": match.question.qtype,
                "title": match.question.title_fr if locale == "fr" else match.question.title_en,
                "match_score": round(match.score, 2),
                "answer": "\n".join(lines).strip(),
                "value": value,
            }
        )
        if value is None or (match.question.qtype == "checkbox" and not value and "\n".join(lines).strip()):
            diagnostics["unresolved"].append(match.question.name)
            continue
        data[match.question.name] = value
    return data, diagnostics


def clean_text_value(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    # Output PDFs can wrap free text differently; comparison therefore ignores
    # whitespace while still requiring identical words/punctuation.
    return norm(value)


def compare_control(expected: dict[str, Any], recovered: dict[str, Any], questions: list[Question]) -> dict[str, Any]:
    expected_data = expected.get("data") or {}
    recovered_data = recovered.get("data") or {}
    by_name = {q.name: q for q in questions}
    expected_keys = set(expected_data)
    recovered_keys = set(recovered_data)
    common = expected_keys & recovered_keys
    exact = 0
    text_equal = 0
    choice_total = 0
    choice_exact = 0
    mismatches: list[dict[str, Any]] = []
    for key in sorted(common):
        e = expected_data[key]
        r = recovered_data[key]
        q = by_name.get(key)
        same = e == r
        if same:
            exact += 1
        if q and q.qtype in TEXT_TYPES:
            if clean_text_value(e) == clean_text_value(r):
                text_equal += 1
                same = True
        if q and q.qtype in CHOICE_TYPES:
            choice_total += 1
            if e == r:
                choice_exact += 1
        if not same:
            mismatches.append({"name": key, "expected": e, "recovered": r, "type": q.qtype if q else None})
    key_recall = len(common) / len(expected_keys) if expected_keys else 1.0
    return {
        "expected_version": expected.get("version"),
        "recovered_version": recovered.get("version"),
        "expected_currentPage": expected.get("currentPage"),
        "recovered_currentPage": recovered.get("currentPage"),
        "expected_key_count": len(expected_keys),
        "recovered_key_count": len(recovered_keys),
        "common_key_count": len(common),
        "key_recall": round(key_recall, 4),
        "exact_value_count": exact,
        "choice_fields_compared": choice_total,
        "choice_exact_count": choice_exact,
        "choice_accuracy": round(choice_exact / choice_total, 4) if choice_total else 0.0,
        "missing_keys": sorted(expected_keys - recovered_keys),
        "extra_keys": sorted(recovered_keys - expected_keys),
        "mismatches": mismatches,
    }


def infer_current_page(schema: dict[str, Any]) -> int:
    # The current app historically considers page 12 the final questionnaire
    # page.  Use the schema's final page index for version portability.
    pages = schema.get("pages") or []
    return max(0, len(pages) - 1)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recover_package(
    s: requests.Session,
    package_id: str,
    schemas: dict[str, dict[str, Any]],
    output_dir: Path,
    debug_dir: Path | None,
    keep_pdfs: bool,
) -> dict[str, Any]:
    package = package_show(s, package_id)
    en_resource = choose_pdf_resource(package, "en")
    if not en_resource:
        raise RecoveryError(f"No English AIA PDF found in package {package_id}")
    fr_resource = choose_pdf_resource(package, "fr")

    en_pdf = get_bytes(s, en_resource["url"])
    en_text, en_pages = extract_pdf(en_pdf)
    selected_schema = detect_version(en_text, schemas)
    version = selected_schema["version"]
    schema = selected_schema["definition"]
    en_data, en_diag = reconstruct(en_text, schema, "en")

    translations: dict[str, Any] = {}
    fr_diag: dict[str, Any] | None = None
    fr_text = ""
    fr_pdf: bytes | None = None
    if fr_resource and fr_resource.get("url") != en_resource.get("url"):
        fr_pdf = get_bytes(s, fr_resource["url"])
        fr_text, _ = extract_pdf(fr_pdf)
        fr_data, fr_diag = reconstruct(fr_text, schema, "fr")
        qtypes = {q.name: q.qtype for q in schema_questions(schema)}
        for key, value in fr_data.items():
            if qtypes.get(key) in TEXT_TYPES and key in en_data and isinstance(value, str):
                translations[key] = value

    survey_file = {
        "version": version,
        "currentPage": infer_current_page(schema),
        "data": en_data,
        "translationsOnResult": translations,
    }
    output_path = output_dir / package_id / "aia-results.json"
    write_json(output_path, survey_file)

    diagnostic = {
        "package_id": package_id,
        "package_title": package.get("title"),
        "survey_version": version,
        "schema_source": selected_schema["source"],
        "english_resource": {"id": en_resource.get("id"), "name": en_resource.get("name"), "url": en_resource.get("url")},
        "french_resource": ({"id": fr_resource.get("id"), "name": fr_resource.get("name"), "url": fr_resource.get("url")} if fr_resource else None),
        "english": en_diag,
        "french": fr_diag,
        "output": str(output_path),
    }
    if debug_dir:
        pkg_debug = debug_dir / package_id
        pkg_debug.mkdir(parents=True, exist_ok=True)
        (pkg_debug / "english.txt").write_text(en_text, encoding="utf-8")
        if fr_text:
            (pkg_debug / "french.txt").write_text(fr_text, encoding="utf-8")
        write_json(pkg_debug / "diagnostics.json", diagnostic)
        if keep_pdfs:
            pdf_dir = debug_dir / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            (pdf_dir / f"{package_id}-en.pdf").write_bytes(en_pdf)
            if fr_pdf:
                (pdf_dir / f"{package_id}-fr.pdf").write_bytes(fr_pdf)
    return diagnostic


def run_control(
    s: requests.Session,
    schemas: dict[str, dict[str, Any]],
    debug_dir: Path,
    keep_pdfs: bool,
) -> dict[str, Any]:
    package = package_show(s, CONTROL_PACKAGE_ID)
    en_resource = choose_pdf_resource(package, "en")
    fr_resource = choose_pdf_resource(package, "fr")
    json_resource = choose_json_resource(package, CONTROL_JSON_RESOURCE_ID)
    if not en_resource or not json_resource:
        raise RecoveryError("Control package is missing its expected PDF or JSON")

    en_pdf = get_bytes(s, en_resource["url"])
    en_text, _ = extract_pdf(en_pdf)
    selected_schema = detect_version(en_text, schemas)
    schema = selected_schema["definition"]
    en_data, en_diag = reconstruct(en_text, schema, "en")

    translations: dict[str, Any] = {}
    fr_text = ""
    fr_pdf: bytes | None = None
    if fr_resource and fr_resource.get("url") != en_resource.get("url"):
        fr_pdf = get_bytes(s, fr_resource["url"])
        fr_text, _ = extract_pdf(fr_pdf)
        fr_data, _ = reconstruct(fr_text, schema, "fr")
        qtypes = {q.name: q.qtype for q in schema_questions(schema)}
        for key, value in fr_data.items():
            if qtypes.get(key) in TEXT_TYPES and key in en_data and isinstance(value, str):
                translations[key] = value

    expected = get_json(s, json_resource["url"])
    recovered = {
        "version": selected_schema["version"],
        "currentPage": infer_current_page(schema),
        "data": en_data,
        "translationsOnResult": translations,
    }
    report = compare_control(expected, recovered, schema_questions(schema))
    report["package_id"] = CONTROL_PACKAGE_ID
    report["english_resource_url"] = en_resource["url"]
    report["published_json_url"] = json_resource["url"]
    report["english_diagnostics"] = en_diag

    control_dir = debug_dir / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "english.txt").write_text(en_text, encoding="utf-8")
    if fr_text:
        (control_dir / "french.txt").write_text(fr_text, encoding="utf-8")
    write_json(control_dir / "expected.json", expected)
    write_json(control_dir / "recovered.json", recovered)
    write_json(control_dir / "comparison.json", report)
    if keep_pdfs:
        pdf_dir = debug_dir / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        (pdf_dir / f"{CONTROL_PACKAGE_ID}-en.pdf").write_bytes(en_pdf)
        if fr_pdf:
            (pdf_dir / f"{CONTROL_PACKAGE_ID}-fr.pdf").write_bytes(fr_pdf)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default="scripts/aia_pdf_recovery_targets.json")
    parser.add_argument("--output-dir", default="recovered_aia_json")
    parser.add_argument("--debug-dir", default="recovery_debug")
    parser.add_argument("--skip-control", action="store_true")
    parser.add_argument("--keep-pdfs", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    targets_path = repo_root / args.targets
    output_dir = repo_root / args.output_dir
    debug_dir = repo_root / args.debug_dir if args.debug_dir else None
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    s = session()
    schemas = load_schemas(s, repo_root)
    print("Loaded survey versions:", ", ".join(sorted(v["version"] for v in schemas.values())))

    control_report = None
    if not args.skip_control:
        if debug_dir is None:
            raise RecoveryError("Control validation requires --debug-dir")
        control_report = run_control(s, schemas, debug_dir, args.keep_pdfs)
        print(
            "CONTROL:",
            f"key_recall={control_report['key_recall']:.4f}",
            f"choice_accuracy={control_report['choice_accuracy']:.4f}",
            f"keys={control_report['common_key_count']}/{control_report['expected_key_count']}",
        )

    manifest: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for target in targets:
        package_id = target["package_id"]
        print(f"Recovering {package_id} - {target.get('title', '')}")
        try:
            diagnostic = recover_package(s, package_id, schemas, output_dir, debug_dir, args.keep_pdfs)
            manifest.append(
                {
                    "package_id": package_id,
                    "package_title": diagnostic["package_title"],
                    "survey_version": diagnostic["survey_version"],
                    "english_resource": diagnostic["english_resource"],
                    "french_resource": diagnostic["french_resource"],
                    "output": diagnostic["output"],
                    "matched_english_questions": diagnostic["english"]["matched_questions"],
                    "unresolved_english": diagnostic["english"]["unresolved"],
                }
            )
        except Exception as exc:
            print(f"ERROR {package_id}: {exc}", file=sys.stderr)
            failures.append({"package_id": package_id, "error": str(exc)})

    write_json(output_dir / "manifest.json", {"generated": manifest, "failures": failures, "control": control_report})
    print(f"Recovered {len(manifest)}/{len(targets)} target packages")
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
