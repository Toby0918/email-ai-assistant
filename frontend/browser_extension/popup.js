/* global EmailAssistantApi, EmailAssistantRender, EmailAssistantManualAttachmentFiles, chrome */
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
  manualAttachmentInput: document.querySelector("#manual-attachment-files"),
};
const STALE_EMAIL_MESSAGE = "Email changed; analyze again";
const ANALYZING_STATUS = "正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。";
const ANALYSIS_ERROR_STATUSES = Object.freeze({
  LOCAL_ANALYSIS_TIMEOUT: "本地分析服务超时，请重试。",
  INVALID_LOCAL_RESPONSE: "本地分析服务返回无效结果，请重试。",
  LOCAL_HTTP_ERROR: "本地分析服务请求失败，请重试。",
});
let analysisGeneration = 0;
let renderedMessageContext = null;

document.querySelector("#analyze-button").addEventListener("click", analyzeCurrentMessage);

async function analyzeCurrentMessage() {
  const generation = ++analysisGeneration;
  let manualResult = null;
  let mergedResult = null;
  let analysisPayload = null;
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
    if (!hasUsableExtractedBody(extraction)) {
      fields.status.textContent = "Current email body could not be read. Reopen the email and try again.";
      return;
    }
    const messageContext = contextFromExtraction(extraction);
    if (!messageContext) {
      showStaleState(generation);
      return;
    }
    manualResult = await readManualAttachmentFiles();
    if (generation !== analysisGeneration) {
      return;
    }
    mergedResult = mergeCurrentAttachmentFiles(
      manualResult.attachment_files,
      extractedArray(extraction.payload, "attachment_files"),
      [
        ...manualResult.resource_limitations,
        ...extractedArray(extraction.payload, "resource_limitations"),
      ],
    );
    analysisPayload = {
      ...extraction.payload,
      attachment_files: mergedResult.attachment_files,
      resource_limitations: mergedResult.resource_limitations,
    };

    if (!await revalidateMessageContext(messageContext)) {
      showStaleState(generation);
      return;
    }
    if (generation !== analysisGeneration) {
      return;
    }

    setBusy(true, ANALYZING_STATUS);
    const data = await EmailAssistantApi.analyzeCurrentEmail(analysisPayload);
    if (generation !== analysisGeneration) {
      return;
    }
    if (!data || !data.ok) {
      fields.status.textContent = safeAnalysisErrorStatus(data && data.error);
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
    if (fields.attachments) {
      EmailAssistantRender.renderAttachments(
        fields.attachments,
        attachmentMetadataForRender(extraction.payload, mergedResult.attachment_files),
      );
    }
    EmailAssistantRender.renderAnalysis(fields, data.analysis);
    renderedMessageContext = messageContext;
    fields.status.textContent = "分析完成";
  } catch (error) {
    if (generation === analysisGeneration) {
      fields.status.textContent = "Local analysis service unavailable. Please try again";
    }
  } finally {
    clearManualAttachmentSelection();
    manualResult = null;
    mergedResult = null;
    analysisPayload = null;
    if (generation === analysisGeneration) {
      fields.analyzeButton.disabled = false;
      if (fields.manualAttachmentInput) {
        fields.manualAttachmentInput.disabled = false;
      }
    }
  }
}

function mergeCurrentAttachmentFiles(manualFiles, automaticFiles, limitations) {
  if (
    typeof EmailAssistantManualAttachmentFiles !== "object" ||
    typeof EmailAssistantManualAttachmentFiles.mergeAttachmentFiles !== "function"
  ) {
    return {
      attachment_files: Array.isArray(automaticFiles) ? automaticFiles.slice() : [],
      resource_limitations: Array.isArray(limitations) ? limitations.slice() : [],
    };
  }
  return EmailAssistantManualAttachmentFiles.mergeAttachmentFiles(
    manualFiles,
    automaticFiles,
    limitations,
  );
}

async function readManualAttachmentFiles() {
  const input = fields.manualAttachmentInput;
  const files = input && input.files;
  if (!files || !Number.isSafeInteger(files.length) || files.length <= 0) {
    return { attachment_files: [], resource_limitations: [] };
  }
  if (
    typeof EmailAssistantManualAttachmentFiles !== "object" ||
    typeof EmailAssistantManualAttachmentFiles.readSelectedFiles !== "function"
  ) {
    throw new Error("Manual attachment reader is unavailable.");
  }
  return EmailAssistantManualAttachmentFiles.readSelectedFiles(files);
}

function clearManualAttachmentSelection() {
  if (fields.manualAttachmentInput) {
    fields.manualAttachmentInput.value = "";
  }
}

function extractedArray(payload, key) {
  return payload && Array.isArray(payload[key]) ? payload[key] : [];
}

function attachmentMetadataForRender(payload, attachmentFiles) {
  const projected = [];
  const seen = new Set();
  for (const item of [
    ...extractedArray(payload, "attachments"),
    ...(Array.isArray(attachmentFiles) ? attachmentFiles : []),
  ]) {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      continue;
    }
    const filename = typeof item.filename === "string" ? item.filename : "";
    const type = typeof item.type === "string" ? item.type : "";
    const size = ["string", "number"].includes(typeof item.size) ? item.size : "";
    const key = [filename.toLowerCase(), type.toLowerCase(), String(size)].join("\u0000");
    if (!filename || seen.has(key)) {
      continue;
    }
    seen.add(key);
    projected.push({ filename, type, size });
  }
  return projected;
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

function hasUsableExtractedBody(extraction) {
  return Boolean(
    extraction &&
    extraction.payload &&
    typeof extraction.payload === "object" &&
    typeof extraction.payload.body_text === "string" &&
    extraction.payload.body_text.trim()
  );
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
  if (fields.manualAttachmentInput) {
    fields.manualAttachmentInput.disabled = isBusy;
  }
  fields.status.textContent = message;
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
