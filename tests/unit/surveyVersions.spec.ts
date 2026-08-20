import {
  CURRENT_VERSION,
  findSurveyVersion,
  isCurrentVersion,
  surveyVersions
} from "@/utils/surveyVersions";
import { normalizeSurveyFile } from "@/utils/surveyFile";

describe("versioned AIA questionnaires", () => {
  it("exposes only the 0.8-and-later historical releases", () => {
    expect(surveyVersions.map(record => record.version)).toEqual([
      "v1.0.0",
      "v0.10.0",
      "v0.9.1",
      "v.0.8a1"
    ]);
  });

  it("matches version aliases used by saved AIA files", () => {
    expect(findSurveyVersion("0.10.0")?.version).toBe("v0.10.0");
    expect(findSurveyVersion("v0.8")?.version).toBe("v.0.8a1");
    expect(findSurveyVersion("v0.9")?.version).toBe("v0.9.1");
    expect(findSurveyVersion("v.0.8a1")?.version).toBe("v.0.8a1");
    expect(isCurrentVersion(CURRENT_VERSION)).toBe(true);
  });

  it("normalizes legacy saved-result fields", () => {
    const result = normalizeSurveyFile({
      version: "v0.9.1",
      currentPage: 2,
      data: { aboutSystem1: ["item6-1"], impact4: "Description" },
      translationsOnResult: { impact4: "Description française" }
    });

    expect(result.data.aboutSystem1).toEqual(["item6"]);
    expect(result.data.decisionSector3).toBe("Description");
    expect(result.translationsOnResult.decisionSector3).toBe(
      "Description française"
    );
  });
});
