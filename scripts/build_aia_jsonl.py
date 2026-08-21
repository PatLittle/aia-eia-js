#!/usr/bin/env python3
"""Build a unified bilingual JSON Lines dataset for published AIA results.

The output contains one record per AIA package. Published Open Canada JSON is
preferred. If a package has no usable published JSON, a reconstructed bilingual
SurveyFile from ``recovered_aia_json`` is used.

When a published package provides separate English and French JSON resources,
the English SurveyFile supplies ``data`` and French text/comment responses are
merged into ``translationsOnResult`` using the questionnaire definition for the
embedded survey version.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OPEN_CANADA_BASE = "https://open.canada.ca"
PACKAGE_SEARCH_URL = f"{OPEN_CANADA_BASE}/data/api/action/package_search"
COLLECTION_QUERY = "collection:aia"
CURRENT_VERSION = "v1.0.1"
PAGE_SIZE = 100
REQUEST_TIMEOUT = 90
USER_AGENT = "aia-eia-js JSONL builder/1.0 (+https://github.com/PatLittle/aia-eia-js)"
EXCLUDED_PACKAGE_IDS = {"5423054a-093c-4239-85be-fa0b36ae0b2e"}
QUESTION_TYPES = {"text", "comment", "radiogroup", "dropdown", "checkbox", "boolean"}
TEXT_TYPES = {"text", "comment"}
CHOICE_TYPES = {"radiogroup", "dropdown", "checkbox"}
FRENCH_HINTS = (
    "-fr.", "-fr-", "_fr.", "_fre.", "french", "francais", "français",
    "resultats", "résultats", "evaluation-de", "évaluation-de",
)
ENGLISH_HINTS = ("-en.", "-en-", "_en.", "english", "results")


@dataclass(frozen=True)
class QuestionMeta:
    name: str
    qtype: str
    conditional: bool
    score_type: str
    choices: tuple[str, ...]


def version_norm(value: str) -> str:
    value = str(value or "").strip().lower().replace("version", "").strip().lstrip("v")
    return value[1:] if value.startswith(".") else value


def absolute_open_canada_url(value: Any) -> str:
    """Resolve CKAN resource URLs, including package_search relative paths."""
    url = str(value or "").strip()
    if not url:
        return ""
    return urljoin(f"{OPEN_CANADA_BASE}/", url)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def get_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def package_search_all(session: requests.Session) -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    start = 0
    total: int | None = None
    while True:
        payload = get_json(
            session,
            PACKAGE_SEARCH_URL,
            params={
                "q": COLLECTION_QUERY,
                "rows": PAGE_SIZE,
                "start": start,
                "sort": "metadata_modified desc",
            },
        )
        if not payload.get("success"):
            raise RuntimeError(f"CKAN package_search failed: {payload}")
        result = payload.get("result") or {}
        batch = result.get("results") or []
        if total is None:
            total = int(result.get("count", len(batch)))
        if not batch:
            break
        packages.extend(batch)
        start += len(batch)
        if total is not None and start >= total:
            break

    unique = {
        package["id"]: package
        for package in packages
        if package.get("id")
        and package.get("id") not in EXCLUDED_PACKAGE_IDS
        and str(package.get("collection", "")).strip().lower() == "aia"
    }
    return list(unique.values())


def localized(value: Any) -> tuple[str, str]:
    if value is None:
        return "", ""
    if isinstance(value, str):
        return value, value
    if isinstance(value, dict):
        en = value.get("en") or value.get("default") or value.get("fr") or ""
        fr = value.get("fr") or value.get("default") or value.get("en") or ""
        return str(en), str(fr)
    return str(value), str(value)


def organization_titles(package: dict[str, Any]) -> tuple[str, str]:
    organization = package.get("organization") or {}
    if not isinstance(organization, dict):
        return localized(organization)
    value = (
        organization.get("title_translated")
        or organization.get("title")
        or organization.get("name")
    )
    return localized(value)


def walk_elements(
    elements: Iterable[dict[str, Any]],
    parents: tuple[str, ...] = (),
    inherited_conditional: bool = False,
) -> Iterable[tuple[dict[str, Any], tuple[str, ...], bool]]:
    for element in elements or []:
        if not isinstance(element, dict):
            continue
        name = str(element.get("name") or "")
        conditional = inherited_conditional or bool(element.get("visibleIf"))
        next_parents = parents + ((name,) if name else ())
        if element.get("type") == "panel":
            yield from walk_elements(
                element.get("elements") or [], next_parents, conditional
            )
        else:
            yield element, parents, conditional
            if element.get("elements"):
                yield from walk_elements(
                    element.get("elements") or [], next_parents, conditional
                )


def score_type(name: str, parents: tuple[str, ...]) -> str:
    for candidate in (name, *reversed(parents)):
        if candidate.endswith("-RS"):
            return "RS"
        if candidate.endswith("-MS"):
            return "MS"
        if candidate.endswith("-NS"):
            return "NS"
    return "NS"


def schema_questions(schema: dict[str, Any]) -> list[QuestionMeta]:
    questions: list[QuestionMeta] = []
    for page in schema.get("pages") or []:
        page_name = str(page.get("name") or "")
        page_conditional = bool(page.get("visibleIf"))
        for element, parents, conditional in walk_elements(
            page.get("elements") or [], (page_name,), page_conditional
        ):
            name = str(element.get("name") or "")
            qtype = str(element.get("type") or "")
            if not name or qtype not in QUESTION_TYPES:
                continue
            choices: list[str] = []
            for choice in element.get("choices") or []:
                if isinstance(choice, dict):
                    raw = choice.get("value")
                    if raw is None:
                        raw = choice.get("text")
                    choices.append(str(raw))
                else:
                    choices.append(str(choice))
            questions.append(
                QuestionMeta(
                    name=name,
                    qtype=qtype,
                    conditional=conditional,
                    score_type=score_type(name, parents),
                    choices=tuple(choices),
                )
            )
    return questions


def load_schemas(
    session: requests.Session, repo_root: Path
) -> dict[str, dict[str, Any]]:
    current = json.loads(
        (repo_root / "src" / "survey-enfr.json").read_text(encoding="utf-8")
    )
    schemas: dict[str, dict[str, Any]] = {
        version_norm(CURRENT_VERSION): {
            "version": CURRENT_VERSION,
            "definition": current,
        }
    }
    manifest = json.loads(
        (repo_root / "src" / "generated" / "surveyVersions.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in manifest:
        try:
            definition = get_json(session, entry["sourceUrl"])
        except Exception as exc:
            print(f"WARNING: unable to fetch survey {entry.get('version')}: {exc}")
            continue
        schemas[version_norm(entry["version"])] = {
            "version": entry["version"],
            "definition": definition,
        }
    return schemas


def valid_survey_file(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("data"), dict)
        and bool(value.get("version"))
    )


def json_resource_candidates(package: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for resource in package.get("resources") or []:
        fmt = str(resource.get("format") or "").strip().lower()
        url = str(resource.get("url") or "")
        if fmt == "json" or re.search(r"\.json(?:$|[?#])", url, re.I):
            candidates.append(resource)
    return candidates


def resource_locale(resource: dict[str, Any]) -> str:
    haystack = " ".join(
        [
            str(resource.get("name") or ""),
            str(resource.get("url") or ""),
            str(resource.get("description") or ""),
        ]
    ).lower()
    fr = any(hint in haystack for hint in FRENCH_HINTS)
    en = any(hint in haystack for hint in ENGLISH_HINTS)
    if fr and not en:
        return "fr"
    if en and not fr:
        return "en"
    return "unknown"


def load_published_jsons(
    session: requests.Session, package: dict[str, Any]
) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    loaded: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for resource in json_resource_candidates(package):
        normalized_resource = dict(resource)
        normalized_resource["url"] = absolute_open_canada_url(resource.get("url"))
        try:
            value = get_json(session, normalized_resource["url"])
        except Exception as exc:
            print(
                f"WARNING: {package.get('id')} JSON "
                f"{normalized_resource.get('url')} failed: {exc}"
            )
            continue
        if valid_survey_file(value):
            loaded.append(
                (normalized_resource, value, resource_locale(normalized_resource))
            )
    return loaded


def text_fields_for_version(
    version: str, schemas: dict[str, dict[str, Any]]
) -> set[str]:
    schema = schemas.get(version_norm(version))
    if not schema:
        return set()
    return {
        question.name
        for question in schema_questions(schema["definition"])
        if question.qtype in TEXT_TYPES
    }


def merge_bilingual(
    english: dict[str, Any],
    french: dict[str, Any] | None,
    schemas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = {
        "version": english.get("version"),
        "currentPage": english.get("currentPage", 0),
        "data": dict(english.get("data") or {}),
        "translationsOnResult": dict(english.get("translationsOnResult") or {}),
    }
    if not french:
        return result

    text_fields = text_fields_for_version(str(result.get("version") or ""), schemas)
    french_data = french.get("data") or {}
    for name in text_fields:
        if name in french_data and french_data[name] not in (None, ""):
            result["translationsOnResult"].setdefault(name, french_data[name])
    return result


def choose_published_survey(
    loaded: list[tuple[dict[str, Any], dict[str, Any], str]],
    schemas: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[str]] | None:
    if not loaded:
        return None

    def base_rank(
        item: tuple[dict[str, Any], dict[str, Any], str]
    ) -> tuple[int, int]:
        _resource, survey, locale = item
        translations = survey.get("translationsOnResult") or {}
        bilingual = 1 if isinstance(translations, dict) and bool(translations) else 0
        locale_rank = {"en": 3, "unknown": 2, "fr": 1}.get(locale, 0)
        return (bilingual * 10 + locale_rank, len(survey.get("data") or {}))

    base_resource, base_survey, base_locale = max(loaded, key=base_rank)
    french_candidates = [
        item
        for item in loaded
        if item[2] == "fr" and item[0].get("url") != base_resource.get("url")
    ]
    french_survey = (
        max(french_candidates, key=lambda item: len(item[1].get("data") or {}))[1]
        if french_candidates
        else None
    )

    if base_locale == "fr":
        english_candidates = [item for item in loaded if item[2] == "en"]
        if english_candidates:
            base_resource, base_survey, _ = max(
                english_candidates,
                key=lambda item: len(item[1].get("data") or {}),
            )
            if french_survey is None:
                french_survey = max(
                    [item for item in loaded if item[2] == "fr"],
                    key=lambda item: len(item[1].get("data") or {}),
                )[1]

    merged = merge_bilingual(base_survey, french_survey, schemas)
    urls = [
        str(resource.get("url"))
        for resource, _, _ in loaded
        if resource.get("url")
    ]
    return base_resource, merged, urls


def load_recovered_survey(
    recovered_dir: Path,
    package_id: str,
    schemas: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str] | None:
    package_dir = recovered_dir / package_id
    bilingual_path = package_dir / "aia-results.json"
    if bilingual_path.exists():
        value = json.loads(bilingual_path.read_text(encoding="utf-8"))
        if valid_survey_file(value):
            value.setdefault("translationsOnResult", {})
            return value, str(bilingual_path)

    # Transitional compatibility with the previous EN/FR recovery layout.
    english_path = package_dir / "aia-results-en.json"
    french_path = package_dir / "aia-results-fr.json"
    if english_path.exists():
        english = json.loads(english_path.read_text(encoding="utf-8"))
        french = (
            json.loads(french_path.read_text(encoding="utf-8"))
            if french_path.exists()
            else None
        )
        if valid_survey_file(english):
            return merge_bilingual(english, french, schemas), str(english_path)
    return None


def parse_embedded_value(value: Any) -> int:
    if isinstance(value, list):
        return sum(parse_embedded_value(item) for item in value)
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    match = re.search(r"-(-?\d+)$", value)
    return int(match.group(1)) if match else 0


def max_question_score(question: QuestionMeta) -> int:
    scores = [parse_embedded_value(choice) for choice in question.choices]
    if question.qtype == "checkbox":
        return sum(scores)
    return max(scores, default=0)


def impact_metrics(
    data: dict[str, Any], questions: list[QuestionMeta]
) -> dict[str, Any]:
    raw_risk = mitigation = max_raw = max_mitigation = 0
    for question in questions:
        if question.qtype not in CHOICE_TYPES:
            continue
        if question.score_type == "RS":
            raw_risk += parse_embedded_value(data.get(question.name))
            max_raw += max_question_score(question)
        elif question.score_type == "MS":
            mitigation += parse_embedded_value(data.get(question.name))
            max_mitigation += max_question_score(question)

    total = raw_risk
    if max_mitigation and mitigation >= 0.8 * (max_mitigation / 2):
        total = round(0.85 * raw_risk)

    if max_raw <= 0:
        level = None
    elif total <= max_raw * 0.25:
        level = 1
    elif total <= max_raw * 0.50:
        level = 2
    elif total <= max_raw * 0.75:
        level = 3
    else:
        level = 4

    return {
        "raw_risk_score": raw_risk,
        "mitigation_score": mitigation,
        "final_score": total,
        "impact_level": level,
        "impact_level_label": f"Level {level}" if level else "",
    }


def project_phase(data: dict[str, Any]) -> str:
    value = data.get("projectDetailsPhase")
    if value == "item1":
        return "Design"
    if value == "item2":
        return "Implementation"
    return "Unknown"


def phase_compatible(name: str, phase: str) -> bool:
    lower = name.lower()
    return not (
        phase == "Design" and "implementation" in lower
        or phase == "Implementation" and "design" in lower
    )


def answered(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def completeness_metrics(
    data: dict[str, Any], questions: list[QuestionMeta]
) -> dict[str, Any]:
    phase = project_phase(data)
    eligible = [
        question for question in questions if phase_compatible(question.name, phase)
    ]
    nonconditional = [question for question in eligible if not question.conditional]
    answered_all = sum(
        1 for question in eligible if answered(data.get(question.name))
    )
    answered_nonconditional = sum(
        1 for question in nonconditional if answered(data.get(question.name))
    )
    return {
        "project_phase": phase,
        "eligible_question_count": len(eligible),
        "answered_question_count": answered_all,
        "completeness_pct": (
            round(100 * answered_all / len(eligible), 2) if eligible else None
        ),
        "nonconditional_question_count": len(nonconditional),
        "answered_nonconditional_count": answered_nonconditional,
        "nonconditional_completeness_pct": (
            round(100 * answered_nonconditional / len(nonconditional), 2)
            if nonconditional
            else None
        ),
    }


def schema_for_survey(
    survey: dict[str, Any], schemas: dict[str, dict[str, Any]]
) -> list[QuestionMeta]:
    schema = schemas.get(version_norm(str(survey.get("version") or "")))
    return schema_questions(schema["definition"]) if schema else []


def make_record(
    package: dict[str, Any],
    survey: dict[str, Any],
    source: str,
    resource_url: str,
    resource_urls: list[str],
    schemas: dict[str, dict[str, Any]],
    recovered_path: str = "",
) -> dict[str, Any]:
    title_en, title_fr = localized(
        package.get("title_translated") or package.get("title")
    )
    org_en, org_fr = organization_titles(package)
    questions = schema_for_survey(survey, schemas)
    data = survey.get("data") or {}
    derived = {
        **impact_metrics(data, questions),
        **completeness_metrics(data, questions),
    }
    return {
        "package_id": package.get("id"),
        "title_en": title_en,
        "title_fr": title_fr,
        "organization_en": org_en,
        "organization_fr": org_fr,
        "metadata_created": package.get("metadata_created") or "",
        "metadata_modified": package.get("metadata_modified") or "",
        "dataset_url": f"{OPEN_CANADA_BASE}/data/en/dataset/{package.get('id')}",
        "source": source,
        "resource_url": resource_url,
        "resource_urls": resource_urls,
        "recovered_path": recovered_path,
        "version": survey.get("version"),
        "currentPage": survey.get("currentPage", 0),
        "data": data,
        "translationsOnResult": survey.get("translationsOnResult") or {},
        "derived": derived,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="public/aia-analysis-data/aia-results.jsonl"
    )
    parser.add_argument(
        "--summary-output",
        default="public/aia-analysis-data/aia-results-summary.json",
    )
    parser.add_argument("--recovered-dir", default="recovered_aia_json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = root / args.output
    summary_output = root / args.summary_output
    recovered_dir = root / args.recovered_dir
    session = build_session()
    schemas = load_schemas(session, root)
    packages = package_search_all(session)

    records: list[dict[str, Any]] = []
    missing: list[str] = []
    published_count = recovered_count = 0

    for package in packages:
        package_id = str(package.get("id") or "")
        loaded = load_published_jsons(session, package)
        selected = choose_published_survey(loaded, schemas)
        if selected:
            resource, survey, urls = selected
            records.append(
                make_record(
                    package,
                    survey,
                    "published",
                    str(resource.get("url") or ""),
                    urls,
                    schemas,
                )
            )
            published_count += 1
            continue

        recovered = load_recovered_survey(recovered_dir, package_id, schemas)
        if recovered:
            survey, recovered_path = recovered
            raw_url = (
                "https://raw.githubusercontent.com/PatLittle/aia-eia-js/master/"
                f"recovered_aia_json/{package_id}/aia-results.json"
            )
            records.append(
                make_record(
                    package,
                    survey,
                    "recovered",
                    raw_url,
                    [],
                    schemas,
                    recovered_path=recovered_path,
                )
            )
            recovered_count += 1
        else:
            missing.append(package_id)

    records.sort(
        key=lambda record: (
            str(record.get("metadata_created") or ""),
            str(record.get("package_id") or ""),
        )
    )
    write_jsonl(output, records)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalogue_count": len(packages),
        "record_count": len(records),
        "published_count": published_count,
        "recovered_count": recovered_count,
        "missing_count": len(missing),
        "missing_package_ids": sorted(missing),
        "survey_versions_loaded": sorted(
            {schema["version"] for schema in schemas.values()}
        ),
    }
    write_json(summary_output, summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
