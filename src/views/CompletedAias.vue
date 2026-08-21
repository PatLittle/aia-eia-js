<template>
  <section>
    <h1>{{ labels.title }}</h1>
    <p>{{ labels.introduction }}</p>

    <div class="form-group">
      <label for="completed-aia-filter" class="control-label">
        {{ labels.filter }}
      </label>
      <input
        id="completed-aia-filter"
        v-model="filter"
        type="search"
        class="form-control"
      />
    </div>

    <div v-if="loading" class="alert alert-info" role="status">
      {{ labels.loading }}
    </div>
    <div v-if="error" class="alert alert-danger" role="alert">
      {{ error }}
    </div>

    <div v-if="!loading && !error" class="table-responsive">
      <table class="table table-striped table-hover">
        <thead>
          <tr>
            <th>{{ labels.assessment }}</th>
            <th>{{ labels.organization }}</th>
            <th>{{ labels.publishedDate }}</th>
            <th>{{ labels.version }}</th>
            <th>{{ labels.impactLevel }}</th>
            <th>{{ labels.source }}</th>
            <th>{{ labels.action }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="assessment in filteredAssessments"
            :key="assessment.package_id"
          >
            <td>
              <a :href="assessment.dataset_url">{{ displayTitle(assessment) }}</a>
            </td>
            <td>{{ displayOrganization(assessment) }}</td>
            <td>{{ formatDate(assessment.publication_date) }}</td>
            <td>{{ assessment.aia_version || "—" }}</td>
            <td>{{ assessment.impact_level || "—" }}</td>
            <td>{{ displaySource(assessment.source) }}</td>
            <td>
              <router-link
                class="btn btn-primary btn-sm"
                :to="{
                  path: '/Results',
                  query: { json: assessment.resource_url }
                }"
              >
                {{ labels.loadResults }}
              </router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="filteredAssessments.length === 0" class="alert alert-warning">
        {{ labels.noMatches }}
      </p>
    </div>

    <p>
      <a :href="sourceJsonlUrl">{{ labels.sourceData }}</a>
    </p>
  </section>
</template>

<script lang="ts">
import { Component, Vue } from "vue-property-decorator";

interface CompletedAia {
  package_id: string;
  title_en: string;
  title_fr: string;
  organization_en: string;
  organization_fr: string;
  publication_date: string;
  aia_version: string;
  impact_level: string;
  dataset_url: string;
  resource_url: string;
  source: string;
}

@Component
export default class CompletedAias extends Vue {
  assessments: CompletedAia[] = [];
  filter = "";
  loading = true;
  error = "";

  get sourceJsonlUrl(): string {
    return `${process.env.BASE_URL}aia-analysis-data/aia-results.jsonl`;
  }

  get filteredAssessments(): CompletedAia[] {
    const query = this.filter.trim().toLowerCase();
    if (!query) return this.assessments;
    return this.assessments.filter(assessment =>
      `${assessment.title_en} ${assessment.title_fr} ${assessment.organization_en} ${assessment.organization_fr} ${assessment.aia_version} ${assessment.source}`
        .toLowerCase()
        .includes(query)
    );
  }

  get labels() {
    if (this.$i18n.locale === "fr") {
      return {
        title: "Charger une EIA terminée depuis les données ouvertes",
        introduction:
          "Sélectionnez une EIA publiée ou reconstruite pour afficher ses résultats dans l’outil.",
        filter: "Filtrer les EIA",
        loading: "Chargement des EIA…",
        assessment: "Évaluation",
        organization: "Organisation",
        publishedDate: "Publication",
        version: "Version",
        impactLevel: "Niveau d’incidence",
        source: "Source JSON",
        publishedJson: "JSON publié",
        recoveredJson: "JSON reconstruit",
        action: "Résultats",
        loadResults: "Charger les résultats",
        noMatches: "Aucune EIA ne correspond au filtre.",
        sourceData: "Télécharger le jeu de données JSONL unifié"
      };
    }
    return {
      title: "Load Completed AIA from Open Data",
      introduction:
        "Select a published or reconstructed AIA to display its completed results in this application.",
      filter: "Filter AIAs",
      loading: "Loading AIAs…",
      assessment: "Assessment",
      organization: "Organization",
      publishedDate: "Published",
      version: "Version",
      impactLevel: "Impact level",
      source: "JSON source",
      publishedJson: "Published JSON",
      recoveredJson: "Recovered JSON",
      action: "Results",
      loadResults: "Load results",
      noMatches: "No AIAs match the filter.",
      sourceData: "Download the unified JSONL dataset"
    };
  }

  displayTitle(assessment: CompletedAia): string {
    return this.$i18n.locale === "fr"
      ? assessment.title_fr || assessment.title_en
      : assessment.title_en || assessment.title_fr;
  }

  displayOrganization(assessment: CompletedAia): string {
    return this.$i18n.locale === "fr"
      ? assessment.organization_fr || assessment.organization_en
      : assessment.organization_en || assessment.organization_fr;
  }

  displaySource(source: string): string {
    return source === "recovered"
      ? this.labels.recoveredJson
      : this.labels.publishedJson;
  }

  formatDate(value: string): string {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return value || "—";
    return new Intl.DateTimeFormat(
      this.$i18n.locale === "fr" ? "fr-CA" : "en-CA",
      { year: "numeric", month: "short", day: "numeric" }
    ).format(date);
  }

  async created() {
    try {
      const response = await fetch(
        `${process.env.BASE_URL}aia-analysis-data/completed-aias.json`,
        { cache: "no-cache" }
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }
      this.assessments = (await response.json()) as CompletedAia[];
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
    } finally {
      this.loading = false;
    }
  }
}
</script>
