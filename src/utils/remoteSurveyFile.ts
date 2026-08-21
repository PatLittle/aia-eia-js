import SurveyFile from "@/interfaces/SurveyFile";
import { normalizeSurveyFile } from "@/utils/surveyFile";

const MAX_JSON_BYTES = 10 * 1024 * 1024;
export const CORS_PROXY_BASE =
  "https://lovely-nasturtium-97f019.netlify.app/cors-proxy?url=";

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

export function getSourceJsonUrl(value: string): string {
  const suppliedUrl = validatePublicJsonUrl(value);
  const proxyUrl = new URL(CORS_PROXY_BASE);

  if (
    suppliedUrl.origin === proxyUrl.origin &&
    suppliedUrl.pathname === proxyUrl.pathname
  ) {
    const sourceUrl = suppliedUrl.searchParams.get("url");
    if (!sourceUrl) {
      throw new Error("The CORS proxy URL does not contain a source URL.");
    }
    return validatePublicJsonUrl(sourceUrl).toString();
  }

  return suppliedUrl.toString();
}

export function buildCorsProxyUrl(value: string): string {
  return `${CORS_PROXY_BASE}${encodeURIComponent(getSourceJsonUrl(value))}`;
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
  return parseSurveyFileText(await fetchJsonText(buildCorsProxyUrl(value)));
}
