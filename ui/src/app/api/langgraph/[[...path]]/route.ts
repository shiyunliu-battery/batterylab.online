import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const DEFAULT_LOCAL_LANGGRAPH_API_URL = "http://127.0.0.1:2026";

type RouteContext = {
  params: Promise<{
    path?: string[];
  }>;
};

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

async function proxyRequest(
  request: NextRequest,
  context: RouteContext
): Promise<Response> {
  try {
    const { path = [] } = await context.params;
    const upstreamUrl = buildUpstreamUrl(path, request);
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await request.arrayBuffer();

    const upstreamResponse = await fetch(upstreamUrl, {
      method: request.method,
      headers: buildUpstreamHeaders(request),
      body,
      cache: "no-store",
      redirect: "manual",
    });

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: buildResponseHeaders(upstreamResponse.headers),
    });
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to proxy LangGraph request.",
      },
      { status: 500 }
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
