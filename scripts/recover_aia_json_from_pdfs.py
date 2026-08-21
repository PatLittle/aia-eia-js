#!/usr/bin/env python3
"""Recover one bilingual AIA SurveyFile JSON from published result PDFs.

The English result PDF is authoritative for the SurveyFile ``data`` object.
The French result PDF is used only for SurveyJS ``text`` and ``comment``
questions, whose French responses are written to ``translationsOnResult``.
Choice questions are never duplicated into the translation map because their
stored raw values are language-neutral.

Output shape::

    {
      "version": "v0.10.0",
      "currentPage": 12,
      "data": {...English/raw values...},
      "translationsOnResult": {...French text/comment values...}
    }

A published CBSA CRES/ReportIn assessment is used as a regression control. The
English reconstruction is checked against its published English JSON. French
text/comment reconstruction is checked against the corresponding fields in its
published French JSON. Recovery stops before target files are written if the
control falls below the requested thresholds.
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

CKAN_PACKAGE_SHOW = "https://open.canada.ca/data/api/3/action/package_show?id={}"
CURRENT_VERSION = "v1.0.1"
FINAL_PAGE = 12
CONTROL_PACKAGE_ID = "eaeb269c-6ac5-4429-a5aa-1fcc07c77933"
CONTROL_JSON_IDS = {
    "en": "dd83f660-f2c3-4de1-a953-2174e07401f8",
    "fr": "f6e0e812-2a79-4033-b38b-22b46177cc62",
}
USER_AGENT = "aia-eia-js PDF recovery/4.0 (+https://github.com/PatLittle/aia-eia-js)"

QUESTION_TYPES = {"text", "comment", "radiogroup", "dropdown", "checkbox", "boolean"}
CHOICE_TYPES = {"radiogroup", "dropdown", "checkbox", "boolean"}
TEXT_TYPES = {"text", "comment"}

NUMBERED_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.+?)\s*$")
SECTION_RE = re.compile(r"^\s*Section\s+\d+(?:\.\d+)?\s*:", re.I)
POINTS_RE = re.compile(
    r"\s*\[\s*(?:Points?|Modifier|Modificateur)\s*:\s*[+-]?\d+\s*\]\s*$",
    re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")

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


@dataclass(frozen=True)
class Question:
    name: str
    qtype: str
    title_en: str
    title_fr: str
    choices: tuple[tuple[str, str, str], ...]
    order: int
    score_type: str


@dataclass(frozen=True)
class Match:
    line_index: int
    question: Question
    score: float
    title_lines: int
    printed_number: int
    context: str


class RecoveryError(RuntimeError):
    pass


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
    for old, new in (
        ("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
        ("–", "-"), ("—", "-"), (" ", " "),
    ):
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip().lower()


def version_norm(value: str) -> str:
    value = str(value or "").strip().lower().replace("version", "").strip().lstrip("v")
    return value[1:] if value.startswith(".") else value


def http_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_json(session: requests.Session, url: str) -> Any:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    return response.json()


def get_bytes(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=120)
    response.raise_for_status()
    return response.content


def package_show(session: requests.Session, package_id: str) -> dict[str, Any]:
    payload = get_json(session, CKAN_PACKAGE_SHOW.format(package_id))
    if not payload.get("success"):
        raise RecoveryError(f"CKAN package_show failed for {package_id}")
    return payload["result"]


def walk_elements(
    elements: Iterable[dict[str, Any]],
    parents: tuple[str, ...] = (),
) -> Iterable[tuple[dict[str, Any], tuple[str, ...]]]:
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        name = str(element.get("name") or "")
        next_parents = parents + ((name,) if name else ())
        if element.get("type") == "panel":
            yield from walk_elements(element.get("elements") or [], next_parents)
        else:
            yield element, parents
            if element.get("elements"):
                yield from walk_elements(element.get("elements") or [], next_parents)


def score_type(name: str, parents: tuple[str, ...]) -> str:
    for candidate in (name, *reversed(parents)):
        if candidate.endswith("-RS"):
            return "RS"
        if candidate.endswith("-MS"):
            return "MS"
        if candidate.endswith("-NS"):
            return "NS"
    return "NS"


def choice_records(element: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    result: list[tuple[str, str, str]] = []
    for choice in element.get("choices") or []:
        if isinstance(choice, dict):
            raw = choice.get("value")
            if raw is None:
                raw = clean_display(choice.get("text"), "en")
            label = choice.get("text", raw)
            result.append((str(raw), clean_display(label, "en"), clean_display(label, "fr")))
        else:
            result.append((str(choice), str(choice), str(choice)))
    return tuple(result)


def schema_questions(schema: dict[str, Any]) -> list[Question]:
    result: list[Question] = []
    order = 0
    for page in schema.get("pages") or []:
        page_name = str(page.get("name") or "")
        for element, parents in walk_elements(page.get("elements") or [], (page_name,)):
            name = str(element.get("name") or "")
            qtype = str(element.get("type") or "")
            title = element.get("title")
            if not name or qtype not in QUESTION_TYPES or title is None:
                continue
            result.append(
                Question(
                    name=name,
                    qtype=qtype,
                    title_en=clean_display(title, "en"),
                    title_fr=clean_display(title, "fr"),
                    choices=choice_records(element),
                    order=order,
                    score_type=score_type(name, parents),
                )
            )
            order += 1
    return result


def schema_headers(schema: dict[str, Any], locale: str) -> set[str]:
    headers: set[str] = {
        norm("Algorithmic Impact Assessment Results"),
        norm("Résultats de l'évaluation de l'incidence algorithmique"),
        norm("Project Details"),
        norm("Détails du projet"),
    }

    def add(elements: Iterable[dict[str, Any]]) -> None:
        for element in elements or []:
            if not isinstance(element, dict):
                continue
            if element.get("type") == "panel" and element.get("title"):
                headers.add(norm(clean_display(element["title"], locale)))
            if element.get("elements"):
                add(element.get("elements") or [])

    for page in schema.get("pages") or []:
        if page.get("title"):
            headers.add(norm(clean_display(page["title"], locale)))
        add(page.get("elements") or [])
    return {value for value in headers if value}


def load_schemas(session: requests.Session, repo_root: Path) -> dict[str, dict[str, Any]]:
    current = json.loads((repo_root / "src" / "survey-enfr.json").read_text(encoding="utf-8"))
    schemas: dict[str, dict[str, Any]] = {
        version_norm(CURRENT_VERSION): {
            "version": CURRENT_VERSION,
            "definition": current,
            "source": "src/survey-enfr.json",
        }
    }
    manifest = json.loads(
        (repo_root / "src" / "generated" / "surveyVersions.json").read_text(encoding="utf-8")
    )
    for entry in manifest:
        try:
            definition = get_json(session, entry["sourceUrl"])
        except Exception as exc:
            print(f"WARNING: unable to fetch {entry['version']} schema: {exc}", file=sys.stderr)
            continue
        schemas[version_norm(entry["version"])] = {
            "version": entry["version"],
            "definition": definition,
            "source": entry["sourceUrl"],
        }
    return schemas


def pdf_resource_score(resource: dict[str, Any], locale: str) -> int:
    if str(resource.get("format") or "").upper() != "PDF":
        return -10_000
    haystack = " ".join((str(resource.get("name") or ""), str(resource.get("url") or ""))).lower()
    if any(term in haystack for term in EXCLUDE_PDF_TERMS):
        return -5_000
    score = 10 + (
        20 if any(term in haystack for term in ("aia", "algorithmic impact", "eia", "incidence algorithmique")) else 0
    )
    looks_fr = any(hint in haystack for hint in FRENCH_HINTS)
    looks_en = any(hint in haystack for hint in ENGLISH_HINTS)
    if locale == "en":
        score += 35 if looks_en else 0
        score -= 80 if looks_fr else 0
    else:
        score += 35 if looks_fr else 0
        score -= 80 if looks_en else 0
    return score


def choose_pdf(package: dict[str, Any], locale: str) -> dict[str, Any] | None:
    candidates = sorted(
        package.get("resources") or [],
        key=lambda resource: pdf_resource_score(resource, locale),
        reverse=True,
    )
    if not candidates or pdf_resource_score(candidates[0], locale) < 0:
        return None
    if locale == "fr" and pdf_resource_score(candidates[0], locale) < 35:
        return None
    return candidates[0]


def resource_by_id(package: dict[str, Any], resource_id: str) -> dict[str, Any] | None:
    return next(
        (resource for resource in package.get("resources") or [] if resource.get("id") == resource_id),
        None,
    )


def extract_pdf(pdf: bytes) -> str:
    document = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text("text", sort=True) for page in document)


def detect_version(text: str, schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for match in re.finditer(
        r"Version\s*[:\-]?\s*v?([0-9]+(?:\.[0-9A-Za-z]+){1,3})",
        text,
        flags=re.I,
    ):
        key = version_norm(match.group(1))
        if key in schemas:
            return schemas[key]
    text_n = norm(text)
    ranked: list[tuple[int, str]] = []
    for key, schema in schemas.items():
        hits = sum(
            1
            for question in schema_questions(schema["definition"])
            if len(norm(question.title_en)) >= 24 and norm(question.title_en) in text_n
        )
        ranked.append((hits, key))
    if not ranked:
        raise RecoveryError("No AIA survey schemas available")
    ranked.sort(reverse=True)
    return schemas[ranked[0][1]]


def infer_phase(english_text: str) -> str | None:
    match = re.search(
        r"Project\s+Phase\s*\n\s*(Design|Implementation)\b",
        english_text,
        flags=re.I,
    )
    if not match:
        return None
    return "Design" if norm(match.group(1)) == "design" else "Implementation"


def phase_compatible(question: Question, phase: str | None) -> bool:
    if not phase:
        return True
    name = question.name.lower()
    return not (
        phase == "Design" and "implementation" in name
        or phase == "Implementation" and "design" in name
    )


def context_change(line: str) -> str | None | bool:
    """Return NS/RS/MS, None to disable matching, or False for no change."""
    value = norm(line)
    if not value:
        return False
    if value in {"project details", "détails du projet", "details du projet"}:
        return "NS"
    if "project details" in value and value.startswith("section"):
        return "NS"
    if ("détails du projet" in value or "details du projet" in value) and value.startswith("section"):
        return "NS"
    if "questions and answers" in value and "mitigation" in value:
        return "MS"
    if "questions et réponses" in value or "questions et reponses" in value:
        if "mesures" in value or "atténuation" in value or "attenuation" in value:
            return "MS"
        if "risques" in value or "incidence" in value:
            return "RS"
    if "questions and answers" in value and "impact" in value:
        return "RS"
    if SECTION_RE.match(line) and "questions" not in value:
        return None
    return False


def title_score(title: str, lines: list[str], start: int, first: str) -> tuple[float, int]:
    target = norm(title)
    chunks = [first]
    best = (0.0, 1)
    for count in range(1, 9):
        if count > 1:
            index = start + count - 1
            if index >= len(lines):
                break
            value = lines[index].strip()
            if not value or NUMBERED_RE.match(value) or SECTION_RE.match(value):
                break
            chunks.append(value)
        candidate = norm(" ".join(chunks))
        if candidate == target:
            score = 100.0
        else:
            score = max(
                fuzz.ratio(target, candidate),
                fuzz.token_set_ratio(target, candidate) * 0.97,
            )
            if candidate.startswith(target) or target.startswith(candidate):
                score = max(score, 97.0)
        if score > best[0]:
            best = (score, count)
    return best


def find_matches(
    text: str,
    questions: list[Question],
    locale: str,
    phase: str | None,
) -> list[Match]:
    lines = [line.rstrip() for line in text.replace("\r", "").split("\n")]
    context: str | None = None
    last_order = {"NS": -1, "RS": -1, "MS": -1}
    used: set[str] = set()
    result: list[Match] = []

    for index, line in enumerate(lines):
        change = context_change(line)
        if change is not False:
            context = change
            continue
        if context not in {"NS", "RS", "MS"}:
            continue
        numbered = NUMBERED_RE.match(line)
        if not numbered:
            continue
        pool = [
            question
            for question in questions
            if question.score_type == context
            and question.order > last_order[context]
            and question.name not in used
            and phase_compatible(question, phase)
        ]
        best: tuple[float, int, Question] | None = None
        for question in pool:
            title = question.title_fr if locale == "fr" else question.title_en
            score, count = title_score(title, lines, index, numbered.group(2))
            if best is None or score > best[0] or (
                score == best[0] and question.order < best[2].order
            ):
                best = (score, count, question)
        if not best or best[0] < 84.0:
            continue
        score, count, question = best
        result.append(
            Match(index, question, score, count, int(numbered.group(1)), context)
        )
        last_order[context] = question.order
        used.add(question.name)
    return result


def structural_boundary(line: str, context: str) -> bool:
    change = context_change(line)
    if change is not False and change != context:
        return True
    value = norm(line)
    return value.startswith("section 1:") or value.startswith("section 2:")


def answer_lines(
    text: str,
    matches: list[Match],
    match_index: int,
    headers: set[str],
) -> list[str]:
    lines = [line.rstrip() for line in text.replace("\r", "").split("\n")]
    match = matches[match_index]
    start = match.line_index + match.title_lines
    end = matches[match_index + 1].line_index if match_index + 1 < len(matches) else len(lines)
    output: list[str] = []
    for raw in lines[start:end]:
        if structural_boundary(raw, match.context):
            break
        line = POINTS_RE.sub("", raw).rstrip()
        value = norm(line)
        if value in headers or value in {
            "algorithmic impact assessment results",
            "résultats de l'évaluation de l'incidence algorithmique",
        }:
            continue
        if re.fullmatch(r"\d+", value):
            continue
        output.append(line)
    while output and not output[0].strip():
        output.pop(0)
    while output and not output[-1].strip():
        output.pop()
    compact: list[str] = []
    previous_blank = False
    for line in output:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compact.append(line)
        previous_blank = blank
    return compact


def localized_label(choice: tuple[str, str, str], locale: str) -> str:
    return choice[2] if locale == "fr" else choice[1]


def parse_single(question: Question, lines: list[str], locale: str) -> str | bool | None:
    line_values = [norm(line) for line in lines if norm(line)]
    answer = norm(" ".join(lines))
    exact: list[tuple[str, str]] = []
    for choice in question.choices:
        label = norm(localized_label(choice, locale) or choice[1])
        if label and label in line_values:
            exact.append((choice[0], label))
    if exact:
        return max(exact, key=lambda item: len(item[1]))[0]

    ranked: list[tuple[float, str]] = []
    for choice in question.choices:
        label = norm(localized_label(choice, locale) or choice[1])
        if not label:
            continue
        if answer == label:
            return choice[0]
        ranked.append(
            (
                max(
                    fuzz.ratio(answer, label),
                    fuzz.token_set_ratio(answer, label) * 0.94,
                    fuzz.partial_ratio(answer, label) * 0.82,
                ),
                choice[0],
            )
        )
    if ranked:
        ranked.sort(reverse=True)
        if ranked[0][0] >= 72:
            return ranked[0][1]
    if question.qtype == "boolean":
        if answer.startswith(("yes", "oui")):
            return True
        if answer.startswith(("no", "non")):
            return False
    return None


def parse_checkbox(question: Question, lines: list[str], locale: str) -> list[str]:
    answer = norm(" ".join(lines))
    found: list[tuple[int, str]] = []
    for choice in question.choices:
        raw = choice[0]
        label = norm(localized_label(choice, locale) or choice[1])
        if not label:
            continue
        position = answer.find(label)
        if position >= 0:
            found.append((position, raw))
            continue
        best_score = 0.0
        best_position = 10**9
        for line_no in range(len(lines)):
            for width in (1, 2, 3):
                chunk = norm(" ".join(lines[line_no : line_no + width]))
                if not chunk:
                    continue
                score = max(
                    fuzz.ratio(label, chunk),
                    fuzz.token_set_ratio(label, chunk) * 0.96,
                )
                if score > best_score:
                    best_score, best_position = score, line_no * 1000
        if best_score >= 91:
            found.append((best_position, raw))

    result: list[str] = []
    seen: set[str] = set()
    for _, raw in sorted(found, key=lambda item: item[0]):
        if raw not in seen:
            result.append(raw)
            seen.add(raw)
    return result


def parse_value(question: Question, lines: list[str], locale: str) -> Any:
    if question.qtype in TEXT_TYPES:
        return "\n".join(lines).strip()
    if question.qtype == "checkbox":
        return parse_checkbox(question, lines, locale)
    return parse_single(question, lines, locale)


def reconstruct(
    text: str,
    schema: dict[str, Any],
    locale: str,
    phase: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    questions = schema_questions(schema)
    matches = find_matches(text, questions, locale, phase)
    headers = schema_headers(schema, locale)
    data: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {
        "phase": phase,
        "matched_questions": len(matches),
        "schema_questions": len(questions),
        "unresolved": [],
        "matches": [],
    }
    for index, match in enumerate(matches):
        lines = answer_lines(text, matches, index, headers)
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


def build_translations(
    french_data: dict[str, Any], questions: list[Question]
) -> dict[str, Any]:
    text_fields = {question.name for question in questions if question.qtype in TEXT_TYPES}
    return {
        name: french_data[name]
        for name in text_fields
        if name in french_data and french_data[name] is not None
    }


def make_survey_file(
    version: str,
    english_data: dict[str, Any],
    french_data: dict[str, Any],
    questions: list[Question],
) -> dict[str, Any]:
    return {
        "version": version,
        "currentPage": FINAL_PAGE,
        "data": english_data,
        "translationsOnResult": build_translations(french_data, questions),
    }


def compare_english(
    expected: dict[str, Any], recovered: dict[str, Any], questions: list[Question]
) -> dict[str, Any]:
    expected_data = expected.get("data") or {}
    recovered_data = recovered.get("data") or {}
    question_map = {question.name: question for question in questions}
    expected_keys, recovered_keys = set(expected_data), set(recovered_data)
    common = expected_keys & recovered_keys
    choice_total = choice_exact = text_total = 0
    text_sum = 0.0
    mismatches: list[dict[str, Any]] = []

    for key in sorted(common):
        question = question_map.get(key)
        if question and question.qtype in CHOICE_TYPES:
            choice_total += 1
            if expected_data[key] == recovered_data[key]:
                choice_exact += 1
            else:
                mismatches.append(
                    {
                        "name": key,
                        "type": question.qtype,
                        "expected": expected_data[key],
                        "recovered": recovered_data[key],
                    }
                )
        elif question and question.qtype in TEXT_TYPES:
            text_total += 1
            left, right = norm(expected_data[key]), norm(recovered_data[key])
            similarity = 1.0 if left == right else fuzz.ratio(left, right) / 100
            text_sum += similarity
            if similarity < 0.90:
                mismatches.append(
                    {
                        "name": key,
                        "type": question.qtype,
                        "text_similarity": round(similarity, 4),
                        "expected": expected_data[key],
                        "recovered": recovered_data[key],
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
        "mean_text_similarity": round(text_sum / text_total, 4) if text_total else 1.0,
        "missing_keys": sorted(expected_keys - recovered_keys),
        "extra_keys": sorted(recovered_keys - expected_keys),
        "mismatches": mismatches,
    }


def compare_french_translations(
    expected_french: dict[str, Any],
    recovered: dict[str, Any],
    questions: list[Question],
) -> dict[str, Any]:
    text_fields = {question.name for question in questions if question.qtype in TEXT_TYPES}
    expected_data = expected_french.get("data") or {}
    expected = {
        name: expected_data[name]
        for name in text_fields
        if name in expected_data and expected_data[name] is not None
    }
    actual = recovered.get("translationsOnResult") or {}
    expected_keys, actual_keys = set(expected), set(actual)
    common = expected_keys & actual_keys
    similarities: list[float] = []
    mismatches: list[dict[str, Any]] = []
    for key in sorted(common):
        left, right = norm(expected[key]), norm(actual[key])
        similarity = 1.0 if left == right else fuzz.ratio(left, right) / 100
        similarities.append(similarity)
        if similarity < 0.90:
            mismatches.append(
                {
                    "name": key,
                    "text_similarity": round(similarity, 4),
                    "expected": expected[key],
                    "recovered": actual[key],
                }
            )
    return {
        "expected_translation_count": len(expected_keys),
        "recovered_translation_count": len(actual_keys),
        "common_translation_count": len(common),
        "translation_recall": round(len(common) / len(expected_keys), 4) if expected_keys else 1.0,
        "translation_precision": round(len(common) / len(actual_keys), 4) if actual_keys else 0.0,
        "mean_text_similarity": round(sum(similarities) / len(similarities), 4) if similarities else 1.0,
        "missing_translation_keys": sorted(expected_keys - actual_keys),
        "extra_translation_keys": sorted(actual_keys - expected_keys),
        "mismatches": mismatches,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_control(
    session: requests.Session,
    schemas: dict[str, dict[str, Any]],
    debug_dir: Path,
    keep_pdfs: bool,
) -> dict[str, Any]:
    package = package_show(session, CONTROL_PACKAGE_ID)
    en_pdf_resource = choose_pdf(package, "en")
    fr_pdf_resource = choose_pdf(package, "fr")
    if not en_pdf_resource or not fr_pdf_resource:
        raise RecoveryError("Control package is missing its bilingual AIA PDFs")

    en_pdf = get_bytes(session, en_pdf_resource["url"])
    fr_pdf = get_bytes(session, fr_pdf_resource["url"])
    en_text = extract_pdf(en_pdf)
    fr_text = extract_pdf(fr_pdf)
    selected = detect_version(en_text, schemas)
    version, schema = selected["version"], selected["definition"]
    phase = infer_phase(en_text)
    questions = schema_questions(schema)
    en_data, en_diagnostics = reconstruct(en_text, schema, "en", phase)
    fr_data, fr_diagnostics = reconstruct(fr_text, schema, "fr", phase)
    recovered = make_survey_file(version, en_data, fr_data, questions)

    expected_en_resource = resource_by_id(package, CONTROL_JSON_IDS["en"])
    expected_fr_resource = resource_by_id(package, CONTROL_JSON_IDS["fr"])
    if not expected_en_resource or not expected_fr_resource:
        raise RecoveryError("Control package is missing its published JSON resources")
    expected_en = get_json(session, expected_en_resource["url"])
    expected_fr = get_json(session, expected_fr_resource["url"])

    report = {
        "package_id": CONTROL_PACKAGE_ID,
        "version": version,
        "phase": phase,
        "english": compare_english(expected_en, recovered, questions),
        "french_translations": compare_french_translations(expected_fr, recovered, questions),
        "diagnostics": {"en": en_diagnostics, "fr": fr_diagnostics},
    }
    control_dir = debug_dir / "control"
    control_dir.mkdir(parents=True, exist_ok=True)
    (control_dir / "en.txt").write_text(en_text, encoding="utf-8")
    (control_dir / "fr.txt").write_text(fr_text, encoding="utf-8")
    write_json(control_dir / "expected-en.json", expected_en)
    write_json(control_dir / "expected-fr.json", expected_fr)
    write_json(control_dir / "recovered-bilingual.json", recovered)
    write_json(control_dir / "comparison.json", report)

    if keep_pdfs:
        pdf_dir = debug_dir / "pdfs"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        (pdf_dir / f"{CONTROL_PACKAGE_ID}-en.pdf").write_bytes(en_pdf)
        (pdf_dir / f"{CONTROL_PACKAGE_ID}-fr.pdf").write_bytes(fr_pdf)
    return report


def validate_control(
    report: dict[str, Any],
    min_recall: float,
    min_choice: float,
    min_translation_recall: float,
    min_translation_similarity: float,
) -> list[str]:
    failures: list[str] = []
    english = report["english"]
    french = report["french_translations"]
    if english["expected_version"] != english["recovered_version"]:
        failures.append("English: version mismatch")
    if english["expected_currentPage"] != english["recovered_currentPage"]:
        failures.append("English: currentPage mismatch")
    if english["key_recall"] < min_recall:
        failures.append(
            f"English: key recall {english['key_recall']:.4f} < {min_recall:.4f}"
        )
    if english["choice_accuracy"] < min_choice:
        failures.append(
            f"English: choice accuracy {english['choice_accuracy']:.4f} < {min_choice:.4f}"
        )
    if french["translation_recall"] < min_translation_recall:
        failures.append(
            "French: translation recall "
            f"{french['translation_recall']:.4f} < {min_translation_recall:.4f}"
        )
    if french["mean_text_similarity"] < min_translation_similarity:
        failures.append(
            "French: mean text similarity "
            f"{french['mean_text_similarity']:.4f} < {min_translation_similarity:.4f}"
        )
    return failures


def recover_package(
    session: requests.Session,
    package_id: str,
    schemas: dict[str, dict[str, Any]],
    output_dir: Path,
    debug_dir: Path | None,
    keep_pdfs: bool,
) -> dict[str, Any]:
    package = package_show(session, package_id)
    resources = {locale: choose_pdf(package, locale) for locale in ("en", "fr")}
    if not resources["en"]:
        raise RecoveryError(f"No English AIA PDF found for {package_id}")
    if not resources["fr"] or resources["fr"]["url"] == resources["en"]["url"]:
        raise RecoveryError(f"No distinct French AIA PDF found for {package_id}")

    pdfs = {
        "en": get_bytes(session, resources["en"]["url"]),
        "fr": get_bytes(session, resources["fr"]["url"]),
    }
    texts = {locale: extract_pdf(pdf) for locale, pdf in pdfs.items()}
    selected = detect_version(texts["en"], schemas)
    version, schema = selected["version"], selected["definition"]
    phase = infer_phase(texts["en"])
    questions = schema_questions(schema)
    en_data, en_diagnostics = reconstruct(texts["en"], schema, "en", phase)
    fr_data, fr_diagnostics = reconstruct(texts["fr"], schema, "fr", phase)
    survey_file = make_survey_file(version, en_data, fr_data, questions)

    package_dir = output_dir / package_id
    package_dir.mkdir(parents=True, exist_ok=True)
    output = package_dir / "aia-results.json"
    write_json(output, survey_file)
    for legacy_name in ("aia-results-en.json", "aia-results-fr.json"):
        legacy = package_dir / legacy_name
        if legacy.exists():
            legacy.unlink()

    result: dict[str, Any] = {
        "package_id": package_id,
        "package_title": package.get("title"),
        "survey_version": version,
        "phase": phase,
        "schema_source": selected["source"],
        "resources": {
            locale: {
                "id": resource.get("id"),
                "name": resource.get("name"),
                "url": resource.get("url"),
            }
            for locale, resource in resources.items()
            if resource
        },
        "output": str(output.relative_to(Path(__file__).resolve().parents[1])),
        "translation_count": len(survey_file["translationsOnResult"]),
        "diagnostics": {"en": en_diagnostics, "fr": fr_diagnostics},
    }

    if debug_dir:
        package_debug = debug_dir / package_id
        package_debug.mkdir(parents=True, exist_ok=True)
        for locale, text in texts.items():
            (package_debug / f"{locale}.txt").write_text(text, encoding="utf-8")
        write_json(package_debug / "diagnostics.json", result)
        if keep_pdfs:
            pdf_dir = debug_dir / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            for locale, pdf in pdfs.items():
                (pdf_dir / f"{package_id}-{locale}.pdf").write_bytes(pdf)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", default="scripts/aia_pdf_recovery_targets.json")
    parser.add_argument("--output-dir", default="recovered_aia_json")
    parser.add_argument("--debug-dir", default="recovery_debug")
    parser.add_argument("--keep-pdfs", action="store_true")
    parser.add_argument("--skip-control", action="store_true")
    parser.add_argument("--min-control-key-recall", type=float, default=0.99)
    parser.add_argument("--min-control-choice-accuracy", type=float, default=0.99)
    parser.add_argument("--min-control-translation-recall", type=float, default=0.99)
    parser.add_argument("--min-control-translation-similarity", type=float, default=0.95)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    targets = json.loads((root / args.targets).read_text(encoding="utf-8"))
    output_dir = root / args.output_dir
    debug_dir = root / args.debug_dir if args.debug_dir else None
    session = http_session()
    schemas = load_schemas(session, root)
    print("Loaded survey versions:", ", ".join(sorted(schema["version"] for schema in schemas.values())))

    control = None
    if not args.skip_control:
        if debug_dir is None:
            raise RecoveryError("Control validation requires --debug-dir")
        control = run_control(session, schemas, debug_dir, args.keep_pdfs)
        english = control["english"]
        french = control["french_translations"]
        print(
            "CONTROL EN:",
            f"key_recall={english['key_recall']:.4f}",
            f"choice_accuracy={english['choice_accuracy']:.4f}",
            f"keys={english['common_key_count']}/{english['expected_key_count']}",
            f"text_similarity={english['mean_text_similarity']:.4f}",
        )
        print(
            "CONTROL FR translations:",
            f"recall={french['translation_recall']:.4f}",
            f"translations={french['common_translation_count']}/{french['expected_translation_count']}",
            f"text_similarity={french['mean_text_similarity']:.4f}",
        )
        failures = validate_control(
            control,
            args.min_control_key_recall,
            args.min_control_choice_accuracy,
            args.min_control_translation_recall,
            args.min_control_translation_similarity,
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
            generated.append(
                recover_package(
                    session,
                    package_id,
                    schemas,
                    output_dir,
                    debug_dir,
                    args.keep_pdfs,
                )
            )
        except Exception as exc:
            print(f"ERROR {package_id}: {exc}", file=sys.stderr)
            failures.append({"package_id": package_id, "error": str(exc)})

    manifest = {"generated": generated, "failures": failures, "control": control}
    write_json(output_dir / "manifest.json", manifest)
    print(f"Recovered {len(generated)}/{len(targets)} target packages")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
