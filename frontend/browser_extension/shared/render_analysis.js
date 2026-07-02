(function () {
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
    complaint: "投诉/质量",
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

  function renderAnalysis(fields, analysis) {
    fields.priority.textContent = formatPriority(analysis.priority);
    fields.summary.textContent = textOrFallback(analysis.summary, "No summary returned");
    fields.category.textContent = formatCategory(analysis.category);
    fields.risks.textContent = formatList(analysis.risk_flags, formatRisk);
    fields.actions.textContent = formatList(analysis.suggested_actions, formatAction);
    fields.draft.value = analysis.reply_draft && analysis.reply_draft.body ? analysis.reply_draft.body : "";
  }

  function clearAnalysis(fields) {
    fields.priority.textContent = "-";
    fields.summary.textContent = "No analysis yet";
    fields.category.textContent = "-";
    fields.risks.textContent = "-";
    fields.actions.textContent = "-";
    fields.draft.value = "";
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

  function textOrDash(value) {
    return textOrFallback(value, "-");
  }

  function textOrFallback(value, fallback) {
    const text = String(value || "").trim();
    return text || fallback;
  }

  window.EmailAssistantRender = {
    renderAnalysis,
    clearAnalysis,
  };
})();
