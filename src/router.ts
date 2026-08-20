import Vue from "vue";
import Router from "vue-router";
import Results from "./views/Results.vue";
import Home from "./views/Home.vue";
import CompletedAias from "./views/CompletedAias.vue";
import AnalysisReport from "./views/AnalysisReport.vue";

Vue.use(Router);

export default new Router({
  mode: "history",
  base: process.env.BASE_URL,
  routes: [
    {
      path: "/",
      name: "home",
      component: Home
    },
    {
      path: "/Results",
      name: "results",
      component: Results
    },
    {
      path: "/CompletedAIAs",
      name: "completed-aias",
      component: CompletedAias
    },
    {
      path: "/AnalysisReport",
      name: "analysis-report",
      component: AnalysisReport
    },
    {
      path: "/version/:version",
      alias: "/:version",
      name: "versioned-home",
      component: Home
    }
  ]
});
