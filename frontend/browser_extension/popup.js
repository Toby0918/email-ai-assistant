/* global EmailAssistantApi, EmailAssistantRender, chrome */
const fields = {
  status: document.querySelector("#status"),
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
  analyzeButton: document.querySelector("#analyze-button"),
  copyButton: document.querySelector("#copy-draft-button"),
};

document.querySelector("#analyze-button").addEventListener("click", analyzeCurrentMessage);

async function analyzeCurrentMessage() {
  setBusy(true, "Reading current email");
  try {
    EmailAssistantRender.clearAnalysis(fields);
    const extraction = await requestCurrentEmail();
    if (!extraction.ok) {
      fields.status.textContent = extraction.error ||
        "Open a Tencent Exmail message or select email body text from that opened message first";
      return;
    }
    if (fields.attachments) {
      EmailAssistantRender.renderAttachments(fields.attachments, extraction.payload.attachments);
    }

    setBusy(true, "Analyzing");
    const data = await EmailAssistantApi.analyzeCurrentEmail(extraction.payload);
    if (!data || !data.ok) {
      const message = data && data.error ? data.error.message : "";
      fields.status.textContent = message || "Analysis failed";
      return;
    }
    if (!data.analysis || typeof data.analysis !== "object") {
      fields.status.textContent = "Invalid analysis response";
      return;
    }
    EmailAssistantRender.renderAnalysis(fields, data.analysis);
    fields.status.textContent = `Saved #${data.saved_id || data.request_id || "-"}`;
  } catch (error) {
    fields.status.textContent = "Local analysis service unavailable. Please try again";
  } finally {
    fields.analyzeButton.disabled = false;
  }
}

document.querySelector("#copy-draft-button").addEventListener("click", async () => {
  const draft = fields.draft.value.trim();
  if (!draft) {
    fields.status.textContent = "No draft to copy";
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
    return await chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_CURRENT_EMAIL" });
  } catch (error) {
    return {
      ok: false,
      error: "Open a Tencent Exmail message or select email body text from that opened message first",
    };
  }
}

function setBusy(isBusy, message) {
  fields.analyzeButton.disabled = isBusy;
  fields.status.textContent = message;
}
