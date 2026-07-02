(function () {
  function renderAnalysis(fields, analysis) {
    fields.priority.textContent = textOrDash(analysis.priority);
    fields.summary.textContent = textOrFallback(analysis.summary, "No summary returned");
    fields.category.textContent = textOrDash(analysis.category);
    fields.risks.textContent = formatList(analysis.risk_flags);
    fields.actions.textContent = formatList(analysis.suggested_actions);
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

  function formatList(value) {
    if (!Array.isArray(value) || value.length === 0) {
      return "-";
    }
    return value.map((item) => String(item).trim()).filter(Boolean).join(", ") || "-";
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
