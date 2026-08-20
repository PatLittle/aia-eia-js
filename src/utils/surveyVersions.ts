import currentSurvey from "@/survey-enfr.json";
import versionRecords from "@/generated/surveyVersions.json";

export const CURRENT_VERSION = "v1.0.1";

export interface SurveyVersionRecord {
  version: string;
  releaseName: string;
  sourceUrl: string;
  assetPath: string;
}

export const surveyVersions = versionRecords as SurveyVersionRecord[];

function comparableVersion(value: string): string {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/^v\.?/, "")
    .replace(/[^0-9a-z]/g, "");
}

export function findSurveyVersion(
  requestedVersion?: string | null
): SurveyVersionRecord | undefined {
  const requested = String(requestedVersion || "")
    .trim()
    .toLowerCase();
  const versionAliases = new Map<string, string>([
    ["0.8", "v.0.8a1"],
    ["v0.8", "v.0.8a1"],
    ["0.9", "v0.9.1"],
    ["v0.9", "v0.9.1"],
    ["0.10", "v0.10.0"],
    ["v0.10", "v0.10.0"],
    ["1.0", "v1.0.0"],
    ["v1.0", "v1.0.0"]
  ]);
  const comparable = comparableVersion(
    versionAliases.get(requested) || requested
  );
  return surveyVersions.find(
    record => comparableVersion(record.version) === comparable
  );
}

export function isCurrentVersion(version?: string | null): boolean {
  const comparable = comparableVersion(version || "");
  return comparable === "" || comparable === comparableVersion(CURRENT_VERSION);
}

export async function loadSurveyDefinition(
  requestedVersion?: string | null
): Promise<{ definition: any; version: string }> {
  if (isCurrentVersion(requestedVersion)) {
    return { definition: currentSurvey, version: CURRENT_VERSION };
  }

  const record = findSurveyVersion(requestedVersion);
  if (!record) {
    throw new Error(
      `Unsupported AIA questionnaire version: ${requestedVersion}`
    );
  }

  const response = await fetch(`${process.env.BASE_URL}${record.assetPath}`, {
    cache: "no-cache",
    redirect: "follow"
  });
  if (!response.ok) {
    throw new Error(
      `Could not load AIA questionnaire ${record.version} (HTTP ${response.status}).`
    );
  }

  return { definition: await response.json(), version: record.version };
}
