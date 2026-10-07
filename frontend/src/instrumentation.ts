import type { Instrumentation } from "next";

export const onRequestError: Instrumentation.onRequestError = async (error) => {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { captureServerError } = await import("./lib/server-error-tracking");
    await captureServerError(error);
  }
};
