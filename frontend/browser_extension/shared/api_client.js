(function () {
  const ANALYZE_URL = "http://127.0.0.1:8765/api/analyze-current-email";

  async function analyzeCurrentEmail(payload) {
    const email = payload || {};
    const response = await fetch(ANALYZE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_confirmed: true,
        subject: stringValue(email.subject),
        from: stringValue(email.from),
        to: stringList(email.to),
        sent_at: stringValue(email.sent_at),
        body_text: stringValue(email.body_text),
        attachments: projectItems(email.attachments, ["filename", "size", "type"]),
        thread_segments: projectItems(email.thread_segments, [
          "position",
          "from",
          "to",
          "sent_at",
          "timestamp_text",
          "subject",
          "body_text",
        ]),
        attachment_files: projectItems(email.attachment_files, [
          "filename",
          "type",
          "size",
          "content_base64",
        ]),
        resource_limitations: projectItems(email.resource_limitations, [
          "filename",
          "type",
          "size",
          "limitation",
        ]),
      }),
    });

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
