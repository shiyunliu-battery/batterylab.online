import { execFile } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";
import * as XLSX from "xlsx";
import {
  buildPythonUnavailableMessage,
  resolvePythonExecutable,
  resolveRepoRoot,
} from "@/app/api/_lib/python";

const execFileAsync = promisify(execFile);
const repoRoot = resolveRepoRoot();
const pdfExtractorScript = path.join(
  repoRoot,
  "scripts",
  "extract_pdf_attachment_text.py"
);

const MAX_EXTRACTED_CHARS = 200_000;
const MAX_EXTRACTABLE_FILE_BYTES = 12 * 1024 * 1024;
const MAX_MULTIPART_OVERHEAD_BYTES = 512 * 1024;
const PDF_EXTRACTOR_MAX_BUFFER_BYTES = 4 * 1024 * 1024;
const MAX_SHEETS = 6;
const MAX_ROWS_PER_SHEET = 50;
const MAX_COLUMNS_PER_SHEET = 20;

type ExtractionPayload = {
  content: string;
  summaryLabel: string;
  extractedExtension: string;
};

function getFileExtension(fileName: string): string {
  const parts = fileName.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "";
}

function truncateContent(content: string): string {
  if (content.length <= MAX_EXTRACTED_CHARS) {
    return content;
  }

  return `${content.slice(0, MAX_EXTRACTED_CHARS)}\n\n[Truncated after ${MAX_EXTRACTED_CHARS.toLocaleString()} characters for chat upload preview.]`;
}

function sanitizeCellValue(value: unknown): string {
  return String(value ?? "")
    .replace(/\r\n/g, " ")
    .replace(/\n/g, " ")
    .replace(/\r/g, " ")
    .replace(/\t/g, " ")
    .trim();
}

function extractBufferedOutput(value: unknown): string {
  if (Buffer.isBuffer(value)) {
    return value.toString("utf8").trim();
  }
  return typeof value === "string" ? value.trim() : "";
}

function buildPythonExtractionError(error: unknown): Error {
  const stdout = extractBufferedOutput((error as { stdout?: unknown })?.stdout);
  const stderr = extractBufferedOutput((error as { stderr?: unknown })?.stderr);

  if (stdout) {
    try {
      const payload = JSON.parse(stdout) as {
        error?: string;
        details?: unknown;
      };
      if (payload.error) {
        const details = Array.isArray(payload.details)
          ? payload.details.join("; ")
          : typeof payload.details === "string"
            ? payload.details
            : "";
        return new Error([payload.error, details].filter(Boolean).join(" "));
      }
    } catch {
      // Fall through to the raw process error below.
    }
  }

  if (stderr) {
    return new Error(stderr);
  }

  return error instanceof Error
    ? error
    : new Error("PDF text extraction failed unexpectedly.");
}

async function extractPdfPreview(file: File): Promise<ExtractionPayload> {
  const pythonExecutable = await resolvePythonExecutable(repoRoot);
  if (!pythonExecutable) {
    throw new Error(buildPythonUnavailableMessage("PDF text extraction"));
  }

  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "ionera-attachment-"));
  const tempPath = path.join(tempDir, file.name || "upload.pdf");

  try {
    await fs.writeFile(tempPath, Buffer.from(await file.arrayBuffer()));
    let stdout: string;
    try {
      const execution = await execFileAsync(
        pythonExecutable,
        [pdfExtractorScript, tempPath, String(MAX_EXTRACTED_CHARS)],
        {
          cwd: repoRoot,
          encoding: "utf8",
          env: {
            ...process.env,
            PYTHONIOENCODING: "utf-8",
          },
          maxBuffer: PDF_EXTRACTOR_MAX_BUFFER_BYTES,
          windowsHide: true,
        }
      );
      stdout = String(execution.stdout);
    } catch (error) {
      throw buildPythonExtractionError(error);
    }

    const payload = JSON.parse(stdout) as {
      text?: string;
      page_count?: number;
      engine?: string;
      truncated?: boolean;
    };
    const extractedText = payload.text?.trim();

    const content = truncateContent(
      [
        `Attachment extraction preview`,
        `Original filename: ${file.name}`,
        `MIME type: ${file.type || "application/pdf"}`,
        `Extraction mode: pdf text extraction (${payload.engine || "python"})`,
        typeof payload.page_count === "number"
          ? `Detected pages: ${payload.page_count}`
          : "",
        payload.truncated ? "Extraction preview was truncated." : "",
        "",
        extractedText && extractedText.length > 0
          ? extractedText
          : "[No extractable text was found in this PDF.]",
      ].join("\n")
    );

    return {
      content,
      summaryLabel: "pdf text extraction",
      extractedExtension: "txt",
    };
  } finally {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
}

async function extractSpreadsheetPreview(file: File): Promise<ExtractionPayload> {
  const buffer = Buffer.from(await file.arrayBuffer());
  const workbook = XLSX.read(buffer, { type: "buffer" });
  const sheetNames = workbook.SheetNames.slice(0, MAX_SHEETS);
  const omittedSheetCount = Math.max(workbook.SheetNames.length - sheetNames.length, 0);

  const sections: string[] = [
    "Attachment extraction preview",
    `Original filename: ${file.name}`,
    `MIME type: ${file.type || "application/octet-stream"}`,
    "Extraction mode: spreadsheet preview",
    "",
  ];

  if (sheetNames.length === 0) {
    sections.push("[No visible sheets were found in this workbook.]");
  }

  for (const sheetName of sheetNames) {
    const worksheet = workbook.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(worksheet, {
      header: 1,
      raw: false,
      blankrows: false,
      defval: "",
    }) as unknown[][];
    const previewRows = rows.slice(0, MAX_ROWS_PER_SHEET).map((row) =>
      row.slice(0, MAX_COLUMNS_PER_SHEET).map((cell) => sanitizeCellValue(cell))
    );

    sections.push(`## Sheet: ${sheetName}`);

    if (previewRows.length === 0) {
      sections.push("[No populated rows in preview range.]", "");
      continue;
    }

    sections.push(
      ...previewRows.map((row) => row.join("\t")),
      rows.length > MAX_ROWS_PER_SHEET
        ? `[Preview truncated after ${MAX_ROWS_PER_SHEET} rows.]`
        : "",
      ""
    );
  }

  if (omittedSheetCount > 0) {
    sections.push(`[Preview truncated after ${MAX_SHEETS} sheets; ${omittedSheetCount} additional sheet(s) omitted.]`);
  }

  return {
    content: truncateContent(sections.join("\n").trim()),
    summaryLabel: "spreadsheet preview",
    extractedExtension: "txt",
  };
}

export const runtime = "nodejs";

export async function POST(request: Request) {
  const contentLengthHeader = request.headers.get("content-length");
  const contentLength = contentLengthHeader ? Number(contentLengthHeader) : NaN;

  if (
    Number.isFinite(contentLength) &&
    contentLength > MAX_EXTRACTABLE_FILE_BYTES + MAX_MULTIPART_OVERHEAD_BYTES
  ) {
    return NextResponse.json(
      {
        error: `Automatic preview is limited to files up to ${Math.round(
          MAX_EXTRACTABLE_FILE_BYTES / (1024 * 1024)
        )} MB.`,
      },
      { status: 413 }
    );
  }

  let formData: FormData;

  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      {
        error:
          "The attachment upload could not be parsed. Try a smaller PDF or spreadsheet file.",
      },
      { status: 413 }
    );
  }

  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json(
      { error: "Expected a file upload in the 'file' field." },
      { status: 400 }
    );
  }

  const extension = getFileExtension(file.name);
  if (file.size > MAX_EXTRACTABLE_FILE_BYTES) {
    return NextResponse.json(
      {
        error: `Automatic preview is limited to files up to ${Math.round(
          MAX_EXTRACTABLE_FILE_BYTES / (1024 * 1024)
        )} MB.`,
      },
      { status: 413 }
    );
  }

  try {
    let payload: ExtractionPayload;

    if (extension === "pdf") {
      payload = await extractPdfPreview(file);
    } else if (extension === "xlsx" || extension === "xls") {
      payload = await extractSpreadsheetPreview(file);
    } else {
      return NextResponse.json(
        { error: `Unsupported extraction format: ${extension || "unknown"}.` },
        { status: 400 }
      );
    }

    return NextResponse.json(payload);
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Attachment extraction failed unexpectedly.",
      },
      { status: 500 }
    );
  }
}
