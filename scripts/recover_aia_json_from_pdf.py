#!/usr/bin/env python3
"""Reconstruct AIA SurveyFile JSON from published AIA result PDFs.

The AIA application saves a SurveyFile with four fields::

    version, currentPage, data, translationsOnResult

Published result PDFs contain the displayed question titles and answers but not
the raw SurveyJS choice values.  This script uses the matching version of
``survey-enfr.json`` to map those displayed answers back to the raw values.

A known-good CBSA AIA (CRES/ReportIn) that publishes both PDF and JSON is used
as a regression control.  GitHub Actions should not commit recovered files if
the control reconstruction falls below the configured quality thresholds.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pymupdf
import requests
from rapidfuzz import fuzz

CKAN_API = "https://open.canada.ca/data/api/3/action/package_show?id={}"
CURRENT_VERSION = "v1.0.1"
FINAL_PAGE = 12
CONTROL_PACKAGE_ID = "eaeb269c-6ac5-4429-a5aa-1fcc07c77933"
CONTROL_EN_JSON_ID = "dd83f660-f2c3-4de1-a953-2174e07401f8"
CONTROL_FR_JSON_ID = "f6e0e812-2a79-4033-b38b-22b46177cc62"
USER_AGENT = "aia-eia-js PDF JSON recovery/2.0 (+https://github.com/PatLittle/aia-eia-js)"

QUESTION_TYPES = {"text", "comment", "radiogroup", "dropdown", "checkbox", "boolean"}
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
    "résumé analytique",
    "resume analytique",
    "résumé en langage",
    "resume en langage",
)
FRENCH_HINTS = (
    "-fr.", "-fr-", "_fr.", "_fre.", "french", "francais", "français",
    "levaluation", "l-evaluation", "resultats-de", "resultats_",
    "indicateur-de", "outil-de", "gestion-des-cotisations",
)
ENGLISH_HINTS = ("-en.", "-en-", "_en.", "english")

NUMBERED_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.+?)\s*$")
SECTION_RE = re.compile(r"^\s*Section\s+\d+(?:\.\d+)?\s*:", re.I)
POINTS_RE = re.compile(
    r"\s*\[\s*(?:Points?|Modifier|Modificateur)\s*:\s*[+-]?\d+\s*\]\s*$",
    re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")


@dataclass(frozen=True)
class Question:
    name: str
    qtype: str
    title_en: str
    title_fr: str
    choices: tuple[tuple[str, str, str], ...]  # raw value, English, French
    order: int
    score_type: str  # NS, RS, MS


@dataclass
class Match:
    line_index: int
    question: Question
    score: float
    title_lines: int
    printed_number: int
    context: str


class RecoveryError(RuntimeError):
    pass


def http_session() -> requests.Session:
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
    text = html.unescape(str(value))
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    text = TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_display(value))
    text = (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
        .replace(" ", " ")
    )
    return re.sub(r"\s+", " ", text).strip().lower()


def version_norm(value: str) -> str:
    value = str(value or "").strip().lower().replace("version", "").strip().lstrip("v")
    return value[1:] if value.startswith(".") else value


def score_type_from_names(name: str, parents: Iterable[str]) -> str:
    for candidate in (name, *reversed(tuple(parents))):
        if candidate.endswith("-RS"):
            return "RS"
        if candidate.endswith("-MS"):
            return "MS"
        if candidate.endswith("-NS"):
            return "NS"
    return "NS"


def walk_elements(
    elements: Iterable[dict[str, Any]],
    parent_names: tuple[str, ...] = (),
) -> Iterable[tuple[dict[str, Any], tuple[str, ...]]]:
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        name = str(element.get("name") or "")
        if element.get("type") == "panel":
            yield from walk_elements(
                element.get("elements") or [],
                parent_names + ((name,) if name else ()),
            )
        else:
            yield element, parent_names
            if element.get("elements"):
                yield from walk_elements(
                    element.get("elements") or [],
                    parent_names + ((name,) if name else ()),
                )


def choice_records(element: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    records: list[tuple[str, str, str]] = []
    for choice in element.get("choices") or []:
        if isinstance(choice, dict):
            raw = choice.get("value")
            if raw is None:
                raw = clean_display(choice.get("text"), "en")
            label = choice.get("text", raw)
            records.append((str(raw), clean_display(label, "en"), clean_display(label, "fr")))
        else:
            records.append((str(choice), str(choice), str(choice)))
    return tuple(records)


def schema_questions(schema: dict[str, Any]) -> list[Question]:
    result: list[Question] = []
    order = 0
    for page in schema.get("pages") or []:
        page_name = str(page.get("name") or "")
        for element, parents in walk_elements(page.get("elements") or [], (page_name,)):
            qtype = str(element.get("type") or "")
            name = str(element.get("name") or "")
            title = element.get("title")
            if qtype not in QUESTION_TYPES or not name or title is None:
                continue
            result.append(
                Question(
                    name=name,
                    qtype=qtype,
                    title_en=clean_display(title, "en"),
                    title_fr=clean_display(title, "fr"),
                    choices=choice_records(element),
                    order=order,
                    score_type=score_type_from_names(name, parents),
                )
            )
            order += 1
    return result


def schema_headers(schema: dict[str, Any], locale: str) -> set[str]:
    headers: set[str] = set()

    def visit(elements: Iterable[dict[str, Any]]) -> None:
        for element in elements or []:
            if not isinstance(element, dict):
                continue
            if element.get("type") == "panel" and element.get("title"):
                value = norm(clean_display(element["title"], locale))
                if value:
                    headers.add(value)
            if element.get("elements"):
                visit(element.get("elements") or [])

    for page in schema.get("pages") or []:
        if page.get("title"):
            value = norm(clean_display(page["title"], locale))
            if value:
                headers.add(value)
        visit(page.get("elements") or [])

    headers.update(
        norm(x)
        for x in (
            "Algorithmic Impact Assessment Results",
            "Project Details",
            "Questions and Answers",
            "Impact Questions and Answers",
            "Mitigation Questions and Answers",
        )
    )
    return headers


def load_schemas(s: requests.Session, repo_root: Path) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    current = json.loads((repo_root / "src" / "survey-enfr.json").read_text(encoding="utf-8"))
    schemas[version_norm(CURRENT_VERSION)] = {
        "version": CURRENT_VERSION,
        "definition": current,
        "source": "src/survey-enfr.json",
    }
    manifest = json.loads(
        (repo_root / "src" / "generated" / "surveyVersions.json").read_text(encoding="utf-8")
    )
    for entry in manifest:
        version = entry["version"]
        try:
            definition = get_json(s, entry["sourceUrl"])
        except Exception as exc:
            print(f"WARNING: could not fetch schema {version}: {exc}", file=sys.stderr)
            continue
        schemas[version_norm(version)] = {
            "version": version,
            "definition": definition,
            "source": entry["sourceUrl"],
        }
    return schemas


def pdf_resource_score(resource: dict[str, Any], locale: str) -> int:
    if str(resource.get("format") or "").upper() != "PDF":
        return -10_000
    hay = " ".join((str(resource.get("name") or ""), str(resource.get("url") or ""))).lower()
    if any(term in hay for term in EXCLUDE_PDF_TERMS):
        return -5_000
    score = 10
    if any(term in hay for term in ("algorithmic impact", "aia", "incidence algorithmique", "eia")):
        score += 20
    looks_fr = any(hint in hay for hint in FRENCH_HINTS)
    looks_en = any(hint in hay for hint in ENGLISH_HINTS)
    if locale == "en":
        score += 35 if looks_en else 0
        score -= 80 if looks_fr else 0
    else:
        score += 35 if looks_fr else 0
        score -= 80 if looks_en else 0
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


def choose_resource_by_id(package: dict[str, Any], resource_id: str) -> dict[str, Any] | None:
    return next((r for r in package.get("resources") or [] if r.get("id") == resource_id), None)


def extract_pdf(pdf_bytes: bytes) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(page.get_text("text", sort=True) for page in doc)


def detect_version(text: str, schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for match in re.finditer(
        r"(?:AIA|Algorithmic Impact Assessment)?\s*Version\s*[:\-]?\s*v?([0-9]+(?:\.[0-9A-Za-z]+){1,3})",
        text,
        flags=re.I,
    ):
        key = version_norm(match.group(1))
        if key in schemas:
            return schemas[key]

    # Fallback for unusual PDFs that omit a version line.
    text_n = norm(text)
    ranked: list[tuple[int, str]] = []
    for key, schema in schemas.items():
        questions = schema_questions(schema["definition"])
        hits = sum(
            1
            for q in questions
            if len(norm(q.title_en)) >= 24 and norm(q.title_en) in text_n
        )
        ranked.append((hits, key))
    if not ranked:
        raise RecoveryError("No survey schemas available")
    ranked.sort(reverse=True)
    return schemas[ranked[0][1]]


def infer_phase(text: str) -> str | None:
    patterns = (
        r"Project\s+Phase\s*\n\s*(Design|Implementation)\b",
        r"Étape\s+du\s+projet\s*\n\s*(Conception|Mise\s+en\s+œuvre|Mise\s+en\s+oeuvre)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        value = norm(match.group(1))
        if value in {"design", "conception"}:
            return "Design"
        if value.startswith("implementation") or value.startswith("mise en"):
            return "Implementation"
    return None


def phase_compatible(question: Question, phase: str | None) -> bool:
    if not phase:
        return True
    name = question.name.lower()
    if phase == "Design" and "implementation" in name:
        return False
    if phase == "Implementation" and "design" in name:
        return False
    return True


def context_from_line(line: str) -> str | None | bool:
    value = norm(line)
    if not value:
        return False
    if "mitigation questions and answers" in value:
        return "MS"
    if "impact questions and answers" in value:
        return "RS"
    if value == "project details" or "project details" in value and value.startswith("section"):
        return "NS"
    # Requirements/result sections can contain numbered prose. Disable question matching there.
    if SECTION_RE.match(line) and not "questions and answers" in value:
        return None
    return False


def candidate_title_score(
    question_title: str,
    lines: list[str],
    start: int,
    first_text: str,
    max_lines: int = 8,
) -> tuple[float, int]:
    target = norm(question_title)
    if not target:
        return 0.0, 1
    chunks = [first_text]
    best_score = 0.0
    best_k = 1
    for k in range(1, max_lines + 1):
        if k > 1:
            idx = start + k - 1
            if idx >= len(lines):
                break
            line = lines[idx].strip()
            # Question titles wrap, but they do not cross a blank line or another numbered item.
            if not line or NUMBERED_RE.match(line) or SECTION_RE.match(line):
                break
            chunks.append(line)
        candidate = norm(" ".join(chunks))
        if not candidate:
            continue
        if candidate == target:
            score = 100.0
        else:
            ratio = fuzz.ratio(target, candidate)
            token = fuzz.token_set_ratio(target, candidate)
            score = max(ratio, token * 0.97)
            if candidate.startswith(target) or target.startswith(candidate):
                score = max(score, 97.0)
        if score > best_score:
            best_score, best_k = score, k
    return best_score, best_k


def find_question_matches(
    text: str,
    questions: list[Question],
    locale: str,
    phase: str | None,
) -> list[Match]:
    lines = [line.rstrip() for line in text.replace("\r", "").split("\n")]
    context: str | None = None
    last_order = {"NS": -1, "RS": -1, "MS": -1}
    used_names: set[str] = set()
    matches: list[Match] = []

    for i, line in enumerate(lines):
        change = context_from_line(line)
        if change is not False:
            context = change
            continue
        if context not in {"NS", "RS", "MS"}:
            continue
        numbered = NUMBERED_RE.match(line)
        if not numbered:
            continue

        first_text = numbered.group(2)
        pool = [
            q
            for q in questions
            if q.score_type == context
            and q.order > last_order[context]
            and q.name not in used_names
            and phase_compatible(q, phase)
        ]
        best: tuple[float, int, Question] | None = None
        for question in pool:
            title = question.title_fr if locale == "fr" else question.title_en
            score, title_lines = candidate_title_score(title, lines, i, first_text)
            if best is None or score > best[0] or (
                score == best[0] and question.order < best[2].order
            ):
                best = (score, title_lines, question)

        if not best or best[0] < 84.0:
            continue

        score, title_lines, question = best
        matches.append(
            Match(
                line_index=i,
                question=question,
                score=score,
                title_lines=title_lines,
                printed_number=int(numbered.group(1)),
                context=context,
            )
        )
        used_names.add(question.name)
        last_order[context] = question.order

    return matches


def strip_points(line: str) -> str:
    return POINTS_RE.sub("", line).rstrip()


def is_structural_boundary(line: str, current_context: str) -> bool:
    change = context_from_line(line)
    if change is not False and change != current_context:
        return True
    value = norm(line)
    return bool(value.startswith("section 1:") or value.startswith("section 2:"))


def answer_lines(
    text: str,
    matches: list[Match],
    index: int,
    headers: set[str],
) -> list[str]:
    lines = [line.rstrip() for line in text.replace("\r", "").split("\n")]
    match = matches[index]
    start = match.line_index + match.title_lines
    end = matches[index + 1].line_index if index + 1 < len(matches) else len(lines)

    collected: list[str] = []
    for line in lines[start:end]:
        if is_structural_boundary(line, match.context):
            break
        clean = strip_points(line)
        clean_n = norm(clean)
        if clean_n in headers:
            continue
        if clean_n == "algorithmic impact assessment results" or re.fullmatch(r"\d+", clean_n):
            continue
        collected.append(clean)

    while collected and not collected[0].strip():
        collected.pop(0)
    while collected and not collected[-1].strip():
        collected.pop()

    # Remove repeated blank lines while preserving paragraph boundaries.
    result: list[str] = []
    previous_blank = False
    for line in collected:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        result.append(line)
        previous_blank = blank
    return result


def choice_label(choice: tuple[str, str, str], locale: str) -> str:
    return choice[2] if locale == "fr" else choice[1]


def single_choice_value(question: Question, lines: list[str], locale: str) -> str | bool | None:
    answer_lines_n = [norm(line) for line in lines if norm(line)]
    answer_n = norm(" ".join(lines))

    exact: list[tuple[str, str]] = []
    for choice in question.choices:
        label = choice_label(choice, locale) or choice[1]
        label_n = norm(label)
        if label_n and label_n in answer_lines_n:
            exact.append((choice[0], label_n))
    if len(exact) == 1:
        return exact[0][0]
    if exact:
        # Prefer the longest exact label if labels overlap.
        return max(exact, key=lambda row: len(row[1]))[0]

    if question.choices:
        ranked: list[tuple[float, str]] = []
        for choice in question.choices:
            label = choice_label(choice, locale) or choice[1]
            label_n = norm(label)
            if not label_n:
                continue
            if answer_n == label_n:
                return choice[0]
            ratio = fuzz.ratio(answer_n, label_n)
            token = fuzz.token_set_ratio(answer_n, label_n) * 0.94
            partial = fuzz.partial_ratio(answer_n, label_n) * 0.82
            ranked.append((max(ratio, token, partial), choice[0]))
        if ranked:
            ranked.sort(reverse=True)
            if ranked[0][0] >= 72.0:
                return ranked[0][1]

    if question.qtype == "boolean":
        if answer_n.startswith(("yes", "oui")):
            return True
        if answer_n.startswith(("no", "non")):
            return False
    return None


def checkbox_values(question: Question, lines: list[str], locale: str) -> list[str]:
    answer_n = norm(" ".join(lines))
    selected: list[tuple[int, str]] = []
    unresolved_choices: list[tuple[float, int, str]] = []

    for choice in question.choices:
        raw = choice[0]
        label = choice_label(choice, locale) or choice[1]
        label_n = norm(label)
        if not label_n:
            continue
        pos = answer_n.find(label_n)
        if pos >= 0:
            selected.append((pos, raw))
            continue

        # Fallback for minor extraction differences: match against a moving window of lines.
        best_score = 0.0
        best_pos = 10**9
        for line_no in range(len(lines)):
            for width in (1, 2, 3):
                chunk = norm(" ".join(lines[line_no : line_no + width]))
                if not chunk:
                    continue
                score = max(fuzz.ratio(label_n, chunk), fuzz.token_set_ratio(label_n, chunk) * 0.96)
                if score > best_score:
                    best_score = score
                    best_pos = line_no * 1000
        if best_score >= 91.0:
            unresolved_choices.append((best_score, best_pos, raw))

    selected.extend((pos, raw) for _, pos, raw in unresolved_choices)
    # De-duplicate while retaining display order.
    out: list[str] = []
    seen: set[str] = set()
    for _, raw in sorted(selected, key=lambda row: row[0]):
        if raw not in seen:
            out.append(raw)
            seen.add(raw)
    return out


def parse_value(question: Question, lines: list[str], locale: str) -> Any:
    if question.qtype in TEXT_TYPES:
        return "\n".join(lines).strip()
    if question.qtype == "checkbox":
        return checkbox_values(question, lines, locale)
    return single_choice_value(question, lines, locale)


def reconstruct(
    text: str,
    schema: dict[str, Any],
    locale: str,
    phase: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    questions = schema_questions(schema)
    headers = schema_headers(schema, locale)
    matches = find_question_matches(text, questions, locale, phase)
    data: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {
        "phase": phase,
        "matched_questions": len(matches),
        "schema_questions": len(questions),
        "unresolved": [],
        "matches": [],
    }

    for i, match in enumerate(matches):
        lines = answer_lines(text, matches, i, headers)
        value = parse_value(match.question, lines, locale)
        answer = "\n".join(lines).strip()
        unresolved = value is None or (
            match.question.qtype == "checkbox" and bool(answer) and not value
        )
        if unresolved:
            diagnostics["unresolved"].append(match.question.name)
        else:
            data[match.question.name] = value
        diagnostics["matches"].append(
            {
                "number": match.printed_number,
                "name": match.question.name,
                "type": match.question.qtype,
                "score_type": match.question.score_type,
                "title": match.question.title_fr if locale == "fr" else match.question.title_en,
                "match_score": round(match.score, 2),
                "answer": answer,
                "value": value,
            }
        )
    return data, diagnostics


def survey_file(version: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": version,
        "currentPage": FINAL_PAGE,
        "data": data,
        "translationsOnResult": {},
    }


def compare_control(
    expected: dict[str, Any],
    recovered: dict[str, Any],
    questions: list[Question],
) -> dict[str, Any]:
    expected_data = expected.get("data") or {}
    recovered_data = recovered.get("data") or {}
    by_name = {q.name: q for q in questions}
    expected_keys = set(expected_data)
    recovered_keys = set(recovered_data)
    common = expected_keys & recovered_keys

    choice_total = 0
    choice_exact = 0
    text_total = 0
    text_similarity_sum = 0.0
    mismatches: list[dict[str, Any]] = []

    for key in sorted(common):
        question = by_name.get(key)
        expected_value = expected_data[key]
        recovered_value = recovered_data[key]
        if question and question.qtype in CHOICE_TYPES:
            choice_total += 1
            if expected_value == recovered_value:
                choice_exact += 1
            else:
                mismatches.append(
                    {"name": key, "type": question.qtype, "expected": expected_value, "recovered": recovered_value}
                )
        elif question and question.qtype in TEXT_TYPES:
            text_total += 1
            a, b = norm(expected_value), norm(recovered_value)
            similarity = 1.0 if a == b else fuzz.ratio(a, b) / 100.0
            text_similarity_sum += similarity
            if similarity < 0.90:
                mismatches.append(
                    {
                        "name": key,
                        "type": question.qtype,
                        "text_similarity": round(similarity, 4),
                        "expected": expected_value,
                        "recovered": recovered_value,
                    }
                )

    return {
        "expected_version": expected.get("version"),
        "recovered_version": recovered.get("version"),
        "expected_currentPage": expected.get("currentPage"),
        "recovered_currentPage": recovered.get("currentPage"),
        "expected_key_count": len(expected_keys),
        "recovered_key_count": len(recovered_keys),
        "common_key_count": len(common),
        "key_recall": round(len(common) / len(expected_keys), 4) if expected_keys else 1.0,
        "key_precision": round(len(common) / len(recovered_keys), 4) if recovered_keys else 0.0,
        "choice_fields_compared": choice_total,
        "choice_exact_count": choice_exact,
        "choice_accuracy": round(choice_exact / choice_total, 4) if choice_total else 1.0,
        "text_fields_compared": text_total,
        "mean_text_similarity": round(text_similarity_sum / text_total, 4) if text_total else 1.0,
        "missing_keys": sorted(expected_keys - recovered_keys),
        "extra_keys": sorted(recovered_keys - expected_keys),
        "mismatches": mismatches,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recover_locale(
    s: requests.Session,
    resource: dict[str, Any],
    schema: dict[str, Any],
    version: str,
    locale: str,
    phase: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str, bytes]:
    pdf = get_bytes(s, resource["url"])
    text = extract_pdf(pdf)
    data, diagnostics = reconstruct(text, schema, locale, phase)
    return survey_file(version, data), diagnostics, text, pdf


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
    fr_resource = choose_pdf_resource(package, "fr")
    if not en_resource:
        raise RecoveryError(f"No English AIA PDF found for {package_id}")

    en_pdf = get_bytes(s, en_resource["url"])
    en_text = extract_pdf(en_pdf)
    selected = detect_version(en_text, schemas)
    version = selected["version"]
    schema = selected["definition"]
    phase = infer_phase(en_text)
    en_data, en_diag = reconstruct(en_text, schema, "en", phase)
    en_file = survey_file(version, en_data)

    package_output = output_dir / package_id
    write_json(package_output / "aia-results-en.json", en_file)

    fr_file: dict[str, Any] | None = None
    fr_diag: dict[str, Any] | None = None
    fr_text = ""
    fr_pdf: bytes | None = None
    if fr_resource and fr_resource.get("url") != en_resource.get("url"):
        fr_pdf = get_bytes(s, fr_resource["url"])
        fr_text = extract_pdf(fr_pdf)
        fr_data, fr_diag = reconstruct(fr_text, schema, "fr", phase)
        fr_file = survey_file(version, fr_data)
        write_json(package_output / "aia-results-fr.json", fr_file)

    result = {
        "package_id": package_id,
        "package_title": package.get("title"),
        "survey_version": version,
        "phase": phase,
        "schema_source": selected["source"],
        "english_resource": {"id": en_resource.get("id"), "name": en_resource.get("name"), "url": en_resource.get("url")},
        "french_resource": (
            {"id": fr_resource.get("id"), "name": fr_resource.get("name"), "url": fr_resource.get("url")}
            if fr_resource else None
        ),
        "english": en_diag,
        "french": fr_diag,
        "outputs": {
            "en": str(package_output / "aia-results-en.json"),
            "fr": str(package_output / "aia-results-fr.json") if fr_file else None,
        },
    }

    if debug_dir:
        pkg_debug = debug_dir / package_id
        pkg_debug.mkdir(parents=True, exist_ok=True)
        (pkg_debug / "english.txt").write_text(en_text, encoding="utf-8")
        if fr_text:
            (pkg_debug / "french.txt").write_text(fr_text, encoding="utf-8")
        write_json(pkg_debug / "diagnostics.json", result)
        if keep_pdfs:
            pdf_dir = debug_dir / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            (pdf_dir / f"{package_id}-en.pdf").write_bytes(en_pdf)
            if fr_pdf:
                (pdf_dir / f"{package_id}-fr.pdf").write_bytes(fr_pdf)
    return result


def run_control(
    s: requests.Session,
    schemas: dict[str, dict[str, Any]],
    debug_dir: Path,
    keep_pdfs: bool,
) -> dict[str, Any]:
    package = package_show(s, CONTROL_PACKAGE_ID)
    en_pdf_resource = choose_pdf_resource(package, "en")
    fr_pdf_resource = choose_pdf_resource(package, "fr")
    en_json_resource = choose_resource_by_id(package, CONTROL_EN_JSON_ID)
    fr_json_resource = choose_resource_by_id(package, CONTROL_FR_JSON_ID)
    if not en_pdf_resource or not en_json_resource:
        raise RecoveryError("Control package is missing the expected English PDF/JSON")

    en_pdf = get_bytes(s, en_pdf_resource["url"])
    en_text = extract_pdf(en_pdf)
    selected = detect_version(en_text, schemas)
    version = selected["version"]
    schema = selected["definition"]
    phase = infer_phase(en_text)
    questions = schema_questions(schema)

    en_data, en_diag = reconstruct(en_text, schema, "en", phase)
    en_recovered = survey_file(version, en_data)
    en_expected = get_json(s, en_json_resource["url"])
    en_comparison = compare_control(en_expected, en_recovered, questions)
    en_comparison["diagnostics"] = en_diag

    fr_comparison = None
    fr_text = ""
    fr_pdf: bytes | None = None
    fr_expected = None
    fr_recovered = None
    if fr_pdf_resource and fr_json_resource:
        fr_pdf = get_bytes(s, fr_pdf_resource["url"])
        fr_text = extract_pdf(fr_pdf)
        fr_data, fr_diag = reconstruct(fr_text, schema, "fr", phase)
        fr_recovered = survey_file(version, fr_data)
        fr_expected = get_json(s, fr_json_resource["url"])
        fr_comparison = compare_control(fr_expected, fr_recovered, questions)
        fr_comparison["diagnostics"] = fr_diag

    report = {
        "package_id": CONTROL_PACKAGE_ID,
        "version": version,
        "phase": phase,
        "english": en_comparison,
        "french": fr_comparison,
    }

    control_dir = debug_dir / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "english.txt").write_text(en_text, encoding="utf-8")
    write_json(control_dir / "expected-en.json", en_expected)
    write_json(control_dir / "recovered-en.json", en_recovered)
    if fr_text and fr_expected is not None and fr_recovered is not None:
        (control_dir / "french.txt").write_text(fr_text, encoding="utf-8")
        write_json(control_dir / "expected-fr.json", fr_expected)
        write_json(control_dir / "recovered-fr.json", fr_recovered)
    write_json(control_dir / "comparison.json", report)

    if keep_pdfs:
        pdf_dir = debug_dir / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        (pdf_dir / f"{CONTROL_PACKAGE_ID}-en.pdf").write_bytes(en_pdf)
        if fr_pdf:
            (pdf_dir / f"{CONTROL_PACKAGE_ID}-fr.pdf").write_bytes(fr_pdf)
    return report


def validate_control(report: dict[str, Any], min_key_recall: float, min_choice_accuracy: float) -> list[str]:
    failures: list[str] = []
    for locale in ("english", "french"):
        comparison = report.get(locale)
        if not comparison:
            continue
        if comparison["recovered_version"] != comparison["expected_version"]:
            failures.append(f"{locale}: survey version mismatch")
        if comparison["recovered_currentPage"] != comparison["expected_currentPage"]:
            failures.append(f"{locale}: currentPage mismatch")
        if comparison["key_recall"] < min_key_recall:
            failures.append(
                f"{locale}: key recall {comparison['key_recall']:.4f} < {min_key_recall:.4f}"
            )
        if comparison["choice_accuracy"] < min_choice_accuracy:
            failures.append(
                f"{locale}: choice accuracy {comparison['choice_accuracy']:.4f} < {min_choice_accuracy:.4f}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default="scripts/aia_pdf_recovery_targets.json")
    parser.add_argument("--output-dir", default="recovered_aia_json")
    parser.add_argument("--debug-dir", default="recovery_debug")
    parser.add_argument("--keep-pdfs", action="store_true")
    parser.add_argument("--skip-control", action="store_true")
    parser.add_argument("--min-control-key-recall", type=float, default=0.99)
    parser.add_argument("--min-control-choice-accuracy", type=float, default=0.99)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    targets = json.loads((repo_root / args.targets).read_text(encoding="utf-8"))
    output_dir = repo_root / args.output_dir
    debug_dir = repo_root / args.debug_dir if args.debug_dir else None
    s = http_session()
    schemas = load_schemas(s, repo_root)
    print("Loaded survey versions:", ", ".join(sorted(v["version"] for v in schemas.values())))

    control_report = None
    if not args.skip_control:
        if debug_dir is None:
            raise RecoveryError("Control validation requires --debug-dir")
        control_report = run_control(s, schemas, debug_dir, args.keep_pdfs)
        for locale in ("english", "french"):
            comparison = control_report.get(locale)
            if comparison:
                print(
                    f"CONTROL {locale.upper()}:",
                    f"key_recall={comparison['key_recall']:.4f}",
                    f"choice_accuracy={comparison['choice_accuracy']:.4f}",
                    f"keys={comparison['common_key_count']}/{comparison['expected_key_count']}",
                    f"text_similarity={comparison['mean_text_similarity']:.4f}",
                )
        failures = validate_control(
            control_report,
            args.min_control_key_recall,
            args.min_control_choice_accuracy,
        )
        if failures:
            print("CONTROL VALIDATION FAILED:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 3

    generated: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for target in targets:
        package_id = target["package_id"]
        print(f"Recovering {package_id} - {target.get('title', '')}")
        try:
            result = recover_package(
                s,
                package_id,
                schemas,
                output_dir,
                debug_dir,
                args.keep_pdfs,
            )
            generated.append(
                {
                    "package_id": package_id,
                    "package_title": result["package_title"],
                    "survey_version": result["survey_version"],
                    "phase": result["phase"],
                    "english_resource": result["english_resource"],
                    "french_resource": result["french_resource"],
                    "outputs": result["outputs"],
                    "english_matched_questions": result["english"]["matched_questions"],
                    "english_unresolved": result["english"]["unresolved"],
                    "french_matched_questions": (
                        result["french"]["matched_questions"] if result["french"] else None
                    ),
                    "french_unresolved": result["french"]["unresolved"] if result["french"] else None,
                }
            )
        except Exception as exc:
            print(f"ERROR {package_id}: {exc}", file=sys.stderr)
            failures.append({"package_id": package_id, "error": str(exc)})

    manifest = {"generated": generated, "failures": failures, "control": control_report}
    write_json(output_dir / "manifest.json", manifest)
    print(f"Recovered {len(generated)}/{len(targets)} target packages")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
