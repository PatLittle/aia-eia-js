import Vuex from "vuex";
import { createLocalVue, shallowMount } from "@vue/test-utils";
import Results from "@/views/Results.vue";
import Obligations from "@/components/Obligations.vue";
import i18n from "@/plugins/i18n";
import store from "@/store";

const localVue = createLocalVue();
localVue.use(Vuex);

const savedLegacyAia = {
  version: "v0.10.0",
  currentPage: 1,
  data: {
    projectDetailsTitle: "Legacy AIA project",
    "riskQuestion-RS": "item1-3"
  },
  translationsOnResult: {}
};

const legacySurvey = {
  pages: [
    {
      name: "projectDetails-NS",
      elements: [
        {
          type: "panel",
          name: "projectDetailsPanel-NS",
          elements: [{ type: "text", name: "projectDetailsTitle" }]
        }
      ]
    },
    {
      name: "risk-RS",
      elements: [
        {
          type: "panel",
          name: "riskPanel-RS",
          elements: [
            {
              type: "radiogroup",
              name: "riskQuestion-RS",
              choices: ["item1-0", "item1-3"]
            }
          ]
        }
      ]
    }
  ]
};

function responseWithText(value: unknown) {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    headers: { get: () => null },
    text: () => Promise.resolve(JSON.stringify(value))
  };
}

async function flushAsyncWork() {
  await new Promise(resolve => setTimeout(resolve, 0));
  await localVue.nextTick();
}

describe("remote result rendering", () => {
  beforeEach(() => {
    store.commit("resetSurvey");
    store.commit("setSurveyVersion", "v1.0.1");
  });

  it("waits for and reactively renders a historical result model", async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce(responseWithText(savedLegacyAia))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        statusText: "OK",
        json: () => Promise.resolve(legacySurvey)
      });
    (window as any).fetch = fetchMock;

    const wrapper = shallowMount(Results, {
      localVue,
      store,
      i18n,
      mocks: {
        $route: {
          query: { json: "https://open.canada.ca/legacy-aia.json" }
        },
        $router: { push: jest.fn(() => Promise.resolve()) }
      },
      stubs: { "b-table": true }
    });
    const view = wrapper.vm as any;

    expect(view.resultsReady).toBe(false);
    await flushAsyncWork();
    await flushAsyncWork();

    expect(store.state.version).toBe("v0.10.0");
    expect(view.displayVersion).toBe("0.10.0");
    expect(view.resultsReady).toBe(true);
    expect(view.myResults[0]).toHaveLength(1);
    expect(view.myResults[1]).toHaveLength(1);
    expect(store.getters.calcScore[0]).toBe(3);
  });

  it("renders obligations safely before a result exists", () => {
    const wrapper = shallowMount(Obligations, {
      localVue,
      store,
      i18n,
      stubs: { ListItem: true }
    });

    expect((wrapper.vm as any).impactLevel).toBe(1);
    expect(wrapper.text()).toContain("Requirements Specific to Impact Level 1");
  });
});
