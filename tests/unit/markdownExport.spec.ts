import { elementToMarkdown } from "@/utils/markdownExport";

describe("Markdown export", () => {
  it("converts result headings, links, emphasis, lists, and tables", () => {
    const content = document.createElement("div");
    content.innerHTML = `
      <h1>AIA Results</h1>
      <p><strong>Version:</strong> 1.0.1</p>
      <h2>Questions and Answers</h2>
      <ul><li>First answer</li><li><a href="https://example.ca">Source</a></li></ul>
      <table><tr><th>Area</th><th>Score</th></tr><tr><td>Impact</td><td>3</td></tr></table>
    `;

    const markdown = elementToMarkdown(content);

    expect(markdown).toContain("# AIA Results");
    expect(markdown).toContain("**Version:** 1.0.1");
    expect(markdown).toContain("## Questions and Answers");
    expect(markdown).toContain("- First answer");
    expect(markdown).toContain("[Source](https://example.ca)");
    expect(markdown).toContain("| Area | Score |");
    expect(markdown).toContain("| --- | --- |");
  });
});
