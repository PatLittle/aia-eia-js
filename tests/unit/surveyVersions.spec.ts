import {
  CURRENT_VERSION,
  findSurveyVersion,
  isCurrentVersion,
  surveyVersions
} from "@/utils/surveyVersions";
import { Model } from "survey-vue";
import { hydrateSurveyModel, normalizeSurveyFile } from "@/utils/surveyFile";
import currentSurvey from "@/survey-enfr.json";
import store from "@/store";

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

  it("hydrates a survey model before it is rendered", () => {
    const model = new Model({
      pages: [
        {
          elements: [{ type: "text", name: "projectDetailsTitle" }]
        }
      ]
    });

    hydrateSurveyModel(model, {
      version: CURRENT_VERSION,
      currentPage: 0,
      data: { projectDetailsTitle: "Compensation Virtual Assistant" },
      translationsOnResult: { projectDetailsTitle: "Assistant virtuel" }
    });

    expect(model.getValue("projectDetailsTitle")).toBe(
      "Compensation Virtual Assistant"
    );
    expect(model.translationsOnResult.projectDetailsTitle).toBe(
      "Assistant virtuel"
    );
  });

  it("produces populated result sections from saved AIA answers", () => {
    const model = new Model(currentSurvey);
    hydrateSurveyModel(model, {
      version: CURRENT_VERSION,
      currentPage: 12,
      data: {
        projectAIAnumber: "1",
        projectDetailsTitle: "Compensation Virtual Assistant",
        projectDetailsPhase: "item2",
        riskProfile1: "item1-3",
        privacyImplementation1: "item1-2"
      },
      translationsOnResult: {}
    });

    store.commit("resetSurvey");
    store.commit("setSurveyVersion", CURRENT_VERSION);
    store.commit("updateResult", model);

    expect(store.state.toolData.projectDetailsTitle).toBe(
      "Compensation Virtual Assistant"
    );
    expect(store.getters.calcScore[0]).toBeGreaterThan(0);
    expect(
      store.getters.resultDataSections[0].some(
        (result: any) => result.name === "projectDetailsTitle"
      )
    ).toBe(true);
  });
});
