/* global EmailAssistantApi, EmailAssistantRender, chrome */
const fields = {
  status: document.querySelector("#status"),
  priority: document.querySelector("#priority"),
  summary: document.querySelector("#summary"),
  category: document.querySelector("#category"),
  risks: document.querySelector("#risks"),
  actions: document.querySelector("#actions"),
  draft: document.querySelector("#draft"),
  analyzeButton: document.querySelector("#analyze-button"),
  copyButton: document.querySelector("#copy-draft-button"),
};

document.querySelector("#analyze-button").addEventListener("click", async () => {
  EmailAssistantRender.clearAnalysis(fields);
  setBusy(true, "Reading current email");

  const extraction = await requestCurrentEmail();
  if (!extraction.ok) {
    setBusy(false, extraction.error || "Open a Tencent Exmail message or select email body text from that opened message first");
    return;
  }

  setBusy(true, "Analyzing");
  let data;
  try {
    data = await EmailAssistantApi.analyzeCurrentEmail(extraction.payload);
  } catch (error) {
    setBusy(false, "Local analysis service unavailable");
    return;
  }

  if (!data || !data.ok) {
    const message = data && data.error ? data.error.message : "";
    setBusy(false, message || "Analysis failed");
    return;
  }

  if (!data.analysis || typeof data.analysis !== "object") {
    setBusy(false, "Invalid analysis response");
    return;
  }

  try {
    EmailAssistantRender.renderAnalysis(fields, data.analysis);
  } catch (error) {
    setBusy(false, "Analysis failed");
    return;
  }

  setBusy(false, `Saved #${data.saved_id || data.request_id || "-"}`);
});

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
