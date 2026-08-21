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
import { Component, Vue, Watch } from "vue-property-decorator";
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
import { hydrateSurveyModel, normalizeSurveyFile } from "@/utils/surveyFile";
import {
  fetchSurveyFileFromUrl,
  getSourceJsonUrl
} from "@/utils/remoteSurveyFile";
import {
  CURRENT_VERSION,
  findSurveyVersion,
  loadSurveyDefinition
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
  loadingMessage = "";
  loadError = "";
  loadedJsonUrl = "";
  surveyRenderKey = 0;

  get uiText() {
    if (this.$i18n.locale === "fr") {
      return {
        loadingVersion: "Chargement du questionnaire…",
        loadingJson: "Chargement des résultats EIA à partir de l’URL…",
        loadError: "Impossible de charger les données demandées.",
        loadedJson: "Résultats EIA chargés depuis :"
      };
    }
    return {
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
    loadedFile.version = loadedFile.version || this.activeVersion;
    hydrateSurveyModel(this.Survey, loadedFile);
    this.$store.commit("updateResult", this.Survey);
    this.surveyRenderKey += 1;
    this.allowDropdown =
      this.Survey.getValue("projectDetailsPhase") !== undefined;
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

  private async initializeFromUrl() {
    const jsonUrl = this.queryJsonUrl();
    let loadedFile: SurveyFile | undefined;
    let requestedVersion = this.routeVersion();

    try {
      if (jsonUrl) {
        this.loadingMessage = this.uiText.loadingJson;
        loadedFile = await fetchSurveyFileFromUrl(jsonUrl);
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
        this.loadedJsonUrl = getSourceJsonUrl(jsonUrl);
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

  @Watch("$route.params.version")
  onRouteVersionChanged() {
    const version = this.routeVersion() || CURRENT_VERSION;
    this.loadVersion(version, true).catch(error => {
      this.loadError = error instanceof Error ? error.message : String(error);
    });
  }

  created() {
    this.configureSurvey(this.Survey);
    this.initializeFromUrl();
  }
}
</script>
