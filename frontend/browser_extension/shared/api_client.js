(function () {
  const ANALYZE_URL = "http://127.0.0.1:8765/api/analyze-current-email";

  async function analyzeCurrentEmail(payload) {
    const email = payload || {};
    const response = await fetch(ANALYZE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_confirmed: true,
        subject: email.subject || "",
        from: email.from || "",
        to: Array.isArray(email.to) ? email.to : [],
        sent_at: email.sent_at || "",
        body_text: email.body_text || "",
        attachments: Array.isArray(email.attachments) ? email.attachments : [],
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

  window.EmailAssistantApi = {
    analyzeCurrentEmail,
  };
})();
