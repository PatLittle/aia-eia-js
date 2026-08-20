import SurveyFile from "@/interfaces/SurveyFile";
import { normalizeSurveyFile } from "@/utils/surveyFile";

const MAX_JSON_BYTES = 10 * 1024 * 1024;

export function validatePublicJsonUrl(value: string): URL {
  const url = new URL(value);
  const hostname = url.hostname.toLowerCase();
  const isPrivateIpv4 =
    /^(10\.|127\.|169\.254\.|192\.168\.)/.test(hostname) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(hostname);
  const isLocal =
    hostname === "localhost" ||
    hostname === "[::1]" ||
    hostname.endsWith(".local");

  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    isPrivateIpv4 ||
    isLocal
  ) {
    throw new Error("The json parameter must be a public HTTPS URL.");
  }
  return url;
}

async function fetchJsonText(url: string): Promise<string> {
  const response = await fetch(url, {
    redirect: "follow",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`);
  }
  const contentLength = Number(response.headers.get("content-length") || 0);
  if (contentLength > MAX_JSON_BYTES) {
    throw new Error("The JSON file is larger than 10 MB.");
  }
  const text = await response.text();
  if (text.length > MAX_JSON_BYTES) {
    throw new Error("The JSON file is larger than 10 MB.");
  }
  return text;
}

export function parseSurveyFileText(text: string): SurveyFile {
  const markdownMarker = "Markdown Content:";
  const jsonText = text.includes(markdownMarker)
    ? text
        .substring(text.indexOf(markdownMarker) + markdownMarker.length)
        .trim()
    : text;
  return normalizeSurveyFile(JSON.parse(jsonText) as SurveyFile);
}

export async function fetchSurveyFileFromUrl(
  value: string
): Promise<SurveyFile> {
  const directUrl = validatePublicJsonUrl(value).toString();
  const candidates = [
    directUrl,
    `https://r.jina.ai/${directUrl}`,
    `https://api.allorigins.win/raw?url=${encodeURIComponent(directUrl)}`
  ];
  let lastError: unknown;

  for (const candidate of candidates) {
    try {
      return parseSurveyFileText(await fetchJsonText(candidate));
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error("Unable to download the AIA JSON file.");
}
