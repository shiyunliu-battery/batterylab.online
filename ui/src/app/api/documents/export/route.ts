import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";

type ExportFormat = "md" | "tex" | "pdf";
type BlockType =
  | "heading1"
  | "heading2"
  | "heading3"
  | "paragraph"
  | "bullet"
  | "numbered"
  | "reference"
  | "table";

type MarkdownBlock = {
  type: BlockType;
  text: string;
  marker?: string;
  headers?: string[];
  rows?: string[][];
};

const IMPLICIT_SECTION_PREFIXES = [
  "Plan Status & Constraints",
  "Fixed Facts",
  "Provisional Defaults",
  "Internal SOP Constraints",
  "Unresolved Hard Constraints",
  "Pending Confirmations",
  "Protocol",
  "Equipment & Setup",
  "Condition Matrix",
  "Protocol Parameters",
  "DCR/HPPC Parameters",
  "Workflow Steps",
  "Checkpoint / Stop Rules",
  "Outputs & Basis",
  "Raw Data Logging",
  "Derived Outputs",
  "Audit Metadata",
  "Calculation & QC Notes",
  "Analysis Plan",
  "References",
  "Public",
  "User-Supplied",
  "Built-In Guidance",
  "Objective",
  "Known Constraints",
  "Goal",
  "Locked Constraints",
  "Recommended Campaign",
  "Execution Order",
  "Data Package",
  "Must Decide Now",
  "Optional Extensions",
] as const;

function sanitizeDownloadStem(fileName: string, fallback = "document"): string {
  const baseName = path.basename(fileName || fallback, path.extname(fileName || ""));
  const sanitized = baseName
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return sanitized || fallback;
}

function inferTitle(fileName: string, content: string): string {
  const firstHeading = content.match(/^#\s+(.+)$/m)?.[1]?.trim();
  if (firstHeading) {
    return stripInlineMarkdown(firstHeading);
  }

  const stem = sanitizeDownloadStem(fileName, "experiment-plan");
  return stem
    .split(/[-_]+/)
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function normalizeContent(content: string): string {
  return content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
}

function normalizeDocumentText(value: string): string {
  return value
    .replace(/\u00a0/g, " ")
    .replace(/\u200b/g, "")
    .replace(/\uFEFF/g, "");
}

function stripInlineMarkdown(value: string): string {
  return normalizeDocumentText(
    value
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/__([^_]+)__/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/(?<![A-Za-z0-9])_([^_]+)_(?![A-Za-z0-9])/g, "$1")
      .replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1")
  ).trim();
}

function unwrapStandaloneBoldLine(line: string): string {
  const trimmed = line.trim();
  const match = trimmed.match(/^\*\*(.+?)\*\*:?\s*$/);
  return match ? match[1].trim() : trimmed;
}

function parseImplicitHeading(
  line: string
): { level: 1 | 2; text: string; trailingText?: string } | null {
  const cleaned = unwrapStandaloneBoldLine(line).replace(/:+$/, "").trim();
  if (!cleaned) {
    return null;
  }

  if (/^(Experiment Plan|Clean Experiment Plan)$/i.test(cleaned)) {
    return { level: 1, text: "Experiment Plan" };
  }

  const phaseWithPurpose = cleaned.match(
    /^(Phase\s+\d+\s+[—-]\s*.+?)\s+Purpose:\s*(.+)$/i
  );
  if (phaseWithPurpose) {
    return {
      level: 2,
      text: phaseWithPurpose[1].trim(),
      trailingText: `Purpose: ${phaseWithPurpose[2].trim()}`,
    };
  }

  if (/^Phase\s+\d+\s+[—-]\s*.+$/i.test(cleaned)) {
    return { level: 2, text: cleaned };
  }

  for (const prefix of IMPLICIT_SECTION_PREFIXES) {
    if (
      cleaned === prefix ||
      cleaned.startsWith(`${prefix} (`) ||
      cleaned.startsWith(`${prefix} -`) ||
      cleaned.startsWith(`${prefix} —`)
    ) {
      return { level: 2, text: cleaned };
    }

    const inlineMatch = cleaned.match(
      new RegExp(`^(${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})\\s*:\\s+(.+)$`, "i")
    );
    if (inlineMatch) {
      return {
        level: 2,
        text: inlineMatch[1].trim(),
        trailingText: inlineMatch[2].trim(),
      };
    }
  }

  return null;
}

function parseTableCells(line: string): string[] {
  const trimmed = line.trim();
  const withoutOuterPipes = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  return withoutOuterPipes.split("|").map((cell) => stripInlineMarkdown(cell.trim()));
}

function isTableDivider(line: string): boolean {
  const cells = parseTableCells(line);
  return (
    cells.length > 0 &&
    cells.every((cell) => /^:?-{3,}:?$/.test(cell.replace(/\s+/g, "")))
  );
}

function isReferenceLine(line: string): RegExpMatchArray | null {
  return line.match(/^\[(\d+)\]\s+(.+)$/);
}

function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = normalizeContent(content).split("\n");
  const blocks: MarkdownBlock[] = [];
  let paragraphBuffer: string[] = [];

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) {
      return;
    }
    const paragraphText = stripInlineMarkdown(paragraphBuffer.join(" "));
    if (paragraphText) {
      blocks.push({ type: "paragraph", text: paragraphText });
    }
    paragraphBuffer = [];
  };

  let index = 0;
  while (index < lines.length) {
    const rawLine = lines[index];
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      const level = heading[1].length;
      blocks.push({
        type:
          level === 1 ? "heading1" : level === 2 ? "heading2" : "heading3",
        text: stripInlineMarkdown(heading[2]),
      });
      index += 1;
      continue;
    }

    if (/^(?:---+|\*\*\*+|___+)\s*$/.test(line)) {
      flushParagraph();
      index += 1;
      continue;
    }

    const implicitHeading = parseImplicitHeading(line);
    if (implicitHeading) {
      flushParagraph();
      blocks.push({
        type:
          implicitHeading.level === 1
            ? "heading1"
            : "heading2",
        text: stripInlineMarkdown(implicitHeading.text),
      });
      if (implicitHeading.trailingText) {
        blocks.push({
          type: "paragraph",
          text: stripInlineMarkdown(implicitHeading.trailingText),
        });
      }
      index += 1;
      continue;
    }

    const nextLine = index + 1 < lines.length ? lines[index + 1].trim() : "";
    if (line.startsWith("|") && nextLine.startsWith("|") && isTableDivider(nextLine)) {
      flushParagraph();
      const headers = parseTableCells(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        rows.push(parseTableCells(lines[index]));
        index += 1;
      }
      blocks.push({
        type: "table",
        text: headers.join(" | "),
        headers,
        rows,
      });
      continue;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      blocks.push({
        type: "bullet",
        text: stripInlineMarkdown(bullet[1]),
        marker: "- ",
      });
      index += 1;
      continue;
    }

    const numbered = line.match(/^(\d+)\.\s+(.+)$/);
    if (numbered) {
      flushParagraph();
      blocks.push({
        type: "numbered",
        text: stripInlineMarkdown(numbered[2]),
        marker: `${numbered[1]}. `,
      });
      index += 1;
      continue;
    }

    const reference = isReferenceLine(line);
    if (reference) {
      flushParagraph();
      const marker = `[${reference[1]}] `;
      const referenceParts = [reference[2].trim()];
      index += 1;

      while (index < lines.length) {
        const continuationLine = lines[index].trim();
        if (!continuationLine) {
          break;
        }
        if (
          continuationLine.match(/^(#{1,6})\s+(.+)$/) ||
          /^(?:---+|\*\*\*+|___+)\s*$/.test(continuationLine) ||
          parseImplicitHeading(continuationLine) ||
          isReferenceLine(continuationLine) ||
          continuationLine.match(/^[-*]\s+(.+)$/) ||
          continuationLine.match(/^(\d+)\.\s+(.+)$/)
        ) {
          break;
        }

        const followingLine = index + 1 < lines.length ? lines[index + 1].trim() : "";
        if (
          continuationLine.startsWith("|") &&
          followingLine.startsWith("|") &&
          isTableDivider(followingLine)
        ) {
          break;
        }

        referenceParts.push(continuationLine);
        index += 1;
      }

      blocks.push({
        type: "reference",
        text: stripInlineMarkdown(referenceParts.join(" ")),
        marker,
      });
      continue;
    }

    paragraphBuffer.push(line);
    index += 1;
  }

  flushParagraph();
  return blocks;
}

function stripLeadingTitleHeading(content: string, title: string): string {
  const normalized = normalizeContent(content);
  const lines = normalized.split("\n");
  const firstNonBlankIndex = lines.findIndex((line) => line.trim().length > 0);
  if (firstNonBlankIndex < 0) {
    return normalized;
  }

  const firstLine = lines[firstNonBlankIndex].trim();
  const headingMatch = firstLine.match(/^#\s+(.+)$/);
  if (
    headingMatch &&
    stripInlineMarkdown(headingMatch[1]).toLowerCase() ===
      stripInlineMarkdown(title).toLowerCase()
  ) {
    const remaining = [
      ...lines.slice(0, firstNonBlankIndex),
      ...lines.slice(firstNonBlankIndex + 1),
    ].join("\n");
    return normalizeContent(remaining);
  }

  return normalized;
}

function escapeLatex(value: string): string {
  return value
    .replace(/\\/g, "\\textbackslash{}")
    .replace(/([#$%&_{}])/g, "\\$1")
    .replace(/\^/g, "\\textasciicircum{}")
    .replace(/~/g, "\\textasciitilde{}");
}

function buildLatexDocument(title: string, content: string): string {
  const blocks = parseMarkdownBlocks(stripLeadingTitleHeading(content, title));
  const latexLines: string[] = [
    "\\documentclass[11pt]{article}",
    "\\usepackage[margin=1in]{geometry}",
    "\\usepackage[T1]{fontenc}",
    "\\usepackage[utf8]{inputenc}",
    "\\usepackage{hyperref}",
    "\\usepackage{tabularx}",
    "\\usepackage{array}",
    "\\title{" + escapeLatex(title) + "}",
    "\\date{}",
    "\\begin{document}",
    "\\maketitle",
  ];

  let index = 0;
  while (index < blocks.length) {
    const block = blocks[index];
    if (block.type === "heading1") {
      latexLines.push(`\\section*{${escapeLatex(block.text)}}`);
      index += 1;
      continue;
    }
    if (block.type === "heading2") {
      latexLines.push(`\\subsection*{${escapeLatex(block.text)}}`);
      index += 1;
      continue;
    }
    if (block.type === "heading3") {
      latexLines.push(`\\subsubsection*{${escapeLatex(block.text)}}`);
      index += 1;
      continue;
    }
    if (block.type === "bullet") {
      latexLines.push("\\begin{itemize}");
      while (index < blocks.length && blocks[index].type === "bullet") {
        latexLines.push(`\\item ${escapeLatex(blocks[index].text)}`);
        index += 1;
      }
      latexLines.push("\\end{itemize}");
      continue;
    }
    if (block.type === "numbered") {
      latexLines.push("\\begin{enumerate}");
      while (index < blocks.length && blocks[index].type === "numbered") {
        latexLines.push(`\\item ${escapeLatex(blocks[index].text)}`);
        index += 1;
      }
      latexLines.push("\\end{enumerate}");
      continue;
    }
    if (block.type === "reference") {
      const marker = block.marker || "";
      latexLines.push(`\\noindent ${escapeLatex(`${marker}${block.text}`)}\\par`);
      latexLines.push("");
      index += 1;
      continue;
    }
    if (block.type === "table") {
      const headers = block.headers ?? [];
      const rows = block.rows ?? [];
      if (headers.length > 0) {
        const columnSpec = `|${headers.map(() => "X|").join("")}`;
        latexLines.push("\\begin{tabularx}{\\textwidth}{" + columnSpec + "}");
        latexLines.push("\\hline");
        latexLines.push(headers.map((cell) => `\\textbf{${escapeLatex(cell)}}`).join(" & ") + " \\\\");
        latexLines.push("\\hline");
        rows.forEach((row) => {
          const paddedRow = headers.map((_, cellIndex) => escapeLatex(row[cellIndex] ?? ""));
          latexLines.push(paddedRow.join(" & ") + " \\\\");
          latexLines.push("\\hline");
        });
        latexLines.push("\\end{tabularx}");
        latexLines.push("");
      }
      index += 1;
      continue;
    }

    latexLines.push(escapeLatex(block.text));
    latexLines.push("");
    index += 1;
  }

  latexLines.push("\\end{document}", "");
  return latexLines.join("\n");
}

function resolveRepoRoot(): string {
  const cwd = process.cwd();
  return path.basename(cwd).toLowerCase() === "ui" ? path.resolve(cwd, "..") : cwd;
}

function resolvePythonExecutable(repoRoot: string): string | null {
  const candidates = [
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
    path.join(repoRoot, ".venv", "bin", "python"),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return null;
}

function buildPdfPayload(title: string, content: string): string {
  const contentWithoutTitleHeading = stripLeadingTitleHeading(content, title);
  return JSON.stringify(
    {
      title,
      blocks: parseMarkdownBlocks(contentWithoutTitleHeading),
    },
    null,
    2
  );
}

function buildRenderedPdf(title: string, content: string): Buffer {
  const repoRoot = resolveRepoRoot();
  const pythonExecutable = resolvePythonExecutable(repoRoot);
  if (!pythonExecutable) {
    throw new Error("Python environment for PDF export is not available.");
  }

  const scriptPath = path.join(repoRoot, "scripts", "render_experiment_plan_pdf.py");
  if (!fs.existsSync(scriptPath)) {
    throw new Error("PDF renderer script is missing.");
  }

  const tempDir = path.join(repoRoot, "tmp", "pdfs");
  fs.mkdirSync(tempDir, { recursive: true });

  const requestId = randomUUID();
  const inputPath = path.join(tempDir, `plan-export-${requestId}.json`);
  const outputPath = path.join(tempDir, `plan-export-${requestId}.pdf`);

  try {
    fs.writeFileSync(inputPath, buildPdfPayload(title, content), "utf8");

    const execution = spawnSync(
      pythonExecutable,
      [scriptPath, "--input", inputPath, "--output", outputPath],
      {
        cwd: repoRoot,
        encoding: "utf8",
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
        },
      }
    );

    if (execution.status !== 0) {
      throw new Error(
        execution.stderr?.trim() ||
          execution.stdout?.trim() ||
          "Failed to render the PDF export."
      );
    }

    if (!fs.existsSync(outputPath)) {
      throw new Error("Rendered PDF output was not created.");
    }

    return fs.readFileSync(outputPath);
  } finally {
    if (fs.existsSync(inputPath)) {
      fs.unlinkSync(inputPath);
    }
    if (fs.existsSync(outputPath)) {
      fs.unlinkSync(outputPath);
    }
  }
}

function buildMarkdownDocument(content: string): string {
  return `${content.trimEnd()}\n`;
}

export const runtime = "nodejs";

export async function POST(request: Request) {
  const payload = (await request.json()) as {
    content?: unknown;
    fileName?: unknown;
    format?: unknown;
  };

  const format = String(payload.format || "").toLowerCase() as ExportFormat;
  const rawContent = typeof payload.content === "string" ? payload.content : "";
  const fileName =
    typeof payload.fileName === "string" && payload.fileName.trim().length > 0
      ? payload.fileName
      : "document";

  if (!["md", "tex", "pdf"].includes(format)) {
    return Response.json(
      { error: "Supported export formats are md, tex, and pdf." },
      { status: 400 }
    );
  }

  if (!rawContent.trim()) {
    return Response.json(
      { error: "Cannot export an empty document." },
      { status: 400 }
    );
  }

  const content = normalizeContent(rawContent);
  const title = inferTitle(fileName, content);
  const downloadStem = sanitizeDownloadStem(fileName, "document");

  let body: string | Buffer;
  let contentType: string;
  let extension: string;

  if (format === "tex") {
    body = buildLatexDocument(title, content);
    contentType = "application/x-tex; charset=utf-8";
    extension = "tex";
  } else if (format === "pdf") {
    body = buildRenderedPdf(title, content);
    contentType = "application/pdf";
    extension = "pdf";
  } else {
    body = buildMarkdownDocument(content);
    contentType = "text/markdown; charset=utf-8";
    extension = "md";
  }

  const responseBody =
    typeof body === "string" ? body : new Uint8Array(body);

  return new Response(responseBody, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `attachment; filename="${downloadStem}.${extension}"`,
    },
  });
}
