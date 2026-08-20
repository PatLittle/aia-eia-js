import {
  fetchSurveyFileFromUrl,
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

  it("follows redirects and uses the text fallback when direct CORS fails", async () => {
    const directFailure = Promise.reject(new TypeError("Failed to fetch"));
    const fallbackResponse = Promise.resolve({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: { get: () => null },
      text: () =>
        Promise.resolve(`Markdown Content:\n${JSON.stringify(savedFile)}`)
    });
    const fetchMock = jest
      .fn()
      .mockReturnValueOnce(directFailure)
      .mockReturnValueOnce(fallbackResponse);
    (window as any).fetch = fetchMock;

    await expect(
      fetchSurveyFileFromUrl("https://open.canada.ca/example.json")
    ).resolves.toEqual(savedFile);
    expect(fetchMock.mock.calls[0][1].redirect).toBe("follow");
    expect(fetchMock.mock.calls[1][0]).toBe(
      "https://r.jina.ai/https://open.canada.ca/example.json"
    );
  });
});
