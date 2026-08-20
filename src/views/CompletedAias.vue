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
            <th>{{ labels.published }}</th>
            <th>{{ labels.version }}</th>
            <th>{{ labels.impactLevel }}</th>
            <th>{{ labels.action }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="assessment in filteredAssessments"
            :key="assessment.package_id"
          >
            <td>
              <a :href="assessment.dataset_url">{{ assessment.title }}</a>
            </td>
            <td>{{ assessment.organization }}</td>
            <td>{{ formatDate(assessment.publication_date) }}</td>
            <td>{{ assessment.aia_version || "—" }}</td>
            <td>{{ assessment.impact_level || "—" }}</td>
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
      <a :href="sourceCsvUrl">{{ labels.source }}</a>
    </p>
  </section>
</template>

<script lang="ts">
import { Component, Vue } from "vue-property-decorator";

interface CompletedAia {
  package_id: string;
  title: string;
  organization: string;
  publication_date: string;
  aia_version: string;
  impact_level: string;
  dataset_url: string;
  resource_url: string;
}

@Component
export default class CompletedAias extends Vue {
  assessments: CompletedAia[] = [];
  filter = "";
  loading = true;
  error = "";

  get sourceCsvUrl(): string {
    return `${process.env.BASE_URL}aia-analysis-data/aia_report_assessments.csv`;
  }

  get filteredAssessments(): CompletedAia[] {
    const query = this.filter.trim().toLowerCase();
    if (!query) return this.assessments;
    return this.assessments.filter(assessment =>
      `${assessment.title} ${assessment.organization} ${assessment.aia_version}`
        .toLowerCase()
        .includes(query)
    );
  }

  get labels() {
    if (this.$i18n.locale === "fr") {
      return {
        title: "Charger une EIA terminée depuis les données ouvertes",
        introduction:
          "Sélectionnez une EIA publiée pour afficher ses résultats dans l’outil.",
        filter: "Filtrer les EIA",
        loading: "Chargement des EIA publiées…",
        assessment: "Évaluation",
        organization: "Organisation",
        published: "Publication",
        version: "Version",
        impactLevel: "Niveau d’incidence",
        action: "Résultats",
        loadResults: "Charger les résultats",
        noMatches: "Aucune EIA ne correspond au filtre.",
        source: "Télécharger les données sources sur les EIA"
      };
    }
    return {
      title: "Load Completed AIA from Open Data",
      introduction:
        "Select a published AIA to display its completed results in this application.",
      filter: "Filter AIAs",
      loading: "Loading published AIAs…",
      assessment: "Assessment",
      organization: "Organization",
      published: "Published",
      version: "Version",
      impactLevel: "Impact level",
      action: "Results",
      loadResults: "Load results",
      noMatches: "No AIAs match the filter.",
      source: "Download the source AIA assessment data"
    };
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
