function cleanInlineText(value: string): string {
  return value.replace(/\u00a0/g, " ").replace(/\s+/g, " ");
}

function inlineMarkdown(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return cleanInlineText(node.textContent || "");
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const element = node as HTMLElement;
  const content = Array.from(element.childNodes)
    .map(inlineMarkdown)
    .join("");

  switch (element.tagName.toLowerCase()) {
    case "a": {
      const href = element.getAttribute("href") || "";
      return href ? `[${content.trim()}](${href})` : content;
    }
    case "strong":
    case "b":
      return `**${content.trim()}**`;
    case "em":
    case "i":
      return `*${content.trim()}*`;
    case "code":
      return `\`${content.trim()}\``;
    case "br":
      return "\n";
    case "textarea":
      return cleanInlineText((element as HTMLTextAreaElement).value);
    default:
      return content;
  }
}

function tableMarkdown(table: HTMLTableElement): string {
  const rows = Array.from(table.rows).map(row =>
    Array.from(row.cells).map(cell => inlineMarkdown(cell).trim())
  );
  if (rows.length === 0) return "";

  const width = Math.max(...rows.map(row => row.length));
  const normalizeRow = (row: string[]) =>
    `| ${row
      .concat(Array(width).fill(""))
      .slice(0, width)
      .join(" | ")} |`;
  return `${normalizeRow(rows[0])}\n${normalizeRow(
    Array(width).fill("---")
  )}\n${rows
    .slice(1)
    .map(normalizeRow)
    .join("\n")}\n\n`;
}

function listMarkdown(list: HTMLElement, depth = 0): string {
  const ordered = list.tagName.toLowerCase() === "ol";
  const items = Array.from(list.children).filter(
    child => child.tagName.toLowerCase() === "li"
  );
  return `${items
    .map((item, index) => {
      const nestedLists = Array.from(item.children).filter(child =>
        ["ul", "ol"].includes(child.tagName.toLowerCase())
      ) as HTMLElement[];
      const clone = item.cloneNode(true) as HTMLElement;
      Array.from(clone.children)
        .filter(child => ["ul", "ol"].includes(child.tagName.toLowerCase()))
        .forEach(child => child.remove());
      const marker = ordered ? `${index + 1}.` : "-";
      const line = `${"  ".repeat(depth)}${marker} ${inlineMarkdown(
        clone
      ).trim()}`;
      return [
        line,
        ...nestedLists.map(nested => listMarkdown(nested, depth + 1))
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n")}\n\n`;
}

function blockMarkdown(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return cleanInlineText(node.textContent || "");
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return "";

  const element = node as HTMLElement;
  const tag = element.tagName.toLowerCase();
  if (/^h[1-6]$/.test(tag)) {
    return `${"#".repeat(Number(tag[1]))} ${inlineMarkdown(
      element
    ).trim()}\n\n`;
  }
  if (tag === "p") return `${inlineMarkdown(element).trim()}\n\n`;
  if (tag === "ul" || tag === "ol") return listMarkdown(element);
  if (tag === "table") return tableMarkdown(element as HTMLTableElement);
  if (tag === "hr") return "---\n\n";

  const content = Array.from(element.childNodes)
    .map(blockMarkdown)
    .join("");
  return ["div", "section", "article", "main"].includes(tag)
    ? `${content}\n`
    : content;
}

export function elementToMarkdown(element: HTMLElement): string {
  return `${Array.from(element.childNodes)
    .map(blockMarkdown)
    .join("")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()}\n`;
}
