import {
  buildCorsProxyUrl,
  CORS_PROXY_BASE,
  fetchSurveyFileFromUrl,
  getSourceJsonUrl,
  parseSurveyFileText,
  validatePublicJsonUrl
} from "@/utils/remoteSurveyFile";

const savedFile = {
  version: "v1.0.1",
  currentPage: 12,
  data: { projectDetailsTitle: "Compensation Virtual Assistant" },
  translationsOnResult: {}
};

describe("remote AIA result files", () => {
  it("parses an AIA saved-result JSON document", () => {
    expect(parseSurveyFileText(JSON.stringify(savedFile))).toEqual(savedFile);
  });

  it("parses JSON returned through the text fallback", () => {
    const response = `Title: AIA results\n\nMarkdown Content:\n${JSON.stringify(
      savedFile
    )}`;
    expect(parseSurveyFileText(response)).toEqual(savedFile);
  });

  it("accepts public HTTPS URLs and rejects local URLs", () => {
    expect(
      validatePublicJsonUrl("https://open.canada.ca/example.json").hostname
    ).toBe("open.canada.ca");
    expect(() =>
      validatePublicJsonUrl("https://localhost/example.json")
    ).toThrow("public HTTPS URL");
  });

  it("loads through the configured CORS proxy", async () => {
    const proxyResponse = Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: { get: () => null },
      text: () => Promise.resolve(JSON.stringify(savedFile))
    });
    const fetchMock = jest.fn().mockReturnValueOnce(proxyResponse);
    (window as any).fetch = fetchMock;

    await expect(
      fetchSurveyFileFromUrl("https://open.canada.ca/example.json")
    ).resolves.toEqual(savedFile);
    expect(fetchMock.mock.calls[0][1].redirect).toBe("follow");
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${CORS_PROXY_BASE}https%3A%2F%2Fopen.canada.ca%2Fexample.json`
    );
  });

  it("removes the proxy prefix when presenting the source URL", () => {
    const source = "https://open.canada.ca/example.json";
    const proxied = buildCorsProxyUrl(source);

    expect(getSourceJsonUrl(proxied)).toBe(source);
    expect(buildCorsProxyUrl(proxied)).toBe(buildCorsProxyUrl(source));
  });
});
