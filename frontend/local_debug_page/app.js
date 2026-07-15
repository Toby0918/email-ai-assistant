const fields = {
  subject: document.querySelector("#subject"),
  from: document.querySelector("#from"),
  to: document.querySelector("#to"),
  sentAt: document.querySelector("#sent-at"),
  attachmentsInput: document.querySelector("#attachments-input"),
  body: document.querySelector("#body"),
  status: document.querySelector("#status"),
  priority: document.querySelector("#priority"),
  summary: document.querySelector("#summary"),
  category: document.querySelector("#category"),
  engine: document.querySelector("#engine"),
  decisionBrief: document.querySelector("#decision-brief"),
  conversationTimeline: document.querySelector("#conversation-timeline"),
  attachmentInsights: document.querySelector("#attachment-insights"),
  attachmentsPreview: document.querySelector("#attachments-preview"),
  risks: document.querySelector("#risks"),
  actions: document.querySelector("#actions"),
  draft: document.querySelector("#draft"),
  analyzeButton: document.querySelector("#analyze-button"),
  copyButton: document.querySelector("#copy-draft-button"),
};

const ANALYZE_TIMEOUT_MS = 15000;
let analysisGeneration = 0;

const PRIORITY_LABELS = {
  urgent: "紧急",
  high: "高",
  normal: "普通",
  low: "低",
};

const CATEGORY_LABELS = {
  customer_inquiry: "客户询问",
  order_followup: "订单/交付跟进",
  payment: "付款/发票",
  contract: "合同/条款",
  complaint: "投诉/质量异常",
  new_product_development: "新品开发/成本优化",
  internal: "内部事项",
  marketing: "营销/参考资料",
  unknown: "未知",
};

const RISK_LABELS = {
  payment_risk: "付款风险",
  delivery_risk: "交付/物流风险",
  contract_risk: "合同风险",
  quality_risk: "质量风险",
  security_risk: "安全风险",
  commitment_risk: "承诺风险",
  prompt_injection_risk: "提示注入风险",
};

const RISK_LEVEL_LABELS = {
  high: "高",
  medium: "中",
  low: "低",
};

const ACTION_LABELS = {
  confirm: "确认",
  check_inventory: "核查库存",
  check_delivery: "核查交付",
  prepare_quote: "准备报价",
  escalate: "升级处理",
  wait: "等待信息",
  ignore: "无需处理",
  reply: "准备回复",
};

const TIMELINE_STATUS_LABELS = {
  resolved: "已解决",
  partially_resolved: "部分解决",
  unresolved: "未解决",
  unknown: "状态未知",
};

const ATTACHMENT_TYPE_LABELS = {
  image: "图片",
  pdf: "PDF",
  xlsx: "XLSX",
  docx: "DOCX",
  unsupported: "不支持的类型",
};

const ATTACHMENT_STATUS_LABELS = {
  parsed: "已解析",
  metadata_only: "仅元数据",
  unavailable: "不可用",
  failed: "解析失败",
};

const ATTACHMENT_REDACTION = "[已隐藏链接或路径]";
const ATTACHMENT_URI_MARKER_PATTERN = /(^|[^A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*:[^\s]/i;
const ATTACHMENT_WINDOWS_PATH_MARKER_PATTERN = /(^|[^A-Za-z0-9])[A-Za-z]:[\\/]/;
const ATTACHMENT_UNC_PATH_MARKER_PATTERN = /\\\\/;
const ATTACHMENT_POSIX_PATH_MARKER_PATTERN = /(^|[\s="'(=：])\/[A-Za-z0-9._-]/;

fields.analyzeButton.addEventListener("click", async () => {
  const generation = ++analysisGeneration;
  fields.analyzeButton.disabled = true;
  try {
    clearAnalysis();
    fields.status.textContent = "Analyzing";
    const attachments = parseAttachmentList(fields.attachmentsInput.value);
    fields.attachmentsPreview.textContent = formatAttachments(attachments);
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
    if (!data.ok) {
      clearAnalysis();
      fields.status.textContent = data.error?.message || "Analysis failed";
      return;
    }
    renderAnalysis(data.analysis);
    fields.status.textContent = `Saved #${data.saved_id}`;
  } catch (error) {
    if (generation === analysisGeneration) {
      clearAnalysis();
      fields.status.textContent = "Local analysis service unavailable";
    }
  } finally {
    if (generation === analysisGeneration) {
      fields.analyzeButton.disabled = false;
    }
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

fields.copyButton.addEventListener("click", async () => {
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

function renderAnalysis(analysis) {
  fields.priority.textContent = formatPriority(analysis.priority);
  fields.summary.textContent = textOrFallback(analysis.summary, "No summary returned");
  fields.category.textContent = formatCategory(analysis.category);
  fields.engine.textContent = formatEngine(analysis.analysis_engine);
  fields.decisionBrief.textContent = formatDecisionBrief(analysis.decision_brief);
  renderConversationTimeline(fields.conversationTimeline, analysis.conversation_timeline);
  renderAttachmentInsights(fields.attachmentInsights, analysis.attachment_insights);
  fields.risks.textContent = formatList(analysis.risk_flags, formatRisk);
  fields.actions.textContent = formatList(analysis.suggested_actions, formatAction);
  fields.draft.value = analysis.reply_draft && analysis.reply_draft.body ? analysis.reply_draft.body : "";
}

function clearAnalysis() {
  fields.priority.textContent = "-";
  fields.summary.textContent = "No analysis yet";
  fields.category.textContent = "-";
  fields.engine.textContent = "-";
  fields.decisionBrief.textContent = "-";
  renderSafePlaceholder(fields.conversationTimeline, "暂无会话进度");
  renderSafePlaceholder(fields.attachmentInsights, "暂无附件洞察");
  fields.attachmentsPreview.textContent = "-";
  fields.risks.textContent = "-";
  fields.actions.textContent = "-";
  fields.draft.value = "";
}

function splitAddressList(value) {
  return value
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

function formatAttachments(value) {
  if (!Array.isArray(value) || value.length === 0) {
    return "-";
  }
  return value
    .map((item) => {
      if (!isPlainObject(item)) {
        return textOrFallback(item, "");
      }
      const filename = textOrFallback(item.filename, "");
      const details = [textOrFallback(item.size, ""), textOrFallback(item.type, "")]
        .filter(Boolean)
        .join(", ");
      return filename && details ? `${filename} (${details})` : filename;
    })
    .filter(Boolean)
    .join(", ") || "-";
}

function renderConversationTimeline(field, timeline) {
  if (!isPlainObject(timeline)) {
    renderSafePlaceholder(field, "暂无会话进度");
    return;
  }
  const items = [
    safeStructuredItem("前情", [
      safeDetailLine("", safeDisplayText(timeline.previous_context, "暂无可用前情")),
    ]),
    safeStructuredItem("当前状态", [
      safeDetailLine("状态", TIMELINE_STATUS_LABELS[timeline.current_status] || "状态未知"),
      safeDetailLine("原因", safeDisplayText(timeline.status_reason, "未提供状态说明")),
    ]),
    safeStructuredItem("最新外部请求", [
      safeDetailLine("", safeDisplayText(timeline.latest_external_request, "暂无明确外部请求")),
    ]),
    safeStructuredItem("最新内部承诺", [
      safeDetailLine("", safeDisplayText(timeline.latest_internal_commitment, "暂无明确内部承诺")),
    ]),
    safeStructuredItem("置信度", [
      safeDetailLine("", formatTimelineConfidence(timeline.confidence)),
    ]),
  ];
  const openItems = Array.isArray(timeline.open_items)
    ? timeline.open_items.filter(isPlainObject)
    : [];
  if (openItems.length === 0) {
    items.push(safeStructuredItem("待办事项", [safeDetailLine("", "暂无未解决事项")]));
  } else {
    openItems.forEach((item, index) => {
      items.push(formatTimelineOpenItem(item, index));
    });
  }
  renderSafeItems(field, items, "暂无会话进度");
}

function formatTimelineOpenItem(item, index) {
  const source = {
    thread: "会话",
    attachment: "附件",
  }[item.source] || "未注明";
  return safeStructuredItem("待办 " + (index + 1), [
    safeDetailLine("事项", safeDisplayText(item.item, "未提供事项说明")),
    safeDetailLine("负责人", safeDisplayText(item.owner_hint, "未指定")),
    safeDetailLine("期限", safeDisplayText(item.due_hint, "未指定")),
    safeDetailLine("来源", source),
  ]);
}

function formatTimelineConfidence(value) {
  return {
    high: "高",
    medium: "中",
    low: "低",
  }[value] || "未知";
}

function renderAttachmentInsights(field, insights) {
  if (!Array.isArray(insights)) {
    renderSafePlaceholder(field, "暂无附件洞察");
    return;
  }
  const items = insights.map(formatAttachmentInsight).filter(Boolean);
  renderSafeItems(field, items, "暂无附件洞察");
}

function formatAttachmentInsight(insight) {
  if (!isPlainObject(insight)) {
    return null;
  }
  const status = ATTACHMENT_STATUS_LABELS[insight.status] || "状态未知";
  const summaryFallback = insight.status === "parsed" ? "未提供解析摘要" : "暂无可用摘要";
  const facts = safeAttachmentStringList(insight.key_facts);
  const limitations = safeAttachmentStringList(insight.limitations);
  const lines = [
    safeDetailLine("类型", ATTACHMENT_TYPE_LABELS[insight.type] || safeDisplayText(insight.type, "未知类型")),
    safeDetailLine("状态", status),
    safeDetailLine("摘要", safeAttachmentText(insight.summary, summaryFallback)),
  ];
  if (facts.length === 0) {
    lines.push(safeDetailLine("关键事实", "暂无关键事实"));
  } else {
    facts.forEach((fact, index) => lines.push(safeDetailLine("关键事实 " + (index + 1), fact)));
  }
  if (limitations.length === 0) {
    const fallback = insight.status === "parsed"
      ? "无已知解析限制"
      : "未提供限制说明，需人工核查";
    lines.push(safeDetailLine("限制", fallback));
  } else {
    limitations.forEach((limitation, index) => lines.push(safeDetailLine("限制 " + (index + 1), limitation)));
  }
  return safeStructuredItem(safeDisplayText(insight.filename, "未命名附件"), lines);
}

function safeAttachmentStringList(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => safeAttachmentText(item, "")).filter(Boolean);
}

function safeAttachmentText(value, fallback) {
  const text = safeDisplayText(value, "");
  if (!text) {
    return fallback;
  }
  return containsAttachmentPrivateReference(text) ? ATTACHMENT_REDACTION : text;
}

function containsAttachmentPrivateReference(text) {
  return ATTACHMENT_URI_MARKER_PATTERN.test(text) ||
    ATTACHMENT_WINDOWS_PATH_MARKER_PATTERN.test(text) ||
    ATTACHMENT_UNC_PATH_MARKER_PATTERN.test(text) ||
    ATTACHMENT_POSIX_PATH_MARKER_PATTERN.test(text);
}

function safeDisplayText(value, fallback) {
  if (typeof value !== "string" && typeof value !== "number") {
    return fallback;
  }
  const text = String(value).trim();
  return text || fallback;
}

function safeStructuredItem(title, lines) {
  return { title, lines: lines.filter((line) => line.text) };
}

function safeDetailLine(label, text) {
  return { label, text: safeDisplayText(text, "") };
}

function renderSafeItems(field, items, fallback) {
  if (items.length === 0) {
    renderSafePlaceholder(field, fallback);
    return;
  }
  if (typeof field.replaceChildren !== "function") {
    field.textContent = items.map(plainTextForSafeItem).join("\n\n");
    return;
  }
  field.replaceChildren(...items.map(renderSafeItem));
}

function plainTextForSafeItem(item) {
  return [
    item.title,
    ...item.lines.map((line) => line.label ? line.label + "：" + line.text : line.text),
  ].filter(Boolean).join("\n");
}

function renderSafeItem(item) {
  const wrapper = document.createElement("div");
  wrapper.className = "analysis-list__item";
  const title = document.createElement("div");
  title.className = "analysis-list__item-title";
  title.textContent = item.title;
  wrapper.appendChild(title);
  item.lines.forEach((line) => {
    const lineElement = document.createElement("div");
    lineElement.className = "analysis-list__line";
    if (line.label) {
      const label = document.createElement("span");
      label.className = "analysis-list__label";
      label.textContent = line.label + "：";
      lineElement.appendChild(label);
    }
    lineElement.appendChild(document.createTextNode(line.text));
    wrapper.appendChild(lineElement);
  });
  return wrapper;
}

function renderSafePlaceholder(field, text) {
  if (typeof field.replaceChildren === "function") {
    field.replaceChildren();
  }
  field.textContent = text;
}

function formatDecisionBrief(value) {
  if (!isPlainObject(value)) {
    return "-";
  }
  const parts = [
    textOrFallback(value.one_line_conclusion, ""),
    value.requested_outcome ? `目的：${value.requested_outcome}` : "",
    formatDecisionSteps(value.next_steps),
    formatKeyFacts(value.key_facts),
    formatStringList("必须核查", value.must_check),
    formatStringList("缺失信息", value.missing_info),
    formatReplyRecommendation(value.reply_recommendation),
  ].filter(Boolean);
  return parts.join("\n") || "-";
}

function formatDecisionSteps(value) {
  if (!Array.isArray(value) || value.length === 0) {
    return "";
  }
  return `当前动作：${value.map((item) => textOrFallback(item.step, "")).filter(Boolean).join("；")}`;
}

function formatKeyFacts(value) {
  if (!Array.isArray(value) || value.length === 0) {
    return "";
  }
  const facts = value
    .map((item) => `${textOrFallback(item.label, "事实")}=${textOrFallback(item.value, "")}`)
    .filter((item) => !item.endsWith("="));
  return facts.length ? `关键事实：${facts.join("；")}` : "";
}

function formatStringList(label, value) {
  if (!Array.isArray(value) || value.length === 0) {
    return "";
  }
  return `${label}：${value.map((item) => textOrFallback(item, "")).filter(Boolean).join("；")}`;
}

function formatReplyRecommendation(value) {
  if (!isPlainObject(value)) {
    return "";
  }
  return value.reason ? `回复建议：${value.reason}` : "";
}

function formatList(value, formatter) {
  if (!Array.isArray(value) || value.length === 0) {
    return "-";
  }
  return value.map((item) => formatter(item)).filter(Boolean).join(", ") || "-";
}

function formatRisk(item) {
  if (!isPlainObject(item)) {
    return textOrFallback(item, "");
  }

  const type = formatRiskType(item.type);
  const level = formatRiskLevel(item.level);
  const evidence = textOrFallback(item.evidence, "");
  if (type && level) {
    return evidence ? `${type}（${level}）：${evidence}` : `${type}（${level}）`;
  }
  return type || evidence;
}

function formatAction(item) {
  if (!isPlainObject(item)) {
    return textOrFallback(item, "");
  }

  return textOrFallback(item.description, "") || formatActionType(item.type);
}

function formatEngine(value) {
  if (!isPlainObject(value)) {
    return textOrFallback(value, "-");
  }
  return textOrFallback(value.label, "-");
}

function formatPriority(value) {
  const text = textOrFallback(value, "");
  return text ? PRIORITY_LABELS[text] || text : "-";
}

function formatCategory(value) {
  const text = textOrFallback(value, "");
  return text ? CATEGORY_LABELS[text] || text : "-";
}

function formatRiskType(value) {
  const text = textOrFallback(value, "");
  return text ? RISK_LABELS[text] || text : "";
}

function formatRiskLevel(value) {
  const text = textOrFallback(value, "");
  return text ? RISK_LEVEL_LABELS[text] || text : "";
}

function formatActionType(value) {
  const text = textOrFallback(value, "");
  return text ? ACTION_LABELS[text] || text : "";
}

function isPlainObject(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function textOrFallback(value, fallback) {
  const text = String(value || "").trim();
  return text || fallback;
}
