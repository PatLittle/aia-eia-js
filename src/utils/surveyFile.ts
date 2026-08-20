import SurveyFile from "@/interfaces/SurveyFile";

export function normalizeSurveyFile(loadedFile: SurveyFile): SurveyFile {
  if (!loadedFile || typeof loadedFile !== "object" || !loadedFile.data) {
    throw new Error("The JSON file is not a saved AIA result.");
  }

  if ((loadedFile.data as any).aboutSystem1?.includes("item6-1")) {
    const aboutSystem = (loadedFile.data as any).aboutSystem1 as string[];
    aboutSystem[aboutSystem.indexOf("item6-1")] = "item6";
  }

  if ("impact4" in (loadedFile.data as any)) {
    const decisionAutomated = (loadedFile.data as any).impact4 as string;
    (loadedFile.data as any).decisionSector3 = decisionAutomated;
    delete (loadedFile.data as any).impact4;

    if (
      loadedFile.translationsOnResult &&
      "impact4" in (loadedFile.translationsOnResult as any)
    ) {
      const translations = loadedFile.translationsOnResult as any;
      translations.decisionSector3 = translations.impact4;
      delete translations.impact4;
    }
  }

  loadedFile.currentPage = Number(loadedFile.currentPage || 0);
  loadedFile.translationsOnResult = loadedFile.translationsOnResult || {};
  return loadedFile;
}
