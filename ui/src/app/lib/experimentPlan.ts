"use client";

const PLAN_HEADING_REGEX =
  /^(?:#{1,6}\s+|\*\*\s*)?(?:Experiment Plan|Clean Experiment Plan)(?:\s*\*\*)?\s*:?\s*$/im;
const LEGACY_SECTION_START_REGEX =
  /^(?:#{1,6}\s+|\*\*\s*)?(?:Goal|Locked Constraints|Recommended Campaign|Execution Order|Data Package|Must Decide Now|Optional Extensions|Run This Default Plan|Phase\s+\d+\s+[—-].+?)(?:\s*\*\*)?(?::.*)?$/gim;
const CANONICAL_SECTION_PREFIXES = [
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
  "Run This Default Plan",
] as const;

function collapseBlankLines(lines: string[]): string[] {
  const collapsed: string[] = [];
  let previousBlank = false;

  lines.forEach((line) => {
    const isBlank = line.trim().length === 0;
    if (isBlank) {
      if (!previousBlank) {
        collapsed.push("");
      }
      previousBlank = true;
      return;
    }

    collapsed.push(line);
    previousBlank = false;
  });

  while (collapsed.length > 0 && collapsed[0].trim().length === 0) {
    collapsed.shift();
  }
  while (
    collapsed.length > 0 &&
    collapsed[collapsed.length - 1].trim().length === 0
  ) {
    collapsed.pop();
  }

  return collapsed;
}

function unwrapBoldLine(line: string): string {
  const trimmed = line.trim();
  const wrapped = trimmed.match(/^\*\*(.+?)\*\*:?\s*$/);
  return wrapped ? wrapped[1].trim() : trimmed;
}

function splitHeadingLine(line: string): {
  heading: string;
  trailingText: string | null;
} | null {
  const cleaned = unwrapBoldLine(line).replace(/:+$/, "").trim();
  if (!cleaned) {
    return null;
  }

  for (const prefix of CANONICAL_SECTION_PREFIXES) {
    if (
      cleaned === prefix ||
      cleaned.startsWith(`${prefix} (`) ||
      cleaned.startsWith(`${prefix} -`) ||
      cleaned.startsWith(`${prefix} —`)
    ) {
      return {
        heading: cleaned,
        trailingText: null,
      };
    }

    const inlineMatch = cleaned.match(
      new RegExp(
        `^(${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})\\s*:\\s+(.+)$`,
        "i"
      )
    );
    if (inlineMatch) {
      return {
        heading: inlineMatch[1].trim(),
        trailingText: inlineMatch[2].trim(),
      };
    }
  }

  return null;
}

function normalizeExperimentPlan(content: string): string {
  const rawLines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const normalizedLines: string[] = [];
  let headingInserted = false;

  rawLines.forEach((rawLine) => {
    const trimmed = rawLine.trim();

    if (!headingInserted && PLAN_HEADING_REGEX.test(trimmed)) {
      normalizedLines.push("# Experiment Plan");
      normalizedLines.push("");
      headingInserted = true;
      return;
    }

    if (!headingInserted) {
      normalizedLines.push("# Experiment Plan");
      normalizedLines.push("");
      headingInserted = true;
    }

    if (!trimmed) {
      normalizedLines.push("");
      return;
    }

    const splitHeading = splitHeadingLine(trimmed);
    if (splitHeading) {
      if (
        normalizedLines.length > 0 &&
        normalizedLines[normalizedLines.length - 1].trim().length > 0
      ) {
        normalizedLines.push("");
      }
      normalizedLines.push(`## ${splitHeading.heading}`);
      if (splitHeading.trailingText) {
        normalizedLines.push("");
        normalizedLines.push(splitHeading.trailingText);
      }
      return;
    }

    normalizedLines.push(rawLine.trimEnd());
  });

  const collapsed = collapseBlankLines(normalizedLines);
  if (
    collapsed.length >= 2 &&
    collapsed[0].trim().toLowerCase() === "# experiment plan" &&
    /^#{1,6}\s+experiment plan$/i.test(collapsed[1].trim())
  ) {
    collapsed.splice(1, 1);
    if (collapsed[1]?.trim().length === 0) {
      collapsed.splice(1, 1);
    }
  }
  return collapsed.join("\n");
}

export function stripExperimentPlanTitleHeadingForPreview(content: string): string {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const lines = normalized.split("\n");
  const firstNonBlankIndex = lines.findIndex((line) => line.trim().length > 0);

  if (firstNonBlankIndex < 0) {
    return normalized.trim();
  }

  const firstLine = lines[firstNonBlankIndex].trim();
  if (!/^#\s+(?:Experiment Plan|Clean Experiment Plan)\s*$/i.test(firstLine)) {
    return normalized.trim();
  }

  const remainingLines = [
    ...lines.slice(0, firstNonBlankIndex),
    ...lines.slice(firstNonBlankIndex + 1),
  ];

  return collapseBlankLines(remainingLines).join("\n").trim();
}

export function extractCleanExperimentPlan(content: string): string | null {
  const headingMatch = PLAN_HEADING_REGEX.exec(content);
  const headingIndex =
    headingMatch && typeof headingMatch.index === "number"
      ? headingMatch.index
      : -1;

  const legacySectionMatches = Array.from(content.matchAll(LEGACY_SECTION_START_REGEX));
  const fallbackSectionIndex =
    headingIndex < 0 && typeof legacySectionMatches[0]?.index === "number"
      ? legacySectionMatches[0].index
      : -1;

  if (headingIndex < 0 && fallbackSectionIndex < 0) {
    return null;
  }

  const startIndex = headingIndex >= 0 ? headingIndex : fallbackSectionIndex;
  const planContent = normalizeExperimentPlan(content.slice(startIndex).trim());
  return planContent.length > 0 ? planContent : null;
}

export function buildCleanExperimentPlanFilePath(
  messageId: string,
  _planContent: string,
  options?: { slugHint?: string }
): string {
  const slugHint = String(options?.slugHint || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (slugHint) {
    return `/plans/${slugHint}.md`;
  }
  const idSuffix = messageId.slice(0, 8).toLowerCase();
  return `/plans/experiment-plan-${idSuffix}.md`;
}
