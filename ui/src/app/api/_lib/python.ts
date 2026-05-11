import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const VERSION_CHECK_TIMEOUT_MS = 3_000;
const VERSION_CHECK_BUFFER_BYTES = 64 * 1024;

function isPathLike(candidate: string): boolean {
  return (
    path.isAbsolute(candidate) ||
    candidate.includes("/") ||
    candidate.includes("\\") ||
    candidate.startsWith(".")
  );
}

function uniqueCandidates(candidates: Array<string | undefined>): string[] {
  const seen = new Set<string>();
  const resolved: string[] = [];

  for (const candidate of candidates) {
    const trimmed = candidate?.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    resolved.push(trimmed);
  }

  return resolved;
}

async function canRunPython(candidate: string): Promise<boolean> {
  if (isPathLike(candidate) && !fs.existsSync(candidate)) {
    return false;
  }

  try {
    await execFileAsync(candidate, ["--version"], {
      maxBuffer: VERSION_CHECK_BUFFER_BYTES,
      timeout: VERSION_CHECK_TIMEOUT_MS,
      windowsHide: true,
    });
    return true;
  } catch {
    return false;
  }
}

export function resolveRepoRoot(): string {
  const cwd = process.cwd();
  return path.basename(cwd).toLowerCase() === "ui" ? path.resolve(cwd, "..") : cwd;
}

export function buildPythonCandidates(repoRoot = resolveRepoRoot()): string[] {
  return uniqueCandidates([
    process.env.BATTERY_LAB_PYTHON,
    process.env.PYTHON,
    process.env.VIRTUAL_ENV
      ? path.join(
          process.env.VIRTUAL_ENV,
          process.platform === "win32" ? "Scripts\\python.exe" : "bin/python"
        )
      : undefined,
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
    path.join(repoRoot, ".venv", "bin", "python"),
    "/usr/bin/python3",
    "/usr/local/bin/python3",
    "/usr/bin/python",
    ...(process.platform === "win32"
      ? ["py.exe", "py", "python.exe", "python"]
      : ["python3", "python"]),
  ]);
}

export async function resolvePythonExecutable(
  repoRoot = resolveRepoRoot()
): Promise<string | null> {
  for (const candidate of buildPythonCandidates(repoRoot)) {
    if (await canRunPython(candidate)) {
      return candidate;
    }
  }

  return null;
}

export function buildPythonUnavailableMessage(featureName: string): string {
  return [
    `${featureName} needs a Python runtime.`,
    "Set BATTERY_LAB_PYTHON to a usable Python executable,",
    "or run the backend bootstrap so .venv is available.",
  ].join(" ");
}
