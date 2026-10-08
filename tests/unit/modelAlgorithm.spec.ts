import { shallowMount } from "@vue/test-utils";
import AnalysisReport from "@/views/AnalysisReport.vue";
import i18n from "@/plugins/i18n";

describe("Model & Algorithm chart counts", () => {
  it("counts legacy secrecy answers, multiple selections and active filters", async () => {
    const records = [
      {
        package_id: "legacy",
        version: "v0.10.0",
        source: "published",
        data: { aboutAlgorithm1: "item1-3" }
      },
      {
        package_id: "current",
        version: "v1.0.1",
        source: "recovered",
        data: {
          aboutAlgorithm1: "item2-0",
          aboutAlgorithm3: ["item1-0", "item2-1"],
          aboutAlgorithm4: ["item2-1"],
          aboutAlgorithm5: "item1-0"
        }
      },
      {
        package_id: "missing",
        version: "v1.0.1",
        source: "published",
        data: {}
      }
    ];
    (window as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      text: () =>
        Promise.resolve(
          records.map(record => JSON.stringify(record)).join("\n")
        )
    });
    (window as any).Chart = jest.fn();
    const createChart = jest.fn();
    const wrapper = shallowMount(AnalysisReport, {
      i18n,
      methods: { createChart }
    });
    await new Promise(resolve => setTimeout(resolve, 0));
    const vm = wrapper.vm as any;
    const palette = ["black", "green", "blue"];
    createChart.mockClear();
    vm.renderModelAlgorithmCharts(palette);
    expect(
      createChart.mock.calls.map(call => call[1].data.datasets[0].data)
    ).toEqual([
      [1, 1],
      [1, 1],
      [0, 1],
      [1, 0]
    ]);
    vm.selectedSource = "published";
    createChart.mockClear();
    vm.renderModelAlgorithmCharts(palette);
    expect(
      createChart.mock.calls.map(call => call[1].data.datasets[0].data)
    ).toEqual([
      [1, 0],
      [0, 0],
      [0, 0],
      [0, 0]
    ]);
    wrapper.destroy();
    delete (window as any).Chart;
  });
});
