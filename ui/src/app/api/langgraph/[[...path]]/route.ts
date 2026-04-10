import { NextRequest, NextResponse } from "next/server";
import {
  applyGuestQuotaHeaders,
  buildGuestQuotaError,
  consumeGuestUsage,
  getGuestQuotaContext,
  shouldCountGuestUsage,
} from "@/lib/server/guestQuota";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_LOCAL_LANGGRAPH_API_URL = "http://127.0.0.1:2026";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

type JsonRecord = Record<string, unknown>;

function getUpstreamBaseUrl(): string | null {
  const configuredUrl =
    process.env.LANGGRAPH_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_DEPLOYMENT_URL?.trim();

  if (configuredUrl) {
    return configuredUrl;
  }

  return process.env.NODE_ENV === "production"
    ? null
    : DEFAULT_LOCAL_LANGGRAPH_API_URL;
}

function buildUpstreamUrl(pathSegments: string[], request: NextRequest): URL {
  const upstreamBaseUrl = getUpstreamBaseUrl();
  if (!upstreamBaseUrl) {
    throw new Error(
      "LANGGRAPH_API_URL is not configured. Set it in the UI deployment environment."
    );
  }

  const upstreamUrl = new URL(upstreamBaseUrl);
  const incomingUrl = new URL(request.url);
  const normalizedBasePath = upstreamUrl.pathname.replace(/\/+$/, "");
  const pathSuffix =
    pathSegments.length > 0
      ? `/${pathSegments.map((segment) => encodeURIComponent(segment)).join("/")}`
      : "";

  upstreamUrl.pathname = `${normalizedBasePath}${pathSuffix}` || "/";
  upstreamUrl.search = incomingUrl.search;
  return upstreamUrl;
}

function buildUpstreamHeaders(request: NextRequest): Headers {
  const headers = new Headers();

  request.headers.forEach((value, key) => {
    const normalizedKey = key.toLowerCase();
    if (
      normalizedKey === "host" ||
      normalizedKey === "connection" ||
      normalizedKey === "cookie" ||
      normalizedKey === "content-length" ||
      normalizedKey === "transfer-encoding" ||
      normalizedKey === "x-api-key"
    ) {
      return;
    }

    headers.set(key, value);
  });

  const apiKey = process.env.LANGGRAPH_API_KEY?.trim();
  if (apiKey) {
    headers.set("X-Api-Key", apiKey);
  }

  return headers;
}

function buildResponseHeaders(headers: Headers): Headers {
  const nextHeaders = new Headers(headers);
  nextHeaders.delete("content-length");
  nextHeaders.delete("connection");
  nextHeaders.delete("transfer-encoding");
  nextHeaders.set("Cache-Control", "no-store");
  return nextHeaders;
}

function tryParseJsonBody(request: NextRequest, bodyBuffer: Buffer | null): unknown {
  if (!bodyBuffer || bodyBuffer.length === 0) {
    return null;
  }

  const contentType = request.headers.get("content-type")?.toLowerCase() || "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return JSON.parse(bodyBuffer.toString("utf-8"));
  } catch {
    return null;
  }
}

function isJsonRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function getThreadIdFromPath(pathSegments: string[]): string | null {
  if (pathSegments[0] !== "threads") {
    return null;
  }

  const candidate = pathSegments[1];
  if (!candidate || candidate === "search") {
    return null;
  }

  return decodeURIComponent(candidate);
}

function getThreadIdFromPayload(payload: unknown): string | null {
  if (!isJsonRecord(payload)) {
    return null;
  }

  if (typeof payload.thread_id === "string" && payload.thread_id.trim()) {
    return payload.thread_id.trim();
  }

  const checkpoint = payload.checkpoint;
  if (
    isJsonRecord(checkpoint) &&
    typeof checkpoint.thread_id === "string" &&
    checkpoint.thread_id.trim()
  ) {
    return checkpoint.thread_id.trim();
  }

  return null;
}

function getGuestIdFromThreadPayload(payload: unknown): string | null {
  if (!isJsonRecord(payload)) {
    return null;
  }

  const metadata = payload.metadata;
  if (!isJsonRecord(metadata)) {
    return null;
  }

  return typeof metadata.guest_id === "string" && metadata.guest_id.trim()
    ? metadata.guest_id.trim()
    : null;
}

function addGuestMetadataToPayload(
  payload: unknown,
  pathSegments: string[],
  method: string,
  guestId: string | null
): unknown {
  if (!guestId || !isJsonRecord(payload)) {
    return payload;
  }

  const touchesThreadSearch =
    pathSegments[0] === "threads" && pathSegments[1] === "search";
  const touchesThreadOrRunWrite =
    ["POST", "PUT", "PATCH"].includes(method) &&
    (pathSegments[0] === "threads" || pathSegments[0] === "runs");

  if (!touchesThreadSearch && !touchesThreadOrRunWrite) {
    return payload;
  }

  const existingMetadata = isJsonRecord(payload.metadata)
    ? payload.metadata
    : {};

  if (existingMetadata.guest_id === guestId) {
    return payload;
  }

  return {
    ...payload,
    metadata: {
      ...existingMetadata,
      guest_id: guestId,
    },
  };
}

async function fetchThreadForOwnershipCheck(
  threadId: string,
  request: NextRequest
): Promise<unknown | null> {
  const upstreamUrl = buildUpstreamUrl(["threads", threadId], request);
  const upstreamResponse = await fetch(upstreamUrl, {
    method: "GET",
    headers: buildUpstreamHeaders(request),
    cache: "no-store",
    redirect: "manual",
  });

  if (upstreamResponse.status === 404) {
    return null;
  }

  if (!upstreamResponse.ok) {
    throw new Error(
      `Failed to validate thread ownership before proxying (${upstreamResponse.status}).`
    );
  }

  return upstreamResponse.json();
}

async function ensureGuestOwnsThread(
  threadId: string,
  guestId: string | null,
  request: NextRequest,
  guestQuotaContext: ReturnType<typeof getGuestQuotaContext>
): Promise<Response | null> {
  if (!guestId) {
    return null;
  }

  const threadPayload = await fetchThreadForOwnershipCheck(threadId, request);
  const threadGuestId = getGuestIdFromThreadPayload(threadPayload);

  if (threadGuestId && threadGuestId === guestId) {
    return null;
  }

  const headers = new Headers();
  applyGuestQuotaHeaders(headers, guestQuotaContext, null);
  return NextResponse.json(
    {
      error: "Thread not found.",
    },
    {
      status: 404,
      headers,
    }
  );
}

async function proxyRequest(
  request: NextRequest,
  context: RouteContext
): Promise<Response> {
  try {
    const { path = [] } = await context.params;
    const upstreamUrl = buildUpstreamUrl(path, request);
    const bodyBuffer =
      request.method === "GET" || request.method === "HEAD"
        ? null
        : Buffer.from(await request.arrayBuffer());
    const parsedBody = tryParseJsonBody(request, bodyBuffer);
    const guestQuotaContext = getGuestQuotaContext(request);
    const guestId = guestQuotaContext?.guestId ?? null;
    const guardedThreadId =
      getThreadIdFromPath(path) || getThreadIdFromPayload(parsedBody);
    if (guardedThreadId) {
      const ownershipFailure = await ensureGuestOwnsThread(
        guardedThreadId,
        guestId,
        request,
        guestQuotaContext
      );
      if (ownershipFailure) {
        return ownershipFailure;
      }
    }

    const isolatedBody = addGuestMetadataToPayload(
      parsedBody,
      path,
      request.method,
      guestId
    );
    const upstreamBody =
      bodyBuffer &&
      isolatedBody !== parsedBody &&
      request.headers.get("content-type")?.toLowerCase().includes("application/json")
        ? Buffer.from(JSON.stringify(isolatedBody), "utf-8")
        : bodyBuffer;
    let guestQuotaResult = null;

    if (
      guestQuotaContext?.config.enabled &&
      shouldCountGuestUsage(request, path, isolatedBody)
    ) {
      try {
        guestQuotaResult = await consumeGuestUsage(guestQuotaContext);
        if (!guestQuotaResult.allowed) {
          const headers = new Headers();
          applyGuestQuotaHeaders(headers, guestQuotaContext, guestQuotaResult);
          return NextResponse.json(
            {
              error: buildGuestQuotaError(guestQuotaResult),
            },
            {
              status: 429,
              headers,
            }
          );
        }
      } catch (error) {
        console.error(
          "Guest quota check failed; allowing LangGraph request to continue.",
          error
        );
      }
    }

    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers: buildUpstreamHeaders(request),
      body: upstreamBody ?? undefined,
      cache: "no-store",
      redirect: "manual",
    });

    const responseHeaders = buildResponseHeaders(upstreamResponse.headers);
    applyGuestQuotaHeaders(responseHeaders, guestQuotaContext, guestQuotaResult);

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to proxy LangGraph request.",
      },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}
