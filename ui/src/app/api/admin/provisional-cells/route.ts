import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";
import { NextResponse } from "next/server";

const execFileAsync = promisify(execFile);
const repoRoot = path.resolve(process.cwd(), "..");
const pythonExecutable =
  process.platform === "win32"
    ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
    : path.join(repoRoot, ".venv", "bin", "python");
const adminScript = path.join(
  repoRoot,
  "scripts",
  "provisional_cell_asset_admin.py"
);

const MAX_BUFFER_BYTES = 8 * 1024 * 1024;

type ApiPayload = {
  status?: string;
  error_type?: string;
  message?: string;
  [key: string]: unknown;
};

function buildStatusCode(payload: ApiPayload): number {
  if (payload.status !== "error") return 200;
  if (payload.error_type === "unknown_provisional_cell_asset") return 404;
  if (payload.error_type === "invalid_json_payload") return 400;
  if (payload.error_type?.includes("validation")) return 400;
  return 500;
}

async function runAdminScript(args: string[]): Promise<ApiPayload> {
  const { stdout } = await execFileAsync(
    pythonExecutable,
    [adminScript, ...args],
    {
      cwd: repoRoot,
      maxBuffer: MAX_BUFFER_BYTES,
    }
  );

  return JSON.parse(stdout) as ApiPayload;
}

export const runtime = "nodejs";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const provisionalId = url.searchParams.get("provisionalId");
  const query = url.searchParams.get("query");
  const reviewStatus = url.searchParams.get("reviewStatus");
  const limit = Number(url.searchParams.get("limit") || "25");

  try {
    const payload = provisionalId
      ? await runAdminScript(["load", "--provisional-id", provisionalId])
      : await runAdminScript([
          "search",
          ...(query ? ["--query", query] : []),
          ...(reviewStatus ? ["--review-status", reviewStatus] : []),
          "--limit",
          String(Number.isFinite(limit) ? limit : 25),
        ]);

    return NextResponse.json(payload, { status: buildStatusCode(payload) });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        error_type: "admin_route_execution_error",
        message:
          error instanceof Error
            ? error.message
            : "Failed to execute provisional cell admin route.",
      },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as {
      action?: string;
      provisionalId?: string;
      decision?: string;
      actor?: string;
      reviewNotes?: string[];
      correctedFields?: Record<string, unknown>;
      requiredFieldWaivers?: string[];
      reviewer?: string;
      finalCellId?: string | null;
      promotionNotes?: string[];
      replaceExisting?: boolean;
    };

    let payload: ApiPayload;

    if (body.action === "review") {
      payload = await runAdminScript([
        "review",
        "--provisional-id",
        String(body.provisionalId || ""),
        "--decision",
        String(body.decision || ""),
        "--actor",
        String(body.actor || ""),
        "--review-notes-json",
        JSON.stringify(body.reviewNotes ?? []),
        "--corrected-fields-json",
        JSON.stringify(body.correctedFields ?? {}),
        "--required-field-waivers-json",
        JSON.stringify(body.requiredFieldWaivers ?? []),
      ]);
    } else if (body.action === "promote") {
      payload = await runAdminScript([
        "promote",
        "--provisional-id",
        String(body.provisionalId || ""),
        "--reviewer",
        String(body.reviewer || ""),
        ...(body.finalCellId ? ["--final-cell-id", body.finalCellId] : []),
        "--promotion-notes-json",
        JSON.stringify(body.promotionNotes ?? []),
        ...(body.replaceExisting ? ["--replace-existing"] : []),
      ]);
    } else {
      return NextResponse.json(
        {
          status: "error",
          error_type: "unsupported_admin_action",
          message: "Supported actions are review and promote.",
        },
        { status: 400 }
      );
    }

    return NextResponse.json(payload, { status: buildStatusCode(payload) });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        error_type: "admin_route_execution_error",
        message:
          error instanceof Error
            ? error.message
            : "Failed to execute provisional cell admin action.",
      },
      { status: 500 }
    );
  }
}
