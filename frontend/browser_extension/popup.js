/* global EmailAssistantApi, EmailAssistantRender, chrome */
const fields = {
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
  attachments: document.querySelector("#attachments"),
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
const STALE_EMAIL_MESSAGE = "Email changed; analyze again";
let analysisGeneration = 0;
let renderedMessageContext = null;

document.querySelector("#analyze-button").addEventListener("click", analyzeCurrentMessage);

async function analyzeCurrentMessage() {
  const generation = ++analysisGeneration;
  renderedMessageContext = null;
  setBusy(true, "Reading current email");
  try {
    EmailAssistantRender.clearAnalysis(fields);
    const extraction = await requestCurrentEmail();
    if (generation !== analysisGeneration) {
      return;
    }
    if (!extraction.ok) {
      fields.status.textContent = extraction.error ||
        "Open a Tencent Exmail message or select email body text from that opened message first";
      return;
    }
    const messageContext = contextFromExtraction(extraction);
    if (!messageContext) {
      showStaleState(generation);
      return;
    }
    if (fields.attachments) {
      EmailAssistantRender.renderAttachments(fields.attachments, extraction.payload.attachments);
    }

    setBusy(true, "Analyzing");
    const data = await EmailAssistantApi.analyzeCurrentEmail(extraction.payload);
    if (generation !== analysisGeneration) {
      return;
    }
    if (!data || !data.ok) {
      const message = data && data.error ? data.error.message : "";
      fields.status.textContent = message || "Analysis failed";
      return;
    }
    if (!data.analysis || typeof data.analysis !== "object") {
      fields.status.textContent = "Invalid analysis response";
      return;
    }
    if (!await revalidateMessageContext(messageContext)) {
      showStaleState(generation);
      return;
    }
    if (generation !== analysisGeneration) {
      return;
    }
    EmailAssistantRender.renderAnalysis(fields, data.analysis);
    renderedMessageContext = messageContext;
    fields.status.textContent = "分析完成";
  } catch (error) {
    if (generation === analysisGeneration) {
      fields.status.textContent = "Local analysis service unavailable. Please try again";
    }
  } finally {
    if (generation === analysisGeneration) {
      fields.analyzeButton.disabled = false;
    }
  }
}

document.querySelector("#copy-draft-button").addEventListener("click", async () => {
  const draft = fields.draft.value.trim();
  if (!draft) {
    fields.status.textContent = "No draft to copy";
    return;
  }

  const generation = analysisGeneration;
  const messageContext = renderedMessageContext;
  if (
    !messageContext ||
    !await revalidateMessageContext(messageContext) ||
    generation !== analysisGeneration ||
    renderedMessageContext !== messageContext
  ) {
    showStaleState(generation);
    return;
  }

  try {
    await navigator.clipboard.writeText(fields.draft.value);
    fields.status.textContent = "Draft copied";
  } catch (error) {
    fields.status.textContent = "Copy failed";
  }
});

async function requestCurrentEmail() {
  let tabs;
  try {
    tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  } catch (error) {
    return { ok: false, error: "Open a Tencent Exmail tab first" };
  }

  const tab = tabs && tabs[0];
  if (!tab || !tab.id || !tab.url || !tab.url.startsWith("https://exmail.qq.com/")) {
    return { ok: false, error: "Open a Tencent Exmail tab first" };
  }

  try {
    const extraction = await chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_CURRENT_EMAIL" });
    return { ...extraction, tab_id: tab.id };
  } catch (error) {
    return {
      ok: false,
      error: "Open a Tencent Exmail message or select email body text from that opened message first",
    };
  }
}

function contextFromExtraction(extraction) {
  if (
    !Number.isInteger(extraction.tab_id) ||
    typeof extraction.message_fingerprint !== "string" ||
    !/^msg-v1-[a-f0-9]{16}$/.test(extraction.message_fingerprint)
  ) {
    return null;
  }
  return {
    tabId: extraction.tab_id,
    fingerprint: extraction.message_fingerprint,
  };
}

async function revalidateMessageContext(messageContext) {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs && tabs[0];
    if (
      !tab ||
      tab.id !== messageContext.tabId ||
      !tab.url ||
      !tab.url.startsWith("https://exmail.qq.com/")
    ) {
      return false;
    }
    const result = await chrome.tabs.sendMessage(tab.id, {
      type: "REVALIDATE_CURRENT_EMAIL",
    });
    return Boolean(
      result &&
      result.ok === true &&
      result.message_fingerprint === messageContext.fingerprint,
    );
  } catch (error) {
    return false;
  }
}

function showStaleState(generation) {
  if (generation !== analysisGeneration) {
    return;
  }
  renderedMessageContext = null;
  EmailAssistantRender.clearAnalysis(fields);
  fields.status.textContent = STALE_EMAIL_MESSAGE;
}

function setBusy(isBusy, message) {
  fields.analyzeButton.disabled = isBusy;
  fields.status.textContent = message;
}
