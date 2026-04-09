import { spawn } from "node:child_process";
import path from "node:path";
import { NextResponse } from "next/server";

const repoRoot = path.resolve(process.cwd(), "..");
const pythonExecutable =
  process.platform === "win32"
    ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
    : path.join(repoRoot, ".venv", "bin", "python");
const registerScript = path.join(
  repoRoot,
  "scripts",
  "register_uploaded_cell_datasheet.py"
);

type ApiPayload = {
  status?: string;
  error_type?: string;
  message?: string;
  [key: string]: unknown;
};

function buildStatusCode(payload: ApiPayload): number {
  if (payload.status !== "error") return 200;
  if (payload.error_type === "invalid_json_payload") return 400;
  if (payload.error_type?.includes("validation")) return 400;
  return 500;
}

async function runRegistrationScript(payload: Record<string, unknown>): Promise<ApiPayload> {
  return await new Promise<ApiPayload>((resolve, reject) => {
    const child = spawn(pythonExecutable, [registerScript], {
      cwd: repoRoot,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0 && !stdout.trim()) {
        reject(
          new Error(
            stderr.trim() || `Registration script exited with code ${code}.`
          )
        );
        return;
      }

      try {
        resolve(JSON.parse(stdout) as ApiPayload);
      } catch (error) {
        reject(
          new Error(
            error instanceof Error
              ? error.message
              : "Failed to parse registration payload."
          )
        );
      }
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as {
      filePath?: string;
      attachmentText?: string;
      submittedBy?: string;
      submitForReview?: boolean;
    };

    const payload = await runRegistrationScript({
      file_path: String(body.filePath || ""),
      attachment_text: String(body.attachmentText || ""),
      submitted_by: String(body.submittedBy || "chat_user"),
      submit_for_review: Boolean(body.submitForReview ?? true),
    });

    return NextResponse.json(payload, { status: buildStatusCode(payload) });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        error_type: "admin_route_execution_error",
        message:
          error instanceof Error
            ? error.message
            : "Failed to register uploaded datasheet.",
      },
      { status: 500 }
    );
  }
}
