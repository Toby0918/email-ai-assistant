/* global EmailAssistantRender */
const fields = {
  subject: document.querySelector("#subject"),
  from: document.querySelector("#from"),
  to: document.querySelector("#to"),
  sentAt: document.querySelector("#sent-at"),
  attachmentsInput: document.querySelector("#attachments-input"),
  body: document.querySelector("#body"),
  status: document.querySelector("#status"),
  fallbackBanner: document.querySelector("#fallback-banner"),
  conclusion: document.querySelector("#work-conclusion"),
  currentRequest: document.querySelector("#work-current-request"),
  nextSteps: document.querySelector("#work-next-steps"),
  keyFacts: document.querySelector("#work-key-facts"),
  mustCheck: document.querySelector("#work-must-check"),
  technicalDetails: document.querySelector("#technical-details"),
  priority: document.querySelector("#priority"),
  summary: document.querySelector("#summary"),
  category: document.querySelector("#category"),
  engine: document.querySelector("#engine"),
  decisionBrief: document.querySelector("#decision-brief"),
  conversationTimeline: document.querySelector("#conversation-timeline"),
  attachmentInsights: document.querySelector("#attachment-insights"),
  attachments: document.querySelector("#attachments-preview"),
  attachmentsPreview: document.querySelector("#attachments-preview"),
  risks: document.querySelector("#risks"),
  actions: document.querySelector("#actions"),
  draft: document.querySelector("#draft"),
  draftBody: document.querySelector("#draft"),
  draftSubject: document.querySelector("#draft-subject"),
  draftReviewStatus: document.querySelector("#draft-review-status"),
  draftReviewReasons: document.querySelector("#draft-review-reasons"),
  analyzeButton: document.querySelector("#analyze-button"),
  copyButton: document.querySelector("#copy-draft-button"),
};

const ANALYZE_TIMEOUT_MS = 60000;
const ANALYZING_STATUS = "正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。";
const ANALYSIS_ERROR_STATUSES = Object.freeze({
  LOCAL_ANALYSIS_TIMEOUT: "本地分析服务超时，请重试。",
  INVALID_LOCAL_RESPONSE: "本地分析服务返回无效结果，请重试。",
  LOCAL_HTTP_ERROR: "本地分析服务请求失败，请重试。",
});
let analysisGeneration = 0;

fields.analyzeButton.addEventListener("click", async () => {
  const generation = ++analysisGeneration;
  fields.analyzeButton.disabled = true;
  try {
    EmailAssistantRender.clearAnalysis(fields);
    fields.status.textContent = ANALYZING_STATUS;
    const attachments = parseAttachmentList(fields.attachmentsInput.value);
    EmailAssistantRender.renderAttachments(fields.attachmentsPreview, attachments);
    const data = await requestLocalAnalysis({
      user_confirmed: true,
      subject: fields.subject.value,
      from: fields.from.value,
      to: splitAddressList(fields.to.value),
      sent_at: fields.sentAt.value,
      body_text: fields.body.value,
      attachments,
    });
    if (generation !== analysisGeneration) {
      return;
    }
    if (!data || !data.ok || !data.analysis || typeof data.analysis !== "object") {
      EmailAssistantRender.clearAnalysis(fields);
      fields.status.textContent = safeAnalysisErrorStatus(data && data.error);
      return;
    }
    EmailAssistantRender.renderAnalysis(fields, data.analysis);
    fields.status.textContent = "分析完成";
  } catch (error) {
    if (generation === analysisGeneration) {
      EmailAssistantRender.clearAnalysis(fields);
      fields.status.textContent = "Local analysis service unavailable";
    }
  } finally {
    if (generation === analysisGeneration) {
      fields.analyzeButton.disabled = false;
    }
  }
});

fields.copyButton.addEventListener("click", async () => {
  const draft = fields.draftBody.value.trim();
  if (!draft) {
    fields.status.textContent = "No draft to copy";
    return;
  }
  try {
    await navigator.clipboard.writeText(fields.draftBody.value);
    fields.status.textContent = "Draft copied";
  } catch (error) {
    fields.status.textContent = "Copy failed";
  }
});

async function requestLocalAnalysis(payload) {
  const controller = typeof window.AbortController === "function"
    ? new window.AbortController()
    : null;
  const options = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  if (controller) {
    options.signal = controller.signal;
  }
  const request = (async () => {
    const response = await fetch("/api/analyze-current-email", options);
    return response.json();
  })();
  try {
    return await withLocalBackendDeadline(request, controller);
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

function withLocalBackendDeadline(promise, controller) {
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
    }, ANALYZE_TIMEOUT_MS);
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

function splitAddressList(value) {
  return String(value || "")
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseAttachmentList(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((line) => parseAttachmentLine(line))
    .filter(Boolean);
}

function parseAttachmentLine(line) {
  const text = String(line || "").trim();
  if (!text) {
    return null;
  }
  const match = text.match(/^(.+\.(pdf|docx?|xlsx?|pptx?|csv|zip|rar|7z|png|jpe?g|gif|txt))(?:\s*\(([^)]+)\))?$/i);
  if (!match) {
    return { filename: text, size: "", type: "" };
  }
  return {
    filename: match[1].trim(),
    size: String(match[3] || "").trim(),
    type: String(match[2] || "").toLowerCase(),
  };
}

function safeAnalysisErrorStatus(error) {
  const code = ownStringDataProperty(error, "code");
  return Object.prototype.hasOwnProperty.call(ANALYSIS_ERROR_STATUSES, code)
    ? ANALYSIS_ERROR_STATUSES[code]
    : "分析未完成，请重试。";
}

function ownStringDataProperty(value, key) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "";
  }
  try {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return descriptor && Object.prototype.hasOwnProperty.call(descriptor, "value") &&
      typeof descriptor.value === "string"
      ? descriptor.value
      : "";
  } catch (error) {
    return "";
  }
}
