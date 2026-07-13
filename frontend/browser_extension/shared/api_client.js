(function () {
  const ANALYZE_URL = "http://127.0.0.1:8765/api/analyze-current-email";
  const MAX_ANALYZE_TIMEOUT_MS = 35000;
  const FRONTEND_RESOURCE_LIMITATION_CODES = new Set([
    "unsupported_type",
    "frontend_limit",
    "resource_unavailable",
    "resource_read_failed",
    "collection_timeout",
    "candidate_omission",
  ]);

  async function analyzeCurrentEmail(payload, options) {
    const email = payload || {};
    const controller = typeof window.AbortController === "function"
      ? new window.AbortController()
      : null;
    const timeoutMs = boundedTimeout(options && options.timeoutMs);
    const request = requestAnalysis(email, controller);
    try {
      return await withBackendDeadline(request, timeoutMs, controller);
    } catch (error) {
      if (error && error.name === "BackendDeadlineError") {
        return {
          ok: false,
          error: {
            code: "LOCAL_ANALYSIS_TIMEOUT",
            message: "Local analysis service timed out. Please try again.",
            retryable: true,
          },
        };
      }
      throw error;
    }
  }

  async function requestAnalysis(email, controller) {
    const requestOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody(email)),
    };
    if (controller) {
      requestOptions.signal = controller.signal;
    }
    const response = await fetch(ANALYZE_URL, requestOptions);

    let data;
    try {
      data = await response.json();
    } catch (error) {
      return {
        ok: false,
        error: {
          code: "INVALID_LOCAL_RESPONSE",
          message: "Local analysis service returned invalid JSON.",
        },
      };
    }

    if (!response.ok && data.ok !== false) {
      return {
        ok: false,
        error: {
          code: "LOCAL_HTTP_ERROR",
          message: `Local analysis service returned HTTP ${response.status}.`,
        },
      };
    }

    return data;
  }

  function requestBody(email) {
    return {
      user_confirmed: true,
      subject: stringValue(email.subject),
      from: stringValue(email.from),
      to: stringList(email.to),
      sent_at: stringValue(email.sent_at),
      body_text: stringValue(email.body_text),
      attachments: projectItems(email.attachments, ["filename", "size", "type"]),
      thread_segments: projectItems(email.thread_segments, [
        "position", "from", "to", "sent_at", "timestamp_text", "subject", "body_text",
      ]),
      attachment_files: projectItems(email.attachment_files, [
        "filename", "type", "size", "content_base64",
      ]),
      resource_limitations: projectResourceLimitations(email.resource_limitations),
    };
  }

  function withBackendDeadline(promise, timeoutMs, controller) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const timer = window.setTimeout(() => {
        if (settled) {
          return;
        }
        settled = true;
        if (controller) {
          controller.abort();
        }
        const error = new Error("Local analysis deadline expired.");
        error.name = "BackendDeadlineError";
        reject(error);
      }, timeoutMs);
      Promise.resolve(promise).then(
        (value) => {
          if (!settled) {
            settled = true;
            window.clearTimeout(timer);
            resolve(value);
          }
        },
        (error) => {
          if (!settled) {
            settled = true;
            window.clearTimeout(timer);
            reject(error);
          }
        },
      );
    });
  }

  function boundedTimeout(value) {
    return Number.isSafeInteger(value) && value > 0
      ? Math.min(value, MAX_ANALYZE_TIMEOUT_MS)
      : MAX_ANALYZE_TIMEOUT_MS;
  }

  function projectItems(value, allowedFields) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .filter((item) => item && typeof item === "object" && !Array.isArray(item))
      .map((item) => {
        const projected = {};
        for (const field of allowedFields) {
          projected[field] = Object.prototype.hasOwnProperty.call(item, field)
            ? primitiveValue(item[field])
            : "";
        }
        return projected;
      });
  }

  function projectResourceLimitations(value) {
    return projectItems(value, ["code", "filename", "type", "size", "limitation"])
      .filter((item) => FRONTEND_RESOURCE_LIMITATION_CODES.has(item.code));
  }

  function stringValue(value) {
    return typeof value === "string" ? value : "";
  }

  function stringList(value) {
    return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
  }

  function primitiveValue(value) {
    return ["string", "number", "boolean"].includes(typeof value) ? value : "";
  }

  window.EmailAssistantApi = {
    analyzeCurrentEmail,
  };
})();
