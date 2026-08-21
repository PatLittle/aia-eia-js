# AIA bilingual JSON and JSONL data model

The AIA data pipeline uses one bilingual SurveyFile per assessment.

```json
{
  "version": "v1.0.1",
  "currentPage": 12,
  "data": {},
  "translationsOnResult": {}
}
```

- `data` is reconstructed from the English AIA result PDF and contains all raw SurveyJS values.
- `translationsOnResult` contains French values only for questions whose SurveyJS type is `text` or `comment` in the matching questionnaire version.
- Raw values for radio, dropdown, checkbox, and boolean questions are language-neutral and are stored only in `data`.

`public/aia-analysis-data/aia-results.jsonl` is generated during the GitHub Pages build. It contains one normalized record per AIA package. A usable JSON resource published on Open Canada is preferred. When no usable published JSON exists, the corresponding file in `recovered_aia_json/<package-id>/aia-results.json` is used instead.

Each JSONL record adds catalogue metadata and derived analysis fields around the bilingual SurveyFile, including publication date, organization, source (`published` or `recovered`), questionnaire version, project phase, impact level, and completeness metrics.
