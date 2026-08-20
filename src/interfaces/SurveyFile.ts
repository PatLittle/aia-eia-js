export default interface SurveyFile {
  version: string;
  currentPage: number;
  data: Record<string, any>;
  translationsOnResult: Record<string, any>;
}
