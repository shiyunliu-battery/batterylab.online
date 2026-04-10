import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";
import { createClient } from "redis";

const DEFAULT_COOKIE_NAME = "batterylab_guest";
const DEFAULT_WINDOW_DAYS = 30;
const DEFAULT_USAGE_LIMIT = 20;
const DEFAULT_KEY_PREFIX = "guest_usage";
const DEFAULT_TIMEOUT_MS = 1500;
const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

type GuestQuotaConfig = {
  enabled: boolean;
  cookieName: string;
  cookieSecret: string | null;
  keyPrefix: string;
  redisUrl: string | null;
  limit: number;
  windowSeconds: number;
  timeoutMs: number;
};

export type GuestQuotaContext = {
  config: GuestQuotaConfig;
  guestId: string | null;
  setCookieHeader: string | null;
};

export type GuestQuotaResult = {
  allowed: boolean;
  used: number;
  remaining: number;
  limit: number;
  ttlSeconds: number;
};

type ConnectedRedisClient = ReturnType<typeof createClient>;

let redisClientPromise: Promise<ConnectedRedisClient> | null = null;

function getWindowSeconds(rawValue: string | undefined): number {
  const parsedDays = Number(rawValue ?? DEFAULT_WINDOW_DAYS);
  const normalizedDays = Number.isFinite(parsedDays) && parsedDays > 0 ? parsedDays : DEFAULT_WINDOW_DAYS;
  return Math.round(normalizedDays * 24 * 60 * 60);
}

function getGuestQuotaConfig(): GuestQuotaConfig {
  const rawLimit = Number(process.env.GUEST_USAGE_LIMIT ?? DEFAULT_USAGE_LIMIT);
  const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.floor(rawLimit) : 0;
  const rawTimeoutMs = Number(process.env.GUEST_USAGE_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS);
  const timeoutMs =
    Number.isFinite(rawTimeoutMs) && rawTimeoutMs > 0
      ? Math.floor(rawTimeoutMs)
      : DEFAULT_TIMEOUT_MS;
  const redisUrl =
    process.env.REDIS_URL?.trim() ||
    process.env.AZURE_REDIS_URL?.trim() ||
    null;

  return {
    enabled: limit > 0,
    cookieName: process.env.GUEST_USAGE_COOKIE_NAME?.trim() || DEFAULT_COOKIE_NAME,
    cookieSecret: process.env.GUEST_USAGE_COOKIE_SECRET?.trim() || null,
    keyPrefix: process.env.GUEST_USAGE_KEY_PREFIX?.trim() || DEFAULT_KEY_PREFIX,
    redisUrl,
    limit,
    windowSeconds: getWindowSeconds(process.env.GUEST_USAGE_WINDOW_DAYS),
    timeoutMs,
  };
}

function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  message: string
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(message));
    }, timeoutMs);

    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      }
    );
  });
}

function signGuestId(guestId: string, secret: string): string {
  return createHmac("sha256", secret).update(guestId).digest("hex");
}

function decodeGuestCookie(rawValue: string, secret: string | null): string | null {
  const normalized = rawValue.trim();
  if (!normalized) {
    return null;
  }

  if (!secret) {
    return UUID_REGEX.test(normalized) ? normalized : null;
  }

  const [guestId, signature] = normalized.split(".", 2);
  if (!guestId || !signature || !UUID_REGEX.test(guestId)) {
    return null;
  }

  const expectedSignature = signGuestId(guestId, secret);
  const actualBuffer = Buffer.from(signature);
  const expectedBuffer = Buffer.from(expectedSignature);

  if (actualBuffer.length !== expectedBuffer.length) {
    return null;
  }

  return timingSafeEqual(actualBuffer, expectedBuffer) ? guestId : null;
}

function encodeGuestCookie(guestId: string, secret: string | null): string {
  if (!secret) {
    return guestId;
  }
  return `${guestId}.${signGuestId(guestId, secret)}`;
}

function buildSetCookieHeader(config: GuestQuotaConfig, guestId: string): string {
  const cookieValue = encodeGuestCookie(guestId, config.cookieSecret);
  const parts = [
    `${config.cookieName}=${cookieValue}`,
    "Path=/",
    `Max-Age=${config.windowSeconds}`,
    "HttpOnly",
    "SameSite=Lax",
  ];

  if (process.env.NODE_ENV === "production") {
    parts.push("Secure");
  }

  return parts.join("; ");
}

function getRedisClient(config: GuestQuotaConfig): Promise<ConnectedRedisClient> {
  if (!config.redisUrl) {
    throw new Error("REDIS_URL must be configured when GUEST_USAGE_LIMIT is enabled.");
  }

  if (!redisClientPromise) {
    const client = createClient({
      url: config.redisUrl,
      socket: {
        connectTimeout: config.timeoutMs,
        reconnectStrategy(retries) {
          return Math.min(retries * 200, 2_000);
        },
      },
    });
    redisClientPromise = withTimeout(
      client.connect().then(() => client),
      config.timeoutMs,
      "Timed out connecting to Redis for guest usage tracking."
    ).catch(async (error) => {
      redisClientPromise = null;
      try {
        client.destroy();
      } catch {
        // Best-effort cleanup.
      }
      throw error;
    });
  }

  return redisClientPromise;
}

function containsHumanMessage(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some((entry) => containsHumanMessage(entry));
  }

  if (!value || typeof value !== "object") {
    return false;
  }

  const record = value as Record<string, unknown>;

  if (
    record.type === "human" &&
    ("content" in record || "metadata" in record)
  ) {
    return true;
  }

  return Object.values(record).some((entry) => containsHumanMessage(entry));
}

export function getGuestQuotaContext(request: NextRequest): GuestQuotaContext | null {
  const config = getGuestQuotaConfig();
  const rawCookie = request.cookies.get(config.cookieName)?.value ?? "";
  const decodedGuestId = decodeGuestCookie(rawCookie, config.cookieSecret);
  const guestId = decodedGuestId || randomUUID();

  return {
    config,
    guestId,
    setCookieHeader:
      decodedGuestId === guestId ? null : buildSetCookieHeader(config, guestId),
  };
}

export function shouldCountGuestUsage(
  request: NextRequest,
  pathSegments: string[],
  payload: unknown
): boolean {
  if (request.method !== "POST") {
    return false;
  }

  const normalizedPath = pathSegments.join("/").toLowerCase();
  if (normalizedPath.includes("search") || normalizedPath.includes("history")) {
    return false;
  }

  return containsHumanMessage(payload);
}

export async function consumeGuestUsage(
  context: GuestQuotaContext
): Promise<GuestQuotaResult> {
  if (!context.guestId) {
    throw new Error("Guest usage tracking requires a resolved guest identifier.");
  }

  const { config, guestId } = context;
  const client = await getRedisClient(config);
  const key = `${config.keyPrefix}:${guestId}`;

  return withTimeout(
    (async () => {
      const used = await client.incr(key);
      if (used === 1) {
        await client.expire(key, config.windowSeconds);
      }

      const ttl = await client.ttl(key);
      return {
        allowed: used <= config.limit,
        used,
        remaining: Math.max(config.limit - used, 0),
        limit: config.limit,
        ttlSeconds: Math.max(ttl, 0),
      };
    })(),
    config.timeoutMs,
    "Timed out consuming guest usage from Redis."
  );
}

export function applyGuestQuotaHeaders(
  headers: Headers,
  context: GuestQuotaContext | null,
  result: GuestQuotaResult | null
): void {
  if (!context) {
    return;
  }

  headers.set("Cache-Control", "no-store");
  if (context.config.enabled) {
    headers.set("X-Guest-Usage-Limit", String(context.config.limit));
    headers.set(
      "X-Guest-Usage-Window-Seconds",
      String(context.config.windowSeconds)
    );

    if (result) {
      headers.set("X-Guest-Usage-Used", String(result.used));
      headers.set("X-Guest-Usage-Remaining", String(result.remaining));
    }
  }

  if (context.setCookieHeader) {
    headers.append("Set-Cookie", context.setCookieHeader);
  }
}

export function buildGuestQuotaError(result: GuestQuotaResult): string {
  return [
    `Guest usage limit reached.`,
    `This public preview allows ${result.limit} submitted messages per visitor in the current usage window.`,
    `Please try again later or contact the site owner for full access.`,
  ].join(" ");
}
