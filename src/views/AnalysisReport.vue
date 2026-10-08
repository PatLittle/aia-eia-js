<template>
  <section class="analysis-report">
    <h1>{{ labels.title }}</h1>
    <p class="lead">{{ labels.introduction }}</p>

    <div v-if="loading" class="alert alert-info" role="status">
      {{ labels.loading }}
    </div>
    <div v-if="error" class="alert alert-danger" role="alert">
      {{ error }}
    </div>

    <div v-if="!loading && !error">
      <div class="well filters" aria-labelledby="analysis-filter-heading">
        <h2 id="analysis-filter-heading" class="h4">{{ labels.filters }}</h2>
        <div class="row">
          <div class="col-md-4">
            <label for="analysis-source">{{ labels.source }}</label>
            <select
              id="analysis-source"
              v-model="selectedSource"
              class="form-control"
              @change="renderCharts"
            >
              <option value="">{{ labels.allSources }}</option>
              <option value="published">{{ labels.published }}</option>
              <option value="recovered">{{ labels.recovered }}</option>
            </select>
          </div>
          <div class="col-md-4">
            <label for="analysis-version">{{ labels.version }}</label>
            <select
              id="analysis-version"
              v-model="selectedVersion"
              class="form-control"
              @change="renderCharts"
            >
              <option value="">{{ labels.allVersions }}</option>
              <option
                v-for="version in versions"
                :key="version"
                :value="version"
              >
                {{ version }}
              </option>
            </select>
          </div>
          <div class="col-md-4">
            <label for="analysis-organization">{{ labels.organization }}</label>
            <select
              id="analysis-organization"
              v-model="selectedOrganization"
              class="form-control"
              @change="renderCharts"
            >
              <option value="">{{ labels.allOrganizations }}</option>
              <option
                v-for="organization in organizations"
                :key="organization"
                :value="organization"
              >
                {{ organization }}
              </option>
            </select>
          </div>
        </div>
      </div>

      <div class="row metric-row" aria-live="polite">
        <div class="col-sm-6 col-md-3">
          <div class="metric-card">
            <span class="metric-value">{{ filteredRecords.length }}</span>
            <span class="metric-label">{{ labels.assessments }}</span>
          </div>
        </div>
        <div class="col-sm-6 col-md-3">
          <div class="metric-card">
            <span class="metric-value">{{ filteredPublishedCount }}</span>
            <span class="metric-label">{{ labels.published }}</span>
          </div>
        </div>
        <div class="col-sm-6 col-md-3">
          <div class="metric-card">
            <span class="metric-value">{{ filteredRecoveredCount }}</span>
            <span class="metric-label">{{ labels.recovered }}</span>
          </div>
        </div>
        <div class="col-sm-6 col-md-3">
          <div class="metric-card">
            <span class="metric-value">{{ averageCompleteness }}</span>
            <span class="metric-label">{{ labels.averageCompleteness }}</span>
          </div>
        </div>
      </div>

      <div class="row">
        <div class="col-lg-6">
          <article class="panel panel-default chart-card">
            <div class="panel-heading">
              <h2 class="h4">{{ labels.byYear }}</h2>
            </div>
            <div class="panel-body chart-wrap">
              <canvas ref="yearChart"></canvas>
            </div>
          </article>
        </div>
        <div class="col-lg-6">
          <article class="panel panel-default chart-card">
            <div class="panel-heading">
              <h2 class="h4">{{ labels.byOrganization }}</h2>
            </div>
            <div class="panel-body chart-wrap">
              <canvas ref="organizationChart"></canvas>
            </div>
          </article>
        </div>
      </div>

      <div class="row">
        <div class="col-lg-4">
          <article class="panel panel-default chart-card">
            <div class="panel-heading">
              <h2 class="h4">{{ labels.byVersion }}</h2>
            </div>
            <div class="panel-body chart-wrap">
              <canvas ref="versionChart"></canvas>
            </div>
          </article>
        </div>
        <div class="col-lg-4">
          <article class="panel panel-default chart-card">
            <div class="panel-heading">
              <h2 class="h4">{{ labels.byPhase }}</h2>
            </div>
            <div class="panel-body chart-wrap">
              <canvas ref="phaseChart"></canvas>
            </div>
          </article>
        </div>
        <div class="col-lg-4">
          <article class="panel panel-default chart-card">
            <div class="panel-heading">
              <h2 class="h4">{{ labels.bySource }}</h2>
            </div>
            <div class="panel-body chart-wrap">
              <canvas ref="sourceChart"></canvas>
            </div>
          </article>
        </div>
      </div>

      <article class="panel panel-default chart-card">
        <div class="panel-heading">
          <h2 class="h4">{{ labels.completenessByOrganization }}</h2>
        </div>
        <div class="panel-body chart-wrap chart-wrap-wide">
          <canvas ref="completenessChart"></canvas>
        </div>
      </article>

      <section
        class="data-quality-section"
        aria-labelledby="data-quality-heading"
      >
        <h2 id="data-quality-heading">{{ labels.dataQualityHeading }}</h2>
        <p>{{ labels.dataQualityExplanation }}</p>
        <div class="row">
          <div class="col-lg-6">
            <article class="panel panel-default chart-card">
              <div class="panel-heading">
                <h3 class="h4">{{ labels.biasAvailability }}</h3>
              </div>
              <div class="panel-body chart-wrap">
                <canvas ref="biasChart"></canvas>
              </div>
            </article>
          </div>
          <div class="col-lg-6">
            <article class="panel panel-default chart-card">
              <div class="panel-heading">
                <h3 class="h4">{{ labels.resolutionAvailability }}</h3>
              </div>
              <div class="panel-body chart-wrap">
                <canvas ref="resolutionChart"></canvas>
              </div>
            </article>
          </div>
        </div>
        <div class="row">
          <div class="col-lg-6">
            <article class="panel panel-default chart-card">
              <div class="panel-heading">
                <h3 class="h4">{{ labels.unreliableAvailability }}</h3>
              </div>
              <div class="panel-body chart-wrap">
                <canvas ref="unreliableChart"></canvas>
              </div>
            </article>
          </div>
          <div class="col-lg-6">
            <article class="panel panel-default chart-card">
              <div class="panel-heading">
                <h3 class="h4">{{ labels.gbaAvailability }}</h3>
              </div>
              <div class="panel-body chart-wrap">
                <canvas ref="gbaChart"></canvas>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section
        class="data-quality-section"
        aria-labelledby="model-algorithm-heading"
      >
        <h2 id="model-algorithm-heading">{{ labels.modelAlgorithmHeading }}</h2>
        <p>{{ labels.modelAlgorithmExplanation }}</p>
        <div class="model-algorithm-grid">
          <article
            v-for="definition in modelAlgorithmCharts"
            :key="definition.field"
            class="panel panel-default chart-card"
          >
            <div class="panel-heading">
              <h3 class="h4">{{ definition.title }}</h3>
            </div>
            <div class="panel-body chart-wrap">
              <canvas :ref="definition.field"></canvas>
            </div>
            <p class="panel-body small">{{ definition.choices.join("; ") }}</p>
          </article>
        </div>
      </section>

      <article
        class="panel panel-default chart-card security-card"
        aria-labelledby="security-heading"
      >
        <div class="panel-heading">
          <h2 id="security-heading" class="h3">
            {{ labels.securityQuestion }}
          </h2>
        </div>
        <div class="panel-body">
          <p>{{ labels.securityExplanation }}</p>
          <div v-if="securityAnswerCount" class="security-chart-wrap">
            <canvas
              ref="securityChart"
              role="img"
              :aria-label="labels.securityQuestion"
              aria-describedby="security-counts"
            ></canvas>
          </div>
          <p v-else role="status">{{ labels.noSecurityAnswers }}</p>
          <div id="security-counts" class="table-responsive security-counts">
            <table class="table table-condensed table-striped">
              <caption class="wb-inv">
                {{
                  labels.securityCounts
                }}
              </caption>
              <thead>
                <tr>
                  <th scope="col">{{ labels.securityClassification }}</th>
                  <th scope="col">{{ labels.assessments }}</th>
                  <th scope="col">{{ labels.shareOfAnswers }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in securityClassificationCounts"
                  :key="item.key"
                >
                  <th scope="row">
                    <span
                      class="security-swatch"
                      :style="{ backgroundColor: item.color }"
                      aria-hidden="true"
                    ></span
                    >{{ item.label }}
                  </th>
                  <td>{{ item.value }}</td>
                  <td>
                    {{
                      formatPercent((item.value / securityAnswerCount) * 100)
                    }}
                  </td>
                </tr>
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">{{ labels.totalAnswered }}</th>
                  <td>{{ securityAnswerCount }}</td>
                  <td>{{ securityAnswerCount ? "100.0%" : "—" }}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p class="small">
            {{ labels.excludedSecurityAnswers }}:
            {{ filteredRecords.length - securityAnswerCount }}
          </p>
        </div>
      </article>

      <details class="analysis-details">
        <summary>
          <strong>{{ labels.chartData }}</strong>
        </summary>
        <div class="table-responsive">
          <table class="table table-condensed table-striped">
            <thead>
              <tr>
                <th>{{ labels.assessment }}</th>
                <th>{{ labels.organization }}</th>
                <th>{{ labels.source }}</th>
                <th>{{ labels.version }}</th>
                <th>{{ labels.phase }}</th>
                <th>{{ labels.completeness }}</th>
                <th>{{ labels.nonconditionalCompleteness }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="record in filteredRecords"
                :key="'data-' + record.package_id"
              >
                <td>{{ displayTitle(record) }}</td>
                <td>{{ displayOrganization(record) }}</td>
                <td>{{ displaySource(record.source) }}</td>
                <td>{{ record.version || "—" }}</td>
                <td>{{ displayPhase(record) }}</td>
                <td>
                  {{
                    formatPercent(
                      record.derived && record.derived.completeness_pct
                    )
                  }}
                </td>
                <td>
                  {{
                    formatPercent(
                      record.derived &&
                        record.derived.nonconditional_completeness_pct
                    )
                  }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>

      <details class="analysis-details" open>
        <summary>
          <strong>{{ labels.recoveredRecords }}</strong>
        </summary>
        <p>{{ labels.recoveredExplanation }}</p>
        <div class="table-responsive">
          <table class="table table-striped table-hover">
            <thead>
              <tr>
                <th>{{ labels.assessment }}</th>
                <th>{{ labels.organization }}</th>
                <th>{{ labels.version }}</th>
                <th>{{ labels.phase }}</th>
                <th>{{ labels.completeness }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in recoveredRecords" :key="record.package_id">
                <td>
                  <a :href="record.dataset_url">{{ displayTitle(record) }}</a>
                </td>
                <td>{{ displayOrganization(record) }}</td>
                <td>{{ record.version || "—" }}</td>
                <td>{{ displayPhase(record) }}</td>
                <td>
                  {{
                    formatPercent(
                      record.derived && record.derived.completeness_pct
                    )
                  }}
                </td>
              </tr>
              <tr v-if="recoveredRecords.length === 0">
                <td colspan="5">{{ labels.noRecovered }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>

      <p class="source-note">
        {{ labels.dataSource }}
        <a :href="jsonlUrl">{{ labels.downloadJsonl }}</a> ·
        <a href="https://open.canada.ca/data/en/dataset?collection=aia"
          >Open Canada</a
        >
        ·
        <a
          href="https://github.com/PatLittle/aia-eia-js/tree/master/recovered_aia_json"
          >{{ labels.recoveredRepository }}</a
        >
      </p>
    </div>
  </section>
</template>

<script lang="ts">
import { Component, Vue } from "vue-property-decorator";

interface AiaDerived {
  project_phase?: string;
  completeness_pct?: number | null;
  nonconditional_completeness_pct?: number | null;
}

interface AiaRecord {
  package_id: string;
  title_en: string;
  title_fr: string;
  organization_en: string;
  organization_fr: string;
  metadata_created: string;
  dataset_url: string;
  source: string;
  version: string;
  data?: { [key: string]: any };
  derived?: AiaDerived;
}

interface ChartValue {
  label: string;
  value: number;
}

interface CompletenessValue {
  label: string;
  all: number;
  nonconditional: number;
}

interface DataQualityPairDefinition {
  refName: string;
  title: string;
  firstLabel: string;
  secondLabel: string;
  firstSuffixes: string[];
  secondSuffixes: string[];
  gbaPublic?: boolean;
}

interface BinaryCounts {
  firstYes: number;
  firstNo: number;
  secondYes: number;
  secondNo: number;
}

@Component
export default class AnalysisReport extends Vue {
  records: AiaRecord[] = [];
  loading = true;
  error = "";
  selectedSource = "";
  selectedVersion = "";
  selectedOrganization = "";
  charts: any[] = [];

  get jsonlUrl(): string {
    return `${process.env.BASE_URL}aia-analysis-data/aia-results.jsonl`;
  }

  get labels() {
    if (this.$i18n.locale === "fr") {
      return {
        title: "Analyse des évaluations de l’incidence algorithmique",
        securityQuestion:
          "Quelle est la classification de sécurité la plus élevée des données d’entrée utilisées par le système?",
        securityExplanation:
          "Les catégories combinées des anciens questionnaires sont conservées. Les pourcentages portent sur les réponses enregistrées et reconnues, selon les filtres sélectionnés.",
        securityCounts: "Réponses sur la classification de sécurité",
        securityClassification: "Classification de sécurité",
        shareOfAnswers: "Pourcentage des réponses",
        totalAnswered: "Total des réponses",
        excludedSecurityAnswers: "Réponses manquantes ou non reconnues exclues",
        noSecurityAnswers:
          "Aucune réponse sur la classification de sécurité pour les filtres sélectionnés.",
        modelAlgorithmHeading: "Modèle et algorithme",
        modelAlgorithmExplanation:
          "Les graphiques comptent les réponses enregistrées aux questions sur le secret commercial, le type d’algorithme, l’inférence et le type de modèle. Les questions absentes des anciennes versions et les réponses manquantes sont exclues. Plusieurs choix peuvent être comptés pour une même EIA.",
        introduction:
          "Analyse interactive des EIA publiées et des EIA reconstruites à partir de leurs PDF officiels, toutes normalisées dans le même jeu de données bilingue.",
        loading: "Chargement des données d’analyse des EIA…",
        filters: "Filtres",
        source: "Source JSON",
        version: "Version de l’EIA",
        organization: "Organisation",
        allSources: "Toutes les sources",
        allVersions: "Toutes les versions",
        allOrganizations: "Toutes les organisations",
        published: "JSON publié",
        recovered: "JSON reconstruit",
        assessments: "EIA analysées",
        averageCompleteness: "Complétude moyenne",
        byYear: "EIA par année de publication",
        byOrganization: "Organisations ayant le plus d’EIA",
        byVersion: "Versions du questionnaire",
        byPhase: "Phase du projet",
        bySource: "Source des résultats JSON",
        completenessByOrganization: "Complétude moyenne par organisation",
        dataQualityHeading: "Qualité des données et disponibilité publique",
        dataQualityExplanation:
          "Ces graphiques utilisent les champs de conception ou de mise en œuvre correspondant à la phase enregistrée dans chaque EIA. Pour l’ACS Plus, le champ de disponibilité publique est la question 6 dans les versions 0.x et la question 7 dans les versions 1.x. Seules les réponses Oui/Non enregistrées sont comptées.",
        biasAvailability: "Tests de biais et disponibilité publique",
        resolutionAvailability:
          "Résolution des problèmes de qualité et disponibilité publique",
        unreliableAvailability:
          "Gestion des données non fiables et disponibilité publique",
        gbaAvailability: "ACS Plus et disponibilité publique des résultats",
        biasProcess: "Processus de test des biais documenté",
        publicProcess: "Processus accessible au public",
        resolutionProcess: "Processus de résolution documenté",
        unreliableProcess: "Processus de gestion du risque documenté",
        gbaAnalysis: "Analyse ACS Plus entreprise",
        gbaPublic: "Résultats accessibles au public",
        yes: "Oui",
        no: "Non",
        recoveredRecords: "EIA dont le JSON a été reconstruit",
        recoveredExplanation:
          "Ces EIA n’avaient pas de ressource JSON utilisable dans le catalogue. Leurs réponses ont été reconstruites à partir des PDF anglais et français publiés.",
        assessment: "Évaluation",
        phase: "Phase",
        completeness: "Complétude",
        nonconditionalCompleteness:
          "Complétude des questions non conditionnelles",
        noRecovered:
          "Aucune EIA reconstruite ne correspond aux filtres actuels.",
        chartData: "Données des graphiques",
        dataSource: "Données :",
        downloadJsonl: "télécharger le fichier JSONL unifié",
        recoveredRepository: "JSON reconstruits dans GitHub",
        design: "Conception",
        implementation: "Mise en œuvre",
        unknown: "Inconnue",
        allQuestions: "Toutes les questions",
        nonconditional: "Questions non conditionnelles"
      };
    }
    return {
      title: "Algorithmic Impact Assessment analysis",
      securityQuestion:
        "What is the highest security classification of the input data used by the system?",
      securityExplanation:
        "Combined categories from older questionnaires are preserved. Percentages use saved, recognized answers for the selected filters.",
      securityCounts: "Security classification answers",
      securityClassification: "Security classification",
      shareOfAnswers: "Share of answers",
      totalAnswered: "Total answered",
      excludedSecurityAnswers: "Missing or unrecognized answers excluded",
      noSecurityAnswers:
        "No security classification answers for the selected filters.",
      modelAlgorithmHeading: "Model & Algorithm",
      modelAlgorithmExplanation:
        "Charts count saved answers about trade secrecy, algorithm type, inference and model type. Questions absent from older questionnaire versions and missing answers are excluded. Multiple selections can count the same AIA in more than one bar.",
      introduction:
        "Interactive analysis of published AIAs and AIAs reconstructed from their official PDFs, normalized into one bilingual dataset.",
      loading: "Loading AIA analysis data…",
      filters: "Filters",
      source: "JSON source",
      version: "AIA version",
      organization: "Organization",
      allSources: "All sources",
      allVersions: "All versions",
      allOrganizations: "All organizations",
      published: "Published JSON",
      recovered: "Recovered JSON",
      assessments: "AIAs analyzed",
      averageCompleteness: "Average completeness",
      byYear: "AIAs by publication year",
      byOrganization: "Organizations with the most AIAs",
      byVersion: "Questionnaire versions",
      byPhase: "Project phase",
      bySource: "JSON result source",
      completenessByOrganization: "Average completeness by organization",
      dataQualityHeading: "Data quality and public availability",
      dataQualityExplanation:
        "These charts use the Design or Implementation fields that match each AIA's saved project phase. For GBA Plus, the public-availability field is question 6 in v0.x surveys and question 7 in v1.x surveys. Only saved Yes/No answers are counted.",
      biasAvailability: "Bias testing and public availability",
      resolutionAvailability: "Data-quality resolution and public availability",
      unreliableAvailability:
        "Unreliable-data risk management and public availability",
      gbaAvailability: "GBA Plus analysis and public availability",
      biasProcess: "Bias-testing process documented",
      publicProcess: "Process publicly available",
      resolutionProcess: "Resolution process documented",
      unreliableProcess: "Risk-management process documented",
      gbaAnalysis: "GBA Plus analysis undertaken",
      gbaPublic: "Findings publicly available",
      yes: "Yes",
      no: "No",
      recoveredRecords: "AIAs with reconstructed JSON",
      recoveredExplanation:
        "These AIAs had no usable JSON resource in the catalogue. Their responses were reconstructed from the published English and French PDFs.",
      assessment: "Assessment",
      phase: "Phase",
      completeness: "Completeness",
      nonconditionalCompleteness: "Non-conditional question completeness",
      noRecovered: "No reconstructed AIAs match the current filters.",
      chartData: "Chart data",
      dataSource: "Data:",
      downloadJsonl: "download the unified JSONL file",
      recoveredRepository: "recovered JSON in GitHub",
      design: "Design",
      implementation: "Implementation",
      unknown: "Unknown",
      allQuestions: "All questions",
      nonconditional: "Non-conditional questions"
    };
  }

  get securityClassificationCounts() {
    const french = this.$i18n.locale === "fr";
    const definitions = [
      { key: "item1-0", en: "None", fr: "Aucun", color: "#4f6d7a" },
      { key: "item2-1", en: "Protected A", fr: "Protégé A", color: "#2b8a3e" },
      { key: "item4-3", en: "Protected B", fr: "Protégé B", color: "#1c578a" },
      { key: "item6-3", en: "Protected C", fr: "Protégé C", color: "#a05a00" },
      {
        key: "item4-3-legacy",
        en: "Protected B / Protected C",
        fr: "Protégé B / Protégé C",
        color: "#26374a"
      },
      {
        key: "item3-2",
        en: "Confidential",
        fr: "Confidentiel",
        color: "#6f42c1"
      },
      {
        key: "item3-2-legacy",
        en: "Classified / Confidential",
        fr: "Classifié / Confidentiel",
        color: "#5b5f97"
      },
      { key: "item5-4", en: "Secret", fr: "Secret", color: "#8b1e3f" },
      { key: "item7-4", en: "Top Secret", fr: "Très Secret", color: "#7a6c5d" },
      {
        key: "item5-4-legacy",
        en: "Secret / Top Secret",
        fr: "Secret / Très Secret",
        color: "#8a6d3b"
      },
      { key: "item8-0", en: "Other", fr: "Autre", color: "#287271" }
    ];
    const keys = this.filteredRecords.map(record => {
      const answer = record.data && record.data.aboutDataSource2;
      const legacy = /^v?\.?0\./.test(record.version || "");
      return legacy && ["item3-2", "item4-3", "item5-4"].includes(answer)
        ? `${answer}-legacy`
        : answer;
    });
    return definitions
      .map(item => ({
        key: item.key,
        label: french ? item.fr : item.en,
        color: item.color,
        value: keys.filter(key => key === item.key).length
      }))
      .filter(item => item.value > 0);
  }

  get securityAnswerCount(): number {
    return this.securityClassificationCounts.reduce(
      (sum, item) => sum + item.value,
      0
    );
  }

  renderSecurityChart(): void {
    if (!this.securityAnswerCount) return;
    const values = this.securityClassificationCounts;
    this.createChart("securityChart", {
      type: "pie",
      data: {
        labels: values.map(item => item.label),
        datasets: [
          {
            data: values.map(item => item.value),
            backgroundColor: values.map(item => item.color),
            borderColor: "#fff",
            borderWidth: 2
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" },
          tooltip: {
            callbacks: {
              label: (context: any) =>
                `${context.label}: ${context.raw} (${this.formatPercent(
                  (context.raw / this.securityAnswerCount) * 100
                )})`
            }
          }
        }
      }
    });
  }

  get dataQualityPairs(): DataQualityPairDefinition[] {
    return [
      {
        refName: "biasChart",
        title: this.labels.biasAvailability,
        firstLabel: this.labels.biasProcess,
        secondLabel: this.labels.publicProcess,
        firstSuffixes: ["1"],
        secondSuffixes: ["2"]
      },
      {
        refName: "resolutionChart",
        title: this.labels.resolutionAvailability,
        firstLabel: this.labels.resolutionProcess,
        secondLabel: this.labels.publicProcess,
        firstSuffixes: ["3"],
        secondSuffixes: ["4"]
      },
      {
        refName: "unreliableChart",
        title: this.labels.unreliableAvailability,
        firstLabel: this.labels.unreliableProcess,
        secondLabel: this.labels.publicProcess,
        firstSuffixes: ["8"],
        secondSuffixes: ["9"]
      },
      {
        refName: "gbaChart",
        title: this.labels.gbaAvailability,
        firstLabel: this.labels.gbaAnalysis,
        secondLabel: this.labels.gbaPublic,
        firstSuffixes: ["5"],
        secondSuffixes: [],
        gbaPublic: true
      }
    ];
  }

  get versions(): string[] {
    const values: string[] = [];
    this.records.forEach(record => {
      if (record.version && values.indexOf(record.version) === -1) {
        values.push(record.version);
      }
    });
    return values.sort();
  }

  get organizations(): string[] {
    const values: string[] = [];
    this.records.forEach(record => {
      const organization = this.displayOrganization(record);
      if (organization && values.indexOf(organization) === -1) {
        values.push(organization);
      }
    });
    return values.sort((a, b) => a.localeCompare(b));
  }

  get filteredRecords(): AiaRecord[] {
    return this.records.filter(record => {
      if (this.selectedSource && record.source !== this.selectedSource) {
        return false;
      }
      if (this.selectedVersion && record.version !== this.selectedVersion) {
        return false;
      }
      if (
        this.selectedOrganization &&
        this.displayOrganization(record) !== this.selectedOrganization
      ) {
        return false;
      }
      return true;
    });
  }

  get filteredPublishedCount(): number {
    return this.filteredRecords.filter(record => record.source === "published")
      .length;
  }

  get filteredRecoveredCount(): number {
    return this.filteredRecords.filter(record => record.source === "recovered")
      .length;
  }

  get averageCompleteness(): string {
    const values: number[] = [];
    this.filteredRecords.forEach(record => {
      const value = record.derived && record.derived.completeness_pct;
      if (typeof value === "number") values.push(value);
    });
    if (!values.length) return "—";
    const total = values.reduce((sum, value) => sum + value, 0);
    return `${(total / values.length).toFixed(1)}%`;
  }

  get recoveredRecords(): AiaRecord[] {
    return this.filteredRecords.filter(record => record.source === "recovered");
  }

  displayTitle(record: AiaRecord): string {
    return this.$i18n.locale === "fr"
      ? record.title_fr || record.title_en
      : record.title_en || record.title_fr;
  }

  displayOrganization(record: AiaRecord): string {
    return this.$i18n.locale === "fr"
      ? record.organization_fr || record.organization_en
      : record.organization_en || record.organization_fr;
  }

  displayPhase(record: AiaRecord): string {
    const phase = record.derived && record.derived.project_phase;
    if (phase === "Design") return this.labels.design;
    if (phase === "Implementation") return this.labels.implementation;
    return this.labels.unknown;
  }

  displaySource(source: string): string {
    return source === "recovered"
      ? this.labels.recovered
      : this.labels.published;
  }

  formatPercent(value?: number | null): string {
    return typeof value === "number" ? `${value.toFixed(1)}%` : "—";
  }

  countValues(values: string[], limit = 0): ChartValue[] {
    const counts: { [key: string]: number } = {};
    values.forEach(value => {
      const key = value || this.labels.unknown;
      counts[key] = (counts[key] || 0) + 1;
    });
    let entries = Object.keys(counts).map(key => ({
      label: key,
      value: counts[key]
    }));
    entries = entries.sort(
      (a, b) => b.value - a.value || a.label.localeCompare(b.label)
    );
    return limit > 0 ? entries.slice(0, limit) : entries;
  }

  averageCompletenessByOrganization(): CompletenessValue[] {
    const groups: {
      [key: string]: { total: number; nonconditional: number; count: number };
    } = {};
    this.filteredRecords.forEach(record => {
      const organization =
        this.displayOrganization(record) || this.labels.unknown;
      const all = record.derived && record.derived.completeness_pct;
      const nonconditional =
        record.derived && record.derived.nonconditional_completeness_pct;
      if (typeof all !== "number" || typeof nonconditional !== "number") {
        return;
      }
      if (!groups[organization]) {
        groups[organization] = { total: 0, nonconditional: 0, count: 0 };
      }
      groups[organization].total += all;
      groups[organization].nonconditional += nonconditional;
      groups[organization].count += 1;
    });
    return Object.keys(groups)
      .map(organization => ({
        label: organization,
        all: groups[organization].total / groups[organization].count,
        nonconditional:
          groups[organization].nonconditional / groups[organization].count
      }))
      .sort((a, b) => b.all - a.all)
      .slice(0, 12);
  }

  isSubstantive(value: any): boolean {
    if (value === null || typeof value === "undefined") return false;
    if (typeof value === "string") return value.trim().length > 0;
    if (Array.isArray(value)) return value.length > 0;
    return true;
  }

  binaryAnswer(value: any): string {
    if (!this.isSubstantive(value)) return "";
    const normalized = String(value)
      .trim()
      .toLowerCase();
    if (
      normalized === "yes" ||
      normalized === "oui" ||
      normalized.indexOf("item1") === 0
    ) {
      return "yes";
    }
    if (
      normalized === "no" ||
      normalized === "non" ||
      normalized.indexOf("item2") === 0
    ) {
      return "no";
    }
    return "";
  }

  gbaPublicSuffixes(version: string): string[] {
    const normalized = String(version || "")
      .trim()
      .toLowerCase()
      .replace(/^version\s*/, "")
      .replace(/^v\.?/, "");
    return normalized.indexOf("1.") === 0 ? ["7", "6"] : ["6", "7"];
  }

  resolveDataQualityAnswer(record: AiaRecord, suffixes: string[]): any {
    const data = record.data || {};
    const savedPhase = record.derived && record.derived.project_phase;
    const phases: string[] = [];
    if (savedPhase === "Design" || savedPhase === "Implementation") {
      phases.push(savedPhase);
    }
    ["Design", "Implementation"].forEach(phase => {
      if (phases.indexOf(phase) === -1) phases.push(phase);
    });

    for (const phase of phases) {
      for (const suffix of suffixes) {
        const fieldName = `dataQuality${phase}${suffix}`;
        if (this.isSubstantive(data[fieldName])) {
          return data[fieldName];
        }
      }
    }
    return null;
  }

  dataQualityCounts(definition: DataQualityPairDefinition): BinaryCounts {
    const counts: BinaryCounts = {
      firstYes: 0,
      firstNo: 0,
      secondYes: 0,
      secondNo: 0
    };

    this.filteredRecords.forEach(record => {
      const first = this.binaryAnswer(
        this.resolveDataQualityAnswer(record, definition.firstSuffixes)
      );
      const secondSuffixes = definition.gbaPublic
        ? this.gbaPublicSuffixes(record.version)
        : definition.secondSuffixes;
      const second = this.binaryAnswer(
        this.resolveDataQualityAnswer(record, secondSuffixes)
      );

      if (first === "yes") counts.firstYes += 1;
      if (first === "no") counts.firstNo += 1;
      if (second === "yes") counts.secondYes += 1;
      if (second === "no") counts.secondNo += 1;
    });

    return counts;
  }

  get modelAlgorithmCharts() {
    const fr = this.$i18n.locale === "fr";
    return [
      {
        field: "aboutAlgorithm1",
        title: fr
          ? "L’algorithme utilisé sera un secret (commercial)"
          : "The algorithm used will be a (trade) secret",
        choices: [this.labels.yes, this.labels.no],
        values: ["yes", "no"]
      },
      {
        field: "aboutAlgorithm3",
        title: fr
          ? "L’algorithme est (cochez toutes les réponses qui s’appliquent) :"
          : "Is the algorithm (Check all that apply):",
        choices: fr
          ? [
              "Fondé sur des règles établies en fonction des lois, des politiques ou de l’expertise humaine (p. ex. énoncés si/alors)",
              "Fondé sur des modèles de données déterminés par l’IA (p. ex. réseau neuronal, apprentissage profond)"
            ]
          : [
              "Based on rules developed from laws and policy and/or using human expertise (for example, if/then statements)",
              "Based on patterns in data identified by the AI model (for example, neural network, deep learning)"
            ],
        values: ["item1-0", "item2-1"]
      },
      {
        field: "aboutAlgorithm4",
        title: fr
          ? "Si le système est fondé sur un modèle, l’inférence du modèle est-elle (cochez toutes les réponses qui s’appliquent) :"
          : "If the automated decision-system is model based, is the model inference (select all that apply):",
        choices: fr
          ? [
              "Déterministe (suit des règles précises et produit un résultat unique)",
              "Probabiliste (explique les données en appliquant plusieurs modèles)"
            ]
          : [
              "Deterministic (follow precise rules and generate single outcome)",
              "Probabilistic (infer several models to explain data)"
            ],
        values: ["item1-0", "item2-1"]
      },
      {
        field: "aboutAlgorithm5",
        title: fr ? "Le modèle est :" : "Is the model:",
        choices: fr
          ? [
              "Discriminatif (p. ex. analyses de régression, arbres de décision)",
              "Génératif (p. ex. analyse discriminante linéaire, classification naïve bayésienne)"
            ]
          : [
              "Discriminative (for example, regression analyses, decision trees)",
              "Generative (for example, linear discriminant analysis, naïve Bayes)"
            ],
        values: ["item1-0", "item2-1"]
      }
    ];
  }

  renderModelAlgorithmCharts(palette: string[]): void {
    this.modelAlgorithmCharts.forEach(definition => {
      const counts = definition.values.map(
        value =>
          this.filteredRecords.filter(record => {
            const answer = (record.data || {})[definition.field];
            if (definition.field === "aboutAlgorithm1") {
              return this.binaryAnswer(answer) === value;
            }
            const selections = Array.isArray(answer) ? answer : [answer];
            return selections.indexOf(value) !== -1;
          }).length
      );
      this.createChart(definition.field, {
        type: "bar",
        data: {
          labels: definition.choices.map(choice => {
            const words = choice.split(" ");
            const lines: string[] = [];
            words.forEach(word => {
              const last = lines.length - 1;
              if (last < 0 || lines[last].length + word.length > 35)
                lines.push(word);
              else lines[last] += ` ${word}`;
            });
            return lines;
          }),
          datasets: [
            {
              label: this.labels.assessments,
              data: counts,
              backgroundColor: [palette[1], palette[2]]
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              ticks: { precision: 0 },
              title: { display: true, text: this.labels.assessments }
            }
          },
          plugins: { legend: { display: false } }
        }
      });
    });
  }

  async loadChartJs(): Promise<void> {
    const chartWindow: any = window;
    if (chartWindow.Chart) return;
    const existing = document.getElementById("aia-chartjs-library");
    if (existing) {
      await new Promise<void>((resolve, reject) => {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener(
          "error",
          () => reject(new Error("Chart.js failed to load")),
          { once: true }
        );
      });
      return;
    }
    await new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.id = "aia-chartjs-library";
      script.src =
        "https://cdn.jsdelivr.net/npm/chart.js@4.5.0/dist/chart.umd.min.js";
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Chart.js failed to load"));
      document.head.appendChild(script);
    });
  }

  clearCharts(): void {
    this.charts.forEach(chart => chart.destroy());
    this.charts = [];
  }

  createChart(refName: string, configuration: any): void {
    const chartWindow: any = window;
    const reference: any = this.$refs[refName];
    const canvas: any = Array.isArray(reference) ? reference[0] : reference;
    if (!canvas || !chartWindow.Chart) return;
    this.charts.push(
      new chartWindow.Chart(canvas.getContext("2d"), configuration)
    );
  }

  renderDataQualityChart(
    definition: DataQualityPairDefinition,
    palette: string[]
  ): void {
    const counts = this.dataQualityCounts(definition);
    this.createChart(definition.refName, {
      type: "bar",
      data: {
        labels: [definition.firstLabel, definition.secondLabel],
        datasets: [
          {
            label: this.labels.yes,
            data: [counts.firstYes, counts.secondYes],
            backgroundColor: palette[1]
          },
          {
            label: this.labels.no,
            data: [counts.firstNo, counts.secondNo],
            backgroundColor: palette[5]
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
            title: { display: true, text: this.labels.assessments }
          }
        },
        plugins: {
          legend: { position: "bottom" },
          title: { display: false, text: definition.title }
        }
      }
    });
  }

  async renderCharts(): Promise<void> {
    await this.$nextTick();
    const chartWindow: any = window;
    if (!chartWindow.Chart) return;
    this.clearCharts();
    const records = this.filteredRecords;
    const palette = [
      "#26374a",
      "#2b8a3e",
      "#1c578a",
      "#a05a00",
      "#6f42c1",
      "#8b1e3f",
      "#4f6d7a",
      "#7a6c5d",
      "#3c7a89",
      "#8a6d3b",
      "#5b5f97",
      "#287271"
    ];

    const years = this.countValues(
      records.map(record =>
        record.metadata_created
          ? record.metadata_created.slice(0, 4)
          : this.labels.unknown
      )
    ).sort((a, b) => a.label.localeCompare(b.label));
    this.createChart("yearChart", {
      type: "bar",
      data: {
        labels: years.map(item => item.label),
        datasets: [
          {
            label: this.labels.assessments,
            data: years.map(item => item.value),
            backgroundColor: palette[2]
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } }
      }
    });

    const organizationValues = this.countValues(
      records.map(record => this.displayOrganization(record)),
      12
    );
    this.createChart("organizationChart", {
      type: "bar",
      data: {
        labels: organizationValues.map(item => item.label),
        datasets: [
          {
            label: this.labels.assessments,
            data: organizationValues.map(item => item.value),
            backgroundColor: palette[1]
          }
        ]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } }
      }
    });

    const versionValues = this.countValues(
      records.map(record => record.version || this.labels.unknown)
    );
    this.createChart("versionChart", {
      type: "doughnut",
      data: {
        labels: versionValues.map(item => item.label),
        datasets: [
          {
            data: versionValues.map(item => item.value),
            backgroundColor: versionValues.map(
              (_item, index) => palette[index % palette.length]
            )
          }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });

    const phaseValues = this.countValues(
      records.map(record => this.displayPhase(record))
    );
    this.createChart("phaseChart", {
      type: "doughnut",
      data: {
        labels: phaseValues.map(item => item.label),
        datasets: [
          {
            data: phaseValues.map(item => item.value),
            backgroundColor: phaseValues.map(
              (_item, index) => palette[(index + 2) % palette.length]
            )
          }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });

    const sourceValues = this.countValues(
      records.map(record => this.displaySource(record.source))
    );
    this.createChart("sourceChart", {
      type: "doughnut",
      data: {
        labels: sourceValues.map(item => item.label),
        datasets: [
          {
            data: sourceValues.map(item => item.value),
            backgroundColor: [palette[2], palette[3]]
          }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });

    const completeness = this.averageCompletenessByOrganization();
    this.createChart("completenessChart", {
      type: "bar",
      data: {
        labels: completeness.map(item => item.label),
        datasets: [
          {
            label: this.labels.allQuestions,
            data: completeness.map(item => Number(item.all.toFixed(2))),
            backgroundColor: palette[0]
          },
          {
            label: this.labels.nonconditional,
            data: completeness.map(item =>
              Number(item.nonconditional.toFixed(2))
            ),
            backgroundColor: palette[1]
          }
        ]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            beginAtZero: true,
            max: 100,
            title: { display: true, text: "%" }
          }
        }
      }
    });

    this.dataQualityPairs.forEach(definition =>
      this.renderDataQualityChart(definition, palette)
    );
    this.renderModelAlgorithmCharts(palette);
    this.renderSecurityChart();
  }

  async created(): Promise<void> {
    try {
      const response = await fetch(this.jsonlUrl, { cache: "no-cache" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} ${response.statusText}`);
      }
      const text = await response.text();
      const parsed: AiaRecord[] = [];
      text.split(/\r?\n/).forEach(line => {
        if (line.trim()) parsed.push(JSON.parse(line) as AiaRecord);
      });
      this.records = parsed;
      await this.loadChartJs();
      this.loading = false;
      await this.renderCharts();
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
      this.loading = false;
    }
  }

  beforeDestroy(): void {
    this.clearCharts();
  }
}
</script>

<style scoped>
.analysis-report {
  padding-bottom: 3rem;
}

.filters {
  margin-top: 2rem;
}

.filters label {
  margin-top: 0.5rem;
}

.metric-row {
  margin-bottom: 1.5rem;
}

.metric-card {
  border: 1px solid #d6d6d6;
  border-radius: 4px;
  min-height: 9rem;
  margin-bottom: 1rem;
  padding: 1.5rem;
  background: #f8f8f8;
}

.metric-value,
.metric-label {
  display: block;
}

.metric-value {
  font-size: 2.4rem;
  line-height: 1.1;
  font-weight: 700;
}

.metric-label {
  margin-top: 0.6rem;
}

.chart-card {
  margin-bottom: 2rem;
}

.chart-wrap {
  position: relative;
  min-height: 320px;
}

.chart-wrap-wide {
  min-height: 470px;
}

.data-quality-section {
  border-top: 1px solid #ddd;
  margin-top: 2.5rem;
  padding-top: 1rem;
}

.security-card {
  margin-top: 2.5rem;
}

.security-chart-wrap {
  position: relative;
  height: 260px;
  max-width: 600px;
  margin: 0 auto 1.5rem;
}

.security-counts {
  max-width: 720px;
  margin: 0 auto;
}

.security-counts th:not(:first-child),
.security-counts td {
  text-align: right;
}

.security-swatch {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  margin-right: 0.6rem;
}

.analysis-details {
  margin: 2rem 0;
}

.model-algorithm-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2rem;
}

@media (max-width: 767px) {
  .model-algorithm-grid {
    grid-template-columns: 1fr;
  }
}

.analysis-details summary {
  cursor: pointer;
  padding: 0.75rem 0;
}

.source-note {
  border-top: 1px solid #ddd;
  margin-top: 2rem;
  padding-top: 1rem;
}
</style>
