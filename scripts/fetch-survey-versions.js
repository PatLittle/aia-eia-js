"use strict";

const fs = require("fs");
const https = require("https");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const manifestPath = path.join(projectRoot, "aia_release_csv_manifest.csv");
const publicSurveyRoot = path.join(projectRoot, "public", "surveys");
const generatedPath = path.join(
  projectRoot,
  "src",
  "generated",
  "surveyVersions.json"
);

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    const next = text[index + 1];

    if (quoted && character === '"' && next === '"') {
      field += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (!quoted && character === ",") {
      row.push(field);
      field = "";
    } else if (!quoted && (character === "\n" || character === "\r")) {
      if (character === "\r" && next === "\n") index += 1;
      row.push(field);
      field = "";
      if (row.some(value => value !== "")) rows.push(row);
      row = [];
    } else {
      field += character;
    }
  }

  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }

  const headers = rows.shift();
  return rows.map(values =>
    headers.reduce((record, header, index) => {
      record[header] = values[index] || "";
      return record;
    }, {})
  );
}

function isSupportedVersion(version) {
  const match = String(version).match(/(\d+)\.(\d+)/);
  if (!match) return false;
  const major = Number(match[1]);
  const minor = Number(match[2]);
  return major > 0 || minor >= 8;
}

function validateSourceUrl(sourceUrl) {
  const parsed = new URL(sourceUrl);
  if (
    parsed.protocol !== "https:" ||
    parsed.hostname !== "raw.githubusercontent.com" ||
    !parsed.pathname.startsWith("/canada-ca/aia-eia-js/") ||
    !parsed.pathname.endsWith("/src/survey-enfr.json")
  ) {
    throw new Error(`Unsupported survey source URL: ${sourceUrl}`);
  }
  return parsed;
}

function download(url, redirectsRemaining = 5) {
  const parsed = validateSourceUrl(url);
  return new Promise((resolve, reject) => {
    https
      .get(parsed, response => {
        if (
          response.statusCode >= 300 &&
          response.statusCode < 400 &&
          response.headers.location
        ) {
          response.resume();
          if (redirectsRemaining === 0) {
            reject(new Error(`Too many redirects downloading ${url}`));
            return;
          }
          const redirectedUrl = new URL(response.headers.location, parsed).toString();
          download(redirectedUrl, redirectsRemaining - 1).then(resolve, reject);
          return;
        }

        if (response.statusCode < 200 || response.statusCode >= 300) {
          response.resume();
          reject(new Error(`HTTP ${response.statusCode} downloading ${url}`));
          return;
        }

        response.setEncoding("utf8");
        let body = "";
        response.on("data", chunk => {
          body += chunk;
        });
        response.on("end", () => resolve(body));
      })
      .on("error", reject);
  });
}

async function main() {
  const records = parseCsv(fs.readFileSync(manifestPath, "utf8"))
    .filter(record => record.status === "generated")
    .filter(record => isSupportedVersion(record.version));

  if (records.length === 0) {
    throw new Error("The release manifest contains no supported AIA versions.");
  }

  fs.mkdirSync(publicSurveyRoot, { recursive: true });
  const metadata = [];

  for (const record of records) {
    validateSourceUrl(record.source_url);
    const body = await download(record.source_url);
    const survey = JSON.parse(body);

    if (!survey || !Array.isArray(survey.pages)) {
      throw new Error(`Invalid SurveyJS definition for ${record.version}`);
    }

    const versionDirectory = path.join(publicSurveyRoot, record.version);
    fs.mkdirSync(versionDirectory, { recursive: true });
    fs.writeFileSync(
      path.join(versionDirectory, "survey-enfr.json"),
      `${JSON.stringify(survey)}\n`,
      "utf8"
    );

    metadata.push({
      version: record.version,
      releaseName: record.release_name,
      sourceUrl: record.source_url,
      assetPath: `surveys/${record.version}/survey-enfr.json`
    });
    process.stdout.write(`Prepared AIA questionnaire ${record.version}\n`);
  }

  fs.mkdirSync(path.dirname(generatedPath), { recursive: true });
  fs.writeFileSync(generatedPath, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
}

main().catch(error => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
