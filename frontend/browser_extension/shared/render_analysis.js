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

  const OWNER_LABELS = {
    sales: "销售负责人",
    internal_sales: "销售负责人",
    engineering: "工程负责人",
    engineering_owner: "工程负责人",
    quality: "质量负责人",
    quality_owner: "质量负责人",
    finance: "财务负责人",
    operations: "运营负责人",
    internal_follow_up: "跟进负责人",
    "采购/工程负责人": "采购/工程负责人",
  };

  const DEEPSEEK_FALLBACK_REASON = "OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。";
  const RULE_FALLBACK_REASON = "远程模型结果未采用，本次使用安全规则结果。";
  const UNKNOWN_ENGINE_REASON = "分析引擎信息未确认，请人工核查本次结果。";

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

  const ATTACHMENT_STATUS_AGGREGATE_LABELS = Object.freeze({
    parsed: "已解析",
    metadata_only: "仅元数据",
    unavailable: "未读取（附件不可用）",
    failed: "解析失败",
  });
  const ATTACHMENT_STATUS_ORDER = Object.freeze([
    "parsed",
    "metadata_only",
    "unavailable",
    "failed",
  ]);

  const ATTACHMENT_REDACTION = "[已隐藏链接或路径]";
  const ATTACHMENT_URI_MARKER_PATTERN = /(^|[^A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*:[^\s]/i;
  const ATTACHMENT_WINDOWS_PATH_MARKER_PATTERN = /(^|[^A-Za-z0-9])[A-Za-z]:[\\/]/;
  const ATTACHMENT_UNC_PATH_MARKER_PATTERN = /\\\\/;
  const ATTACHMENT_POSIX_PATH_MARKER_PATTERN = /(^|[\s="'(=：])\/[A-Za-z0-9._-]/;

  function renderAnalysis(fields, analysis) {
    const engine = engineSnapshot(analysis.analysis_engine);
    const presentation = enginePresentation(engine);
    renderTaskCard(fields, analysis, engine, presentation);
    setFieldText(fields.priority, formatPriority(analysis.priority));
    setFieldText(fields.summary, textOrFallback(analysis.summary, "未返回摘要"));
    setFieldText(fields.category, formatCategory(analysis.category));
    if (fields.engine) {
      fields.engine.textContent = presentation.label;
    }
    if (fields.decisionBrief) {
      renderDecisionBrief(fields.decisionBrief, analysis.decision_brief);
    }
    if (fields.conversationTimeline) {
      renderConversationTimeline(fields.conversationTimeline, analysis.conversation_timeline);
    }
    if (fields.attachmentInsights) {
      renderAttachmentInsights(fields.attachmentInsights, analysis.attachment_insights);
    }
    if (fields.attachments && Array.isArray(analysis.attachments)) {
      renderAttachments(fields.attachments, analysis.attachments);
    }
    if (fields.risks) {
      renderListField(fields.risks, analysis.risk_flags, formatRisk);
    }
    if (fields.actions) {
      renderListField(fields.actions, analysis.suggested_actions, formatAction);
    }
    renderDraft(fields, analysis.reply_draft);
  }

  function clearAnalysis(fields) {
    setFieldText(fields.priority, "-");
    setFieldText(fields.summary, "暂无分析");
    setFieldText(fields.category, "-");
    setFieldText(fields.conclusion, "暂无分析");
    setFieldText(fields.currentRequest, "-");
    renderPlaceholderIfPresent(fields.nextSteps);
    renderPlaceholderIfPresent(fields.keyFacts);
    renderPlaceholderIfPresent(fields.mustCheck);
    renderPlaceholderIfPresent(fields.technicalDetails);
    if (fields.fallbackBanner) {
      fields.fallbackBanner.hidden = true;
      fields.fallbackBanner.textContent = "";
    }
    if (fields.engine) {
      fields.engine.textContent = "-";
    }
    if (fields.decisionBrief) {
      renderPlaceholder(fields.decisionBrief);
    }
    if (fields.conversationTimeline) {
      renderPlaceholder(fields.conversationTimeline, "暂无会话进度");
    }
    if (fields.attachmentInsights) {
      renderPlaceholder(fields.attachmentInsights, "暂无附件洞察");
    }
    if (fields.attachments) {
      renderPlaceholder(fields.attachments);
    }
    renderPlaceholderIfPresent(fields.risks);
    renderPlaceholderIfPresent(fields.actions);
    setFieldValue(fields.draftBody || fields.draft, "");
    setFieldText(fields.draftSubject, "-");
    setFieldText(fields.draftReviewStatus, "需要人工审核");
    renderPlaceholderIfPresent(fields.draftReviewReasons);
  }

  function renderTaskCard(fields, analysis, engine, presentation) {
    const brief = isPlainObject(analysis.decision_brief) ? analysis.decision_brief : {};
    setFieldText(fields.conclusion, textOrFallback(
      brief.one_line_conclusion,
      textOrFallback(analysis.summary, "暂无分析结论"),
    ));
    setFieldText(fields.currentRequest, textOrFallback(brief.requested_outcome, "暂无明确请求"));
    renderTaskSteps(fields.nextSteps, brief.next_steps);
    renderTaskFacts(fields.keyFacts, brief.key_facts);
    renderMustCheck(fields.mustCheck, brief.must_check, brief.missing_info);
    renderEngineBanner(fields.fallbackBanner, presentation);
    renderTechnicalDetails(fields.technicalDetails, analysis, engine, presentation);
  }

  function renderTaskSteps(field, steps) {
    if (!field) {
      return;
    }
    const items = Array.isArray(steps)
      ? steps.filter(isPlainObject).map((item, index) => structuredItem(
        `第 ${index + 1} 步`,
        [
          detailLine("事项", textOrFallback(item.step, "")),
          detailLine("负责人", formatOwnerHint(item.owner_hint)),
          detailLine("时间", textOrFallback(item.due_hint, "未指定")),
        ],
      ))
      : [];
    renderNonLinkedItems(field, items, "暂无建议动作");
  }

  function renderTaskFacts(field, facts) {
    if (!field) {
      return;
    }
    const items = Array.isArray(facts)
      ? facts.map((item) => isPlainObject(item)
        ? structuredItem("", [detailLine(textOrFallback(item.label, "事实"), textOrFallback(item.value, ""))])
        : structuredItem("", [detailLine("", textOrFallback(item, ""))]))
      : [];
    renderNonLinkedItems(field, items, "暂无关键事实");
  }

  function renderMustCheck(field, mustCheck, missingInfo) {
    if (!field) {
      return;
    }
    const items = [];
    for (const value of Array.isArray(mustCheck) ? mustCheck : []) {
      items.push(structuredItem("", [detailLine("必须核查", textOrFallback(value, ""))]));
    }
    for (const value of Array.isArray(missingInfo) ? missingInfo : []) {
      items.push(structuredItem("", [detailLine("缺失信息", textOrFallback(value, ""))]));
    }
    renderNonLinkedItems(field, items, "暂无必须核查项");
  }

  function renderEngineBanner(field, presentation) {
    if (!field) {
      return;
    }
    const reason = presentation.fallbackReason;
    field.hidden = !reason;
    field.textContent = reason;
  }

  function renderTechnicalDetails(field, analysis, engine, presentation) {
    if (!field) {
      return;
    }
    const scope = {
      current_only: "仅当前邮件",
      relevant_history: "当前邮件与相关历史",
    }[engine.contextScope];
    const lines = [
      `优先级：${formatPriority(analysis.priority)}`,
      `分类：${formatCategory(analysis.category)}`,
      `分析引擎：${presentation.label}`,
    ];
    if (presentation.fallbackReason) {
      lines.push(`回退说明：${presentation.fallbackReason}`);
    }
    if (scope) {
      lines.push(`上下文范围：${scope}`);
    }
    if (engine.contextLimited === true) {
      lines.push("上下文受限：是");
    }
    field.textContent = lines.join("\n");
  }

  function renderDraft(fields, value) {
    const draft = isPlainObject(value) ? value : {};
    const subject = textOrFallback(draft.subject, "-");
    const body = textOrFallback(draft.body, "");
    setFieldText(fields.draftSubject, subject);
    setFieldValue(fields.draftBody || fields.draft, body);
    if (fields.draft && fields.draft !== fields.draftBody) {
      setFieldValue(fields.draft, body);
    }
    setFieldText(
      fields.draftReviewStatus,
      draft.needs_human_review === true ? "需要人工审核" : "请在使用前人工审核",
    );
    if (fields.draftReviewReasons) {
      const reasons = Array.isArray(draft.review_reasons) ? draft.review_reasons : [];
      renderNonLinkedItems(
        fields.draftReviewReasons,
        reasons.map((reason) => structuredItem("", [detailLine("", reason)])),
        "请人工核对草稿内容",
      );
    }
  }

  function setFieldText(field, value) {
    if (field) {
      field.textContent = value;
    }
  }

  function setFieldValue(field, value) {
    if (field) {
      field.value = value;
    }
  }

  function renderPlaceholderIfPresent(field, text = "-") {
    if (field) {
      renderPlaceholder(field, text);
    }
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
    const recommendation = textOrFallback(item.recommendation, "");
    const title = [type || "风险", level ? `（${level}）` : ""].join("");
    return structuredItem(title, [
      detailLine("依据", evidence),
      detailLine("建议", recommendation),
    ]);
  }

  function formatAction(item) {
    if (!isPlainObject(item)) {
      return textOrFallback(item, "");
    }

    const title = formatActionType(item.type) || "建议动作";
    return structuredItem(title, [
      detailLine("事项", textOrFallback(item.description, "")),
      detailLine("负责人", formatOwnerHint(item.owner_hint)),
      detailLine("期限", textOrFallback(item.due_hint, "")),
    ]);
  }

  function formatEngine(value) {
    return enginePresentation(engineSnapshot(value)).label;
  }

  function engineSnapshot(value) {
    return Object.freeze({
      source: ownDataProperty(value, "source", "string"),
      label: ownDataProperty(value, "label", "string"),
      contextScope: ownDataProperty(value, "context_scope", "string"),
      contextLimited: ownDataProperty(value, "context_limited", "boolean"),
    });
  }

  function ownDataProperty(value, key, expectedType) {
    if (!isPlainObject(value)) {
      return undefined;
    }
    try {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (
        !descriptor ||
        !Object.prototype.hasOwnProperty.call(descriptor, "value") ||
        typeof descriptor.value !== expectedType
      ) {
        return undefined;
      }
      return descriptor.value;
    } catch (error) {
      return undefined;
    }
  }

  function enginePresentation(value) {
    if (!isPlainObject(value)) {
      return unknownEnginePresentation();
    }
    if (value.source === "ai_model" && value.label === "OpenAI GPT-5.6 Sol") {
      return { label: "OpenAI GPT-5.6 Sol", fallbackReason: "" };
    }
    if (
      value.source === "ai_model" &&
      ["DeepSeek V4 Flash text fallback", "DeepSeek V4 Pro text fallback"].includes(value.label)
    ) {
      return { label: "DeepSeek text fallback", fallbackReason: DEEPSEEK_FALLBACK_REASON };
    }
    if (value.source === "rule_fallback" && value.label === "Rule fallback") {
      return { label: "Rule fallback", fallbackReason: RULE_FALLBACK_REASON };
    }
    return unknownEnginePresentation();
  }

  function unknownEnginePresentation() {
    return { label: "未确认分析引擎", fallbackReason: UNKNOWN_ENGINE_REASON };
  }

  function formatAttachments(value) {
    if (!Array.isArray(value) || value.length === 0) {
      return "-";
    }
    const text = value.map(formatAttachment).filter(Boolean).join(", ");
    return text || "-";
  }

  function formatAttachment(item) {
    if (!isPlainObject(item)) {
      return textOrFallback(item, "");
    }
    const filename = textOrFallback(item.filename, "");
    if (!filename) {
      return "";
    }
    const details = [textOrFallback(item.size, ""), textOrFallback(item.type, "")]
      .filter(Boolean)
      .join(", ");
    return details ? `${filename} (${details})` : filename;
  }

  function renderAttachments(field, value) {
    renderListField(field, value, formatAttachment);
  }

  function renderConversationTimeline(field, timeline) {
    if (!isPlainObject(timeline)) {
      renderPlaceholder(field, "暂无会话进度");
      return;
    }

    const items = [
      structuredItem("前情", [
        detailLine("", safeDisplayText(timeline.previous_context, "暂无可用前情")),
      ]),
      structuredItem("当前状态", [
        detailLine("状态", formatTimelineStatus(timeline.current_status)),
        detailLine("原因", safeDisplayText(timeline.status_reason, "未提供状态说明")),
      ]),
      structuredItem("最新外部请求", [
        detailLine("", safeDisplayText(timeline.latest_external_request, "暂无明确外部请求")),
      ]),
      structuredItem("最新内部承诺", [
        detailLine("", safeDisplayText(timeline.latest_internal_commitment, "暂无明确内部承诺")),
      ]),
      structuredItem("置信度", [
        detailLine("", formatTimelineConfidence(timeline.confidence)),
      ]),
    ];
    const openItems = Array.isArray(timeline.open_items)
      ? timeline.open_items.filter(isPlainObject)
      : [];
    if (openItems.length === 0) {
      items.push(structuredItem("待办事项", [detailLine("", "暂无未解决事项")]));
    } else {
      openItems.forEach((item, index) => {
        items.push(formatOpenItem(item, index));
      });
    }
    renderNonLinkedItems(field, items, "暂无会话进度");
  }

  function formatOpenItem(item, index) {
    const source = {
      thread: "会话",
      attachment: "附件",
    }[item.source] || "未注明";
    return structuredItem("待办 " + (index + 1), [
      detailLine("事项", safeDisplayText(item.item, "未提供事项说明")),
      detailLine("负责人", formatOwnerHint(item.owner_hint)),
      detailLine("期限", safeDisplayText(item.due_hint, "未指定")),
      detailLine("来源", source),
    ]);
  }

  function formatTimelineStatus(value) {
    return TIMELINE_STATUS_LABELS[value] || "状态未知";
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
      renderPlaceholder(field, "暂无附件洞察");
      return;
    }
    const items = [
      formatAttachmentStatusAggregate(insights),
      ...insights.map(formatAttachmentInsight),
    ].filter(Boolean);
    renderNonLinkedItems(field, items, "暂无附件洞察");
  }

  function formatAttachmentStatusAggregate(insights) {
    const counts = Object.fromEntries(ATTACHMENT_STATUS_ORDER.map((status) => [status, 0]));
    for (const insight of insights) {
      const status = ownDataProperty(insight, "status", "string");
      if (Object.prototype.hasOwnProperty.call(counts, status)) {
        counts[status] += 1;
      }
    }
    if (counts.metadata_only === 0 && counts.unavailable === 0) {
      return null;
    }
    const lines = ATTACHMENT_STATUS_ORDER
      .filter((status) => counts[status] > 0)
      .map((status) => detailLine(
        ATTACHMENT_STATUS_AGGREGATE_LABELS[status],
        `数量 ${counts[status]}`,
      ));
    return lines.length > 0 ? structuredItem("附件读取状态", lines) : null;
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
      detailLine("类型", formatAttachmentType(insight.type)),
      detailLine("状态", status),
      detailLine("摘要", safeAttachmentText(insight.summary, summaryFallback)),
    ];
    if (facts.length === 0) {
      lines.push(detailLine("关键事实", "暂无关键事实"));
    } else {
      facts.forEach((fact, index) => lines.push(detailLine("关键事实 " + (index + 1), fact)));
    }
    if (limitations.length === 0) {
      const fallback = insight.status === "parsed"
        ? "无已知解析限制"
        : "未提供限制说明，需人工核查";
      lines.push(detailLine("限制", fallback));
    } else {
      limitations.forEach((limitation, index) => lines.push(detailLine("限制 " + (index + 1), limitation)));
    }
    return structuredItem(safeDisplayText(insight.filename, "未命名附件"), lines);
  }

  function formatAttachmentType(value) {
    return ATTACHMENT_TYPE_LABELS[value] || safeDisplayText(value, "未知类型");
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

  function renderNonLinkedItems(field, values, fallback) {
    const items = values.map(normalizeFormattedItem).filter(Boolean);
    if (items.length === 0) {
      renderPlaceholder(field, fallback);
      return;
    }
    if (!canRenderChildren(field)) {
      field.textContent = items.map(plainTextForItem).join("\n\n");
      return;
    }

    const doc = field.ownerDocument || document;
    field.className = withClassName(field.className, "analysis-list");
    field.replaceChildren(...items.map((item) => renderFormattedItem(doc, item)));
  }

  function renderDecisionBrief(field, value) {
    const items = formatDecisionBrief(value);
    if (items.length === 0) {
      renderPlaceholder(field);
      return;
    }
    if (!canRenderChildren(field)) {
      field.textContent = items.map(plainTextForItem).join("\n\n");
      return;
    }

    const doc = field.ownerDocument || document;
    field.className = withClassName(field.className, "analysis-list");
    field.replaceChildren(...items.map((item) => renderFormattedItem(doc, item)));
  }

  function formatDecisionBrief(value) {
    if (!isPlainObject(value)) {
      return [];
    }
    const items = [];
    items.push(structuredItem("行动结论", [
      detailLine("结论", textOrFallback(value.one_line_conclusion, "")),
      detailLine("邮件目的", textOrFallback(value.requested_outcome, "")),
      detailLine("回复建议", formatReplyRecommendation(value.reply_recommendation)),
      detailLine("置信度", formatConfidence(value.confidence)),
    ]));
    if (Array.isArray(value.next_steps) && value.next_steps.length > 0) {
      items.push(structuredItem("当前动作", value.next_steps.map(formatDecisionStep).filter(Boolean)));
    }
    if (Array.isArray(value.key_facts) && value.key_facts.length > 0) {
      items.push(structuredItem("关键事实", value.key_facts.map(formatKeyFact).filter(Boolean)));
    }
    if (Array.isArray(value.must_check) && value.must_check.length > 0) {
      items.push(structuredItem("必须核查", value.must_check.map((item) => detailLine("", item)).filter(Boolean)));
    }
    if (Array.isArray(value.missing_info) && value.missing_info.length > 0) {
      items.push(structuredItem("缺失信息", value.missing_info.map((item) => detailLine("", item)).filter(Boolean)));
    }
    return items.map(normalizeFormattedItem).filter((item) => item && (item.title || item.lines.length > 0));
  }

  function formatDecisionStep(item, index) {
    if (!isPlainObject(item)) {
      return null;
    }
    const details = [
      textOrFallback(item.step, ""),
      item.owner_hint ? `负责人：${formatOwnerHint(item.owner_hint)}` : "",
      item.due_hint ? `期限：${item.due_hint}` : "",
    ].filter(Boolean).join("；");
    return detailLine(String(index + 1), details);
  }

  function formatKeyFact(item) {
    if (!isPlainObject(item)) {
      return detailLine("事实", textOrFallback(item, ""));
    }
    return detailLine(textOrFallback(item.label, "事实"), textOrFallback(item.value, ""));
  }

  function formatReplyRecommendation(value) {
    if (!isPlainObject(value)) {
      return "";
    }
    const type = {
      acknowledge: "先确认收到",
      ask_clarification: "先澄清信息",
      provide_info: "核查后回复信息",
      escalate_first: "先内部确认/升级",
      no_reply: "可不回复",
    }[value.reply_type] || textOrFallback(value.reply_type, "");
    const shouldReply = value.should_reply === false ? "不建议直接回复" : "建议回复";
    const reason = textOrFallback(value.reason, "");
    return [shouldReply, type, reason].filter(Boolean).join("；");
  }

  function formatConfidence(value) {
    return {
      high: "高",
      medium: "中",
      low: "低",
    }[value] || textOrFallback(value, "");
  }

  function renderListField(field, value, formatter) {
    const items = Array.isArray(value)
      ? value.map((item) => normalizeFormattedItem(formatter(item))).filter(Boolean)
      : [];
    if (items.length === 0) {
      renderPlaceholder(field);
      return;
    }
    if (!canRenderChildren(field)) {
      field.textContent = items.map(plainTextForItem).join("\n\n");
      return;
    }

    const doc = field.ownerDocument || document;
    const children = items.map((item) => renderFormattedItem(doc, item));
    field.className = withClassName(field.className, "analysis-list");
    field.replaceChildren(...children);
  }

  function structuredItem(title, lines) {
    return {
      title: textOrFallback(title, ""),
      lines: lines.filter((line) => line && line.text),
    };
  }

  function detailLine(label, text) {
    return {
      label,
      text: textOrFallback(text, ""),
    };
  }

  function normalizeFormattedItem(value) {
    if (!value) {
      return null;
    }
    if (typeof value === "string") {
      return structuredItem(value, []);
    }
    if (isPlainObject(value)) {
      return structuredItem(textOrFallback(value.title, ""), Array.isArray(value.lines) ? value.lines : []);
    }
    return structuredItem(String(value), []);
  }

  function plainTextForItem(item) {
    const lines = [];
    if (item.title) {
      lines.push(item.title);
    }
    for (const line of item.lines) {
      lines.push(line.label ? `${line.label}：${line.text}` : line.text);
    }
    return lines.join("\n");
  }

  function renderFormattedItem(doc, item) {
    const wrapper = doc.createElement("div");
    wrapper.className = "analysis-list__item";
    if (item.title) {
      const title = doc.createElement("div");
      title.className = "analysis-list__item-title";
      appendFormattedText(title, item.title);
      wrapper.appendChild(title);
    }
    for (const line of item.lines) {
      const lineElement = doc.createElement("div");
      lineElement.className = "analysis-list__line";
      if (line.label) {
        const label = doc.createElement("span");
        label.className = "analysis-list__label";
        label.textContent = `${line.label}：`;
        lineElement.appendChild(label);
      }
      appendFormattedText(lineElement, line.text);
      wrapper.appendChild(lineElement);
    }
    return wrapper;
  }

  function appendFormattedText(parent, value) {
    appendText(parent, safeDisplayText(value, ""));
  }

  function appendText(parent, text) {
    if (!text) {
      return;
    }
    const doc = parent.ownerDocument || document;
    if (doc && typeof doc.createTextNode === "function" && typeof parent.appendChild === "function") {
      parent.appendChild(doc.createTextNode(text));
      return;
    }
    parent.textContent = `${parent.textContent || ""}${text}`;
  }


  function renderPlaceholder(field, text = "-") {
    if (canRenderChildren(field)) {
      field.replaceChildren();
    }
    field.textContent = text;
  }

  function canRenderChildren(field) {
    return Boolean(field && typeof field.replaceChildren === "function");
  }

  function withClassName(current, className) {
    const names = String(current || "").split(/\s+/).filter(Boolean);
    if (!names.includes(className)) {
      names.push(className);
    }
    return names.join(" ");
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

  function formatOwnerHint(value) {
    const key = textOrFallback(value, "").toLowerCase();
    return OWNER_LABELS[key] || "相关负责人";
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
    formatAttachments,
    renderAttachments,
    renderDecisionBrief,
    renderConversationTimeline,
    renderAttachmentInsights,
  };
})();
