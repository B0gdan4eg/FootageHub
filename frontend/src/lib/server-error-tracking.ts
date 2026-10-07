import { PostHog, type EventMessage } from "posthog-node";

let client: PostHog | undefined;
const recent = new Map<string, number[]>();

export function sanitizeServerError(event: EventMessage | null): EventMessage | null {
  if (!event || event.event !== "$exception") return null;
  const properties = event.properties || {};
  const list = Array.isArray(properties.$exception_list) ? properties.$exception_list : [];
  const exceptions = list.slice(0, 5).map((item) => {
    const frames = Array.isArray(item?.stacktrace?.frames) ? item.stacktrace.frames : [];
    return {
      type: String(item?.type || "Error").slice(0, 100),
      value: String(item?.type || "Error").slice(0, 100),
      stacktrace: {
        type: "raw",
        frames: frames.slice(-50).map((frame: Record<string, unknown>) => ({
          filename: String(frame.filename || "unknown").split(/[\\/]/).pop(),
          function: String(frame.function || "unknown").slice(0, 100),
          lineno: typeof frame.lineno === "number" ? frame.lineno : undefined,
          colno: typeof frame.colno === "number" ? frame.colno : undefined,
          in_app: frame.in_app === true,
        })),
      },
    };
  });
  return {
    event: "$exception", distinctId: "service:frontend", uuid: event.uuid,
    timestamp: event.timestamp, _originatedFromCaptureException: true,
    properties: {
      $exception_list: exceptions, service: "frontend", environment: "production",
      release: /^[a-f0-9]{40}$/.test(process.env.APP_REVISION || "") ? process.env.APP_REVISION : "unknown",
      $process_person_profile: false, $geoip_disable: true, $is_server: true,
    },
  };
}

export async function captureServerError(error: unknown) {
  const token = process.env.POSTHOG_PROJECT_TOKEN || "";
  if (process.env.POSTHOG_ERROR_TRACKING_ENABLED === "0" || !/^phc_[A-Za-z0-9_-]+$/.test(token)) return;
  const kind = error instanceof Error ? error.name : "Error";
  const now = Date.now();
  const timestamps = (recent.get(kind) || []).filter((value) => now - value < 60000);
  if (timestamps.length >= 5 || (recent.size >= 100 && !recent.has(kind))) return;
  recent.set(kind, [...timestamps, now]);
  if (!client) client = new PostHog(token, {
    host: "https://eu.i.posthog.com", before_send: sanitizeServerError,
    enableExceptionAutocapture: false, flushAt: 1, flushInterval: 0,
    requestTimeout: 3000, fetchRetryCount: 1, disableGeoip: true,
  });
  try {
    await client.captureExceptionImmediate(error, "service:frontend");
  } catch {
    console.warn("Server error tracking could not send an exception");
  }
}
