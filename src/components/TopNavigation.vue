<template>
  <nav class="well aia-top-navigation" :aria-label="labels.navigation">
    <div class="aia-top-navigation__links">
      <router-link class="btn btn-primary" to="/CompletedAIAs">
        {{ labels.completedAias }}
      </router-link>
      <router-link class="btn btn-default" to="/AnalysisReport">
        {{ labels.analysisReport }}
      </router-link>
    </div>
    <div class="aia-top-navigation__version">
      <label for="aia-version-navigation" class="control-label">
        {{ labels.olderVersion }}
      </label>
      <select
        id="aia-version-navigation"
        class="form-control"
        :value="selectedVersion"
        @change="switchVersion"
      >
        <option :value="currentVersion">
          {{ labels.currentVersion }} ({{ currentVersion }})
        </option>
        <option
          v-for="record in availableVersions"
          :key="record.version"
          :value="record.version"
        >
          {{ record.version }} — {{ record.releaseName }}
        </option>
      </select>
    </div>
  </nav>
</template>

<script lang="ts">
import { Component, Vue } from "vue-property-decorator";
import {
  CURRENT_VERSION,
  SurveyVersionRecord,
  surveyVersions
} from "@/utils/surveyVersions";

@Component
export default class TopNavigation extends Vue {
  currentVersion = CURRENT_VERSION;
  availableVersions: SurveyVersionRecord[] = surveyVersions;

  get selectedVersion(): string {
    return String(
      this.$route.params.version || this.$store.state.version || CURRENT_VERSION
    );
  }

  get labels() {
    if (this.$i18n.locale === "fr") {
      return {
        navigation: "Navigation de l’Évaluation de l’incidence algorithmique",
        completedAias: "Charger une EIA terminée depuis les données ouvertes",
        analysisReport: "Consulter le rapport d’analyse des EIA",
        olderVersion: "Afficher une version antérieure",
        currentVersion: "Version actuelle"
      };
    }
    return {
      navigation: "Algorithmic Impact Assessment navigation",
      completedAias: "Load Completed AIA from Open Data",
      analysisReport: "View AIA analysis report",
      olderVersion: "View as older version",
      currentVersion: "Current version"
    };
  }

  switchVersion(event: Event) {
    const version = (event.target as HTMLSelectElement).value;
    const path =
      version === CURRENT_VERSION ? "/" : `/${encodeURIComponent(version)}`;
    this.$router.push({ path }).catch(() => undefined);
  }
}
</script>

<style scoped>
.aia-top-navigation {
  align-items: flex-end;
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  justify-content: space-between;
  margin-top: 1.5rem;
}

.aia-top-navigation__links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.aia-top-navigation__version {
  min-width: min(100%, 28rem);
}

.aia-top-navigation__version label {
  display: block;
}

@media (max-width: 767px) {
  .aia-top-navigation,
  .aia-top-navigation__links {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
