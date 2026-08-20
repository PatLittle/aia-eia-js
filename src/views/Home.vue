<template>
  <div class="home">
    <h1>{{ $t("appTitle") }}</h1>
    <p>
      <a
        class="btn btn-default pull-right"
        role="button"
        :href="$t(linkProjectAnchor)"
      >
        {{ $t("linkProjectText") }}
      </a>
    </p>

    <nav class="well version-navigation" :aria-label="uiText.versionNavigation">
      <p>
        <strong>{{ uiText.questionnaireVersion }}</strong>
      </p>
      <label for="aia-version" class="control-label">
        {{ uiText.chooseVersion }}
      </label>
      <select
        id="aia-version"
        class="form-control input-md"
        :value="activeVersion"
        @change="switchVersion"
      >
        <option :value="currentVersion">
          {{ uiText.currentVersion }} ({{ currentVersion }})
        </option>
        <option
          v-for="record in availableVersions"
          :key="record.version"
          :value="record.version"
        >
          {{ record.version }} — {{ record.releaseName }}
        </option>
      </select>
      <p class="mrgn-tp-md mrgn-bttm-0">
        <a :href="analysisReportUrl">{{ uiText.analysisReport }}</a>
      </p>
    </nav>

    <div v-if="loadingMessage" class="alert alert-info" role="status">
      {{ loadingMessage }}
    </div>
    <div v-if="loadError" class="alert alert-danger" role="alert">
      <strong>{{ uiText.loadError }}</strong> {{ loadError }}
    </div>
    <div v-if="loadedJsonUrl" class="alert alert-success" role="status">
      {{ uiText.loadedJson }}
      <a :href="loadedJsonUrl">{{ loadedJsonUrl }}</a>
    </div>

    <div class="alert alert-info">
      <p class="small">{{ $t("localSaveWarning") }}</p>
    </div>

    <form>
      <ActionButtonBar
        v-on:fileLoaded="fileLoaded($event)"
        v-on:startAgain="startAgain"
        :survey="Survey"
      />
    </form>

    <DropDown :survey="Survey" :displayDropDown="allowDropdown" />
    <br />
    <AssessmentTool :survey="Survey" :key="surveyRenderKey" />
    <Score />
    <HelpModal />
  </div>
</template>

<script lang="ts">
import { Component, Vue } from "vue-property-decorator";
import * as Survey from "survey-vue";
import showdown from "showdown";
import DropDown from "@/components/DropDown.vue";
import AssessmentTool from "@/components/AssessmentTool.vue";
import Score from "@/components/Score.vue";
import ActionButtonBar from "@/components/ActionButtonBar.vue";
import HelpModal from "@/components/HelpModal.vue";
import SurveyFile from "@/interfaces/SurveyFile";
import i18n from "@/plugins/i18n";
import currentSurvey from "@/survey-enfr.json";
import { normalizeSurveyFile } from "@/utils/surveyFile";
import {
  CURRENT_VERSION,
  SurveyVersionRecord,
  findSurveyVersion,
  loadSurveyDefinition,
  surveyVersions
} from "@/utils/surveyVersions";

Survey.Serializer.addProperty("question", "help:text");

@Component({
  components: {
    AssessmentTool,
    ActionButtonBar,
    DropDown,
    Score,
    HelpModal
  }
})
export default class Home extends Vue {
  Survey: Survey.Model = new Survey.Model(currentSurvey);
  allowDropdown = false;
  activeVersion = CURRENT_VERSION;
  currentVersion = CURRENT_VERSION;
  availableVersions: SurveyVersionRecord[] = surveyVersions;
  loadingMessage = "";
  loadError = "";
  loadedJsonUrl = "";
  surveyRenderKey = 0;

  get analysisReportUrl(): string {
    return `${process.env.BASE_URL}aia_analysis_report.html`;
  }

  get uiText() {
    if (this.$i18n.locale === "fr") {
      return {
        versionNavigation: "Versions du questionnaire et rapport d’analyse",
        questionnaireVersion: `Version du questionnaire : ${this.activeVersion}`,
        chooseVersion: "Choisir une version de l’EIA",
        currentVersion: "Version actuelle",
        analysisReport: "Consulter le rapport d’analyse des EIA",
        loadingVersion: "Chargement du questionnaire…",
        loadingJson: "Chargement des résultats EIA à partir de l’URL…",
        loadError: "Impossible de charger les données demandées.",
        loadedJson: "Résultats EIA chargés depuis :"
      };
    }
    return {
      versionNavigation: "Questionnaire versions and analysis report",
      questionnaireVersion: `Questionnaire version: ${this.activeVersion}`,
      chooseVersion: "Choose an AIA version",
      currentVersion: "Current version",
      analysisReport: "View the AIA analysis report",
      loadingVersion: "Loading questionnaire…",
      loadingJson: "Loading AIA results from the URL…",
      loadError: "The requested data could not be loaded.",
      loadedJson: "AIA results loaded from:"
    };
  }

  startAgain() {
    this.Survey.clear(true, true);
    window.localStorage.clear();
    this.$store.commit("resetSurvey");
    this.allowDropdown = false;
  }

  fileLoaded(event: SurveyFile) {
    const loadedFile = normalizeSurveyFile(event);
    this.$store.commit(
      "setSurveyVersion",
      loadedFile.version || this.activeVersion
    );
    this.Survey.version = loadedFile.version || this.activeVersion;
    this.Survey.data = loadedFile.data;
    this.Survey.currentPageNo = loadedFile.currentPage;
    this.Survey.translationsOnResult = loadedFile.translationsOnResult;
    this.Survey.start();
    this.$store.commit("updateResult", this.Survey);
    this.allowDropdown =
      this.Survey.getValue("projectDetailsPhase") !== undefined;
  }

  switchVersion(event: Event) {
    const version = (event.target as HTMLSelectElement).value;
    const path =
      version === CURRENT_VERSION ? "/" : `/${encodeURIComponent(version)}`;
    this.$router.push({ path }).catch(() => undefined);
    this.loadVersion(version, true).catch(error => {
      this.loadError = error instanceof Error ? error.message : String(error);
    });
  }

  private async loadVersion(version: string, clearExisting: boolean) {
    this.loadingMessage = this.uiText.loadingVersion;
    this.loadError = "";
    const loaded = await loadSurveyDefinition(version);
    const model = new Survey.Model(loaded.definition);
    this.configureSurvey(model);
    this.Survey = model;
    this.activeVersion = loaded.version;
    this.surveyRenderKey += 1;

    if (clearExisting) this.$store.commit("resetSurvey");
    this.$store.commit("setSurveyVersion", loaded.version);
    this.loadingMessage = "";
  }

  private routeVersion(): string {
    return String(this.$route.params.version || "").trim();
  }

  private queryJsonUrl(): string {
    const value = this.$route.query.json;
    if (Array.isArray(value)) return String(value[0] || "");
    return String(value || "");
  }

  private validatePublicJsonUrl(value: string): URL {
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

  private async fetchJsonText(url: string): Promise<string> {
    const response = await fetch(url, {
      redirect: "follow",
      headers: { Accept: "application/json" }
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    const contentLength = Number(response.headers.get("content-length") || 0);
    if (contentLength > 10 * 1024 * 1024) {
      throw new Error("The JSON file is larger than 10 MB.");
    }
    const text = await response.text();
    if (text.length > 10 * 1024 * 1024) {
      throw new Error("The JSON file is larger than 10 MB.");
    }
    return text;
  }

  private async fetchSurveyFile(value: string): Promise<SurveyFile> {
    const url = this.validatePublicJsonUrl(value);
    const directUrl = url.toString();
    const candidates = [
      directUrl,
      `https://r.jina.ai/${directUrl}`,
      `https://api.allorigins.win/raw?url=${encodeURIComponent(directUrl)}`
    ];
    let lastError: unknown;

    for (const candidate of candidates) {
      try {
        const text = await this.fetchJsonText(candidate);
        const markdownMarker = "Markdown Content:";
        const jsonText = text.includes(markdownMarker)
          ? text
              .substring(text.indexOf(markdownMarker) + markdownMarker.length)
              .trim()
          : text;
        return normalizeSurveyFile(JSON.parse(jsonText) as SurveyFile);
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError || new Error("Unable to download the AIA JSON file.");
  }

  private async initializeFromUrl() {
    const jsonUrl = this.queryJsonUrl();
    let loadedFile: SurveyFile | undefined;
    let requestedVersion = this.routeVersion();

    try {
      if (jsonUrl) {
        this.loadingMessage = this.uiText.loadingJson;
        loadedFile = await this.fetchSurveyFile(jsonUrl);
        requestedVersion = loadedFile.version || requestedVersion;
      }

      if (requestedVersion) {
        const record = findSurveyVersion(requestedVersion);
        if (!record && requestedVersion !== CURRENT_VERSION) {
          throw new Error(
            `Unsupported AIA questionnaire version: ${requestedVersion}`
          );
        }
        await this.loadVersion(requestedVersion, true);
      }

      if (loadedFile) {
        this.fileLoaded(loadedFile);
        this.loadedJsonUrl = jsonUrl;
      } else if (
        this.$store.getters.inProgress &&
        this.$store.state.version === this.activeVersion
      ) {
        this.fileLoaded({
          version: this.$store.state.version,
          currentPage: this.$store.state.currentPageNo,
          data: this.$store.state.toolData,
          translationsOnResult: this.$store.state.translationsOnResult
        } as SurveyFile);
      }
    } catch (error) {
      this.loadError = error instanceof Error ? error.message : String(error);
    } finally {
      this.loadingMessage = "";
    }
  }

  private configureSurvey(model: Survey.Model) {
    model.onAfterRenderQuestion.add(result => {
      this.$store.commit("updateResult", result);
    });

    model.onComplete.add(result => {
      this.$store.commit("updateResult", result);
      this.$router.push({ path: "/Results" }).catch(() => undefined);
    });

    model.onAfterRenderPage.add(result => {
      const progressBar = document.getElementsByClassName("progress-bar")[0] as
        | HTMLElement
        | undefined;
      if (progressBar) {
        progressBar.innerHTML =
          result.currentPageNo === 0
            ? `Page 1 ${this.$t("pageProgressBar")}`
            : `Page ${result.currentPageNo + 1}${this.$t("pageProgressBar")}`;
      }
      if (model.getValue("projectDetailsPhase") !== undefined) {
        this.allowDropdown = true;
      }
    });

    model.onValueChanged.add(result => {
      this.$store.commit("updateResult", result);
      if (model.getValue("projectDetailsPhase") !== undefined) {
        this.allowDropdown = true;
      }
    });

    const converter = new showdown.Converter();
    model.onTextMarkdown.add((survey, options) => {
      let markdownHtml = converter.makeHtml(options.text);
      if (markdownHtml.startsWith("<p>") && markdownHtml.endsWith("</p>")) {
        markdownHtml = markdownHtml.substring(3, markdownHtml.length - 4);
      }
      options.html = markdownHtml;
    });

    model.locale = i18n.locale;
    model.requiredText = "";

    model.onAfterRenderQuestion.add((sender, options) => {
      const title = options.htmlElement.getElementsByTagName("H5")[0];
      if (!title) return;

      let requiredHtml = "";
      let helpButton = "";
      if (options.question.isRequired) {
        const requiredText =
          sender.locale === "fr" ? "obligatoire" : "required";
        requiredHtml = ` <strong class="required">(${requiredText})</strong>`;
      }

      if (options.question.help) {
        let helpText =
          sender.locale === "fr"
            ? String(options.question.help.fr)
            : String(options.question.help.default);
        helpText = helpText
          .replace(/&/g, "&amp;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "ooooo")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/\(/g, "&#40;")
          .replace(/\)/g, "&#41;");
        const showHelpText = this.$t("showHelp").toString();
        const iconUrl = `${process.env.BASE_URL}img/icons/show-help.png`;
        helpButton =
          ` <a role="button" onclick="showHelp('${helpText}')">` +
          `<img src="${iconUrl}" alt="${showHelpText}"></a>`;
      }

      title.outerHTML =
        `<label for="${options.question.inputId}" class="${title.className}">` +
        `<span class="field-name">${title.innerText}</span>${requiredHtml}` +
        `</label>${helpButton}`;
    });
  }

  created() {
    this.configureSurvey(this.Survey);
    this.initializeFromUrl();
  }
}
</script>

<style scoped>
.version-navigation {
  clear: both;
  margin-top: 1.5rem;
}

.version-navigation select {
  max-width: 44rem;
}
</style>
