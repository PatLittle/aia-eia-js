<template>
  <section>
    <div v-if="loading" class="alert alert-info" role="status">
      {{ loadingMessage }}
    </div>
    <div v-if="error" class="alert alert-danger" role="alert">
      {{ error }}
    </div>
    <div v-if="content" v-html="content"></div>
  </section>
</template>

<script lang="ts">
import { Component, Vue } from "vue-property-decorator";

@Component
export default class AnalysisReport extends Vue {
  content = "";
  error = "";
  loading = true;

  get loadingMessage(): string {
    return this.$i18n.locale === "fr"
      ? "Chargement du rapport d’analyse des EIA…"
      : "Loading the AIA analysis report…";
  }

  async created() {
    try {
      const response = await fetch(
        `${process.env.BASE_URL}aia-analysis-data/aia-analysis-report-content.html`,
        { cache: "no-cache" }
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }
      this.content = await response.text();
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
    } finally {
      this.loading = false;
    }
  }
}
</script>
