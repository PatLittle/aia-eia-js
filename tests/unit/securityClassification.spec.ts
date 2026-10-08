import { shallowMount } from "@vue/test-utils";
import AnalysisReport from "@/views/AnalysisReport.vue";
import i18n from "@/plugins/i18n";

describe("Security classification pie chart", () => {
  it("preserves combined legacy categories and excludes missing answers with active filters", async () => {
    const records = [
      {
        package_id: "legacy",
        version: "v0.10.0",
        source: "published",
        data: { aboutDataSource2: "item4-3" }
      },
      {
        package_id: "current",
        version: "v1.0.1",
        source: "recovered",
        data: { aboutDataSource2: "item4-3" }
      },
      {
        package_id: "none",
        version: "v0.9",
        source: "published",
        data: { aboutDataSource2: "item1-0" }
      },
      {
        package_id: "missing",
        version: "v1.0.1",
        source: "published",
        data: {}
      },
      {
        package_id: "invalid",
        version: "v1.0.1",
        source: "published",
        data: { aboutDataSource2: "unknown" }
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
    expect(
      vm.securityClassificationCounts.map((item: any) => [
        item.label,
        item.value
      ])
    ).toEqual([
      ["None", 1],
      ["Protected B", 1],
      ["Protected B / Protected C", 1]
    ]);
    expect(vm.securityAnswerCount).toBe(3);
    createChart.mockClear();
    vm.renderSecurityChart();
    expect(createChart.mock.calls[0][1].type).toBe("pie");
    expect(createChart.mock.calls[0][1].data.datasets[0].data).toEqual([
      1,
      1,
      1
    ]);
    expect(
      wrapper.find(".security-card").element.nextElementSibling!.textContent
    ).toContain("Chart data");
    vm.selectedSource = "recovered";
    expect(
      vm.securityClassificationCounts.map((item: any) => item.label)
    ).toEqual(["Protected B"]);
    vm.selectedVersion = "v0.10.0";
    expect(vm.securityAnswerCount).toBe(0);
    createChart.mockClear();
    vm.renderSecurityChart();
    expect(createChart).not.toHaveBeenCalled();
    wrapper.destroy();
    delete (window as any).Chart;
  });
});
