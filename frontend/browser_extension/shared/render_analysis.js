(function () {
  function renderAnalysis(fields, analysis) {
    fields.priority.textContent = textOrDash(analysis.priority);
    fields.summary.textContent = textOrFallback(analysis.summary, "No summary returned");
    fields.category.textContent = textOrDash(analysis.category);
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

    const type = textOrFallback(item.type, "");
    const level = textOrFallback(item.level, "");
    if (type && level) {
      return `${type} (${level})`;
    }
    return type || textOrFallback(item.evidence, "");
  }

  function formatAction(item) {
    if (!isPlainObject(item)) {
      return textOrFallback(item, "");
    }

    return textOrFallback(item.description, "") || textOrFallback(item.type, "");
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
