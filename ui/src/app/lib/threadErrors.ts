const MISSING_THREAD_TOAST_MESSAGE =
  "This thread is no longer available. Switched back to a new chat.";

function getErrorText(error: unknown): string {
  if (typeof error === "string") {
    return error.toLowerCase();
  }

  if (error && typeof error === "object") {
    const message =
      typeof (error as { message?: unknown }).message === "string"
        ? (error as { message: string }).message
        : "";
    const text =
      typeof (error as { text?: unknown }).text === "string"
        ? (error as { text: string }).text
        : "";

    return `${message} ${text}`.trim().toLowerCase();
  }

  return "";
}

function hasHttpStatus(error: unknown, status: number): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    typeof (error as { status?: unknown }).status === "number" &&
    (error as { status: number }).status === status
  );
}

export function isMissingThreadError(error: unknown): boolean {
  const text = getErrorText(error);

  if (hasHttpStatus(error, 404)) {
    return text.includes("thread") && text.includes("not found");
  }

  return (
    text.includes("http 404") &&
    text.includes("thread") &&
    text.includes("not found")
  );
}

export function isProviderAuthenticationError(error: unknown): boolean {
  const text = getErrorText(error);

  return (
    text.includes("authenticationerror") ||
    text.includes("invalid_api_key") ||
    text.includes("incorrect api key") ||
    text.includes("401 unauthorized")
  );
}

const PROVIDER_AUTH_TOAST_MESSAGE =
  "OpenAI API key is missing or invalid. Update OPENAI_API_KEY in .env, then restart the backend.";

export { MISSING_THREAD_TOAST_MESSAGE, PROVIDER_AUTH_TOAST_MESSAGE };
