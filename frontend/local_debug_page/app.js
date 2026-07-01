const fields = {
  subject: document.querySelector("#subject"),
  from: document.querySelector("#from"),
  to: document.querySelector("#to"),
  sentAt: document.querySelector("#sent-at"),
  body: document.querySelector("#body"),
  status: document.querySelector("#status"),
  priority: document.querySelector("#priority"),
  summary: document.querySelector("#summary"),
  category: document.querySelector("#category"),
  risks: document.querySelector("#risks"),
  actions: document.querySelector("#actions"),
  draft: document.querySelector("#draft"),
  copyButton: document.querySelector("#copy-draft-button"),
};

document.querySelector("#analyze-button").addEventListener("click", async () => {
  clearAnalysis();
  fields.status.textContent = "Analyzing";
  let data;
  try {
    const response = await fetch("/api/analyze-current-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_confirmed: true,
        subject: fields.subject.value,
        from: fields.from.value,
        to: splitAddressList(fields.to.value),
        sent_at: fields.sentAt.value,
        body_text: fields.body.value,
      }),
    });
    data = await response.json();
  } catch (error) {
    clearAnalysis();
    fields.status.textContent = "Local analysis service unavailable";
    return;
  }
  if (!data.ok) {
    clearAnalysis();
    fields.status.textContent = data.error?.message || "Analysis failed";
    return;
  }
  renderAnalysis(data.analysis);
  fields.status.textContent = `Saved #${data.saved_id}`;
});

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
  fields.priority.textContent = analysis.priority;
  fields.summary.textContent = analysis.summary;
  fields.category.textContent = analysis.category;
  fields.risks.textContent = analysis.risk_flags.map((item) => item.type).join(", ") || "none";
  fields.actions.textContent = analysis.suggested_actions.map((item) => item.description).join(" ");
  fields.draft.value = analysis.reply_draft.body;
}

function clearAnalysis() {
  fields.priority.textContent = "-";
  fields.summary.textContent = "No analysis yet";
  fields.category.textContent = "-";
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
