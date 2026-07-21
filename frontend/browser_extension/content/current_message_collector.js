(function (root) {
  "use strict";

  const EXMAIL_ORIGIN = "https://exmail.qq.com";
  const MAX_THREAD_SEGMENTS = 50;
  const MAX_THREAD_SEGMENT_CHARS = 2000;
  const MAX_THREAD_SOURCE_CHARS = 20000;
  const MAX_METADATA_CHARS = 512;
  const MAX_RESOURCE_COUNT = 5;
  const MAX_RESOURCE_CANDIDATES = 20;
  const MAX_RESOURCE_LIMITATIONS = 8;
  const MAX_RESOURCE_BYTES = 10 * 1024 * 1024;
  const MAX_TOTAL_RESOURCE_BYTES = 25 * 1024 * 1024;
  const MAX_PER_RESOURCE_TIMEOUT_MS = 8000;
  const MAX_OVERALL_RESOURCE_TIMEOUT_MS = 20000;
  const LIMITATION_CODES = Object.freeze({
    unsupported: "unsupported_type",
    frontendLimit: "frontend_limit",
    unavailable: "resource_unavailable",
    readFailed: "resource_read_failed",
    timeout: "collection_timeout",
    candidateOmission: "candidate_omission",
  });
  const SUPPORTED_RESOURCE_TYPES = Object.freeze(["image", "pdf", "xlsx", "docx"]);
  const APPROVED_RESOURCE_PATHS = Object.freeze(["/cgi-bin/download", "/cgi-bin/viewfile"]);
  const CURRENT_MESSAGE_SELECTORS = [
    "[data-email-current-message]",
    "#mailContentContainer",
    "#mailContent",
    "#qm_con_body",
    ".qm_con_body",
    ".mail-detail-content",
    ".mail-content",
    ".mail_content",
    ".readmail_content",
  ];
  const KNOWN_BODY_ROOT_SELECTORS = CURRENT_MESSAGE_SELECTORS.slice(1);
  const THREAD_SEGMENT_SELECTORS = [
    "[data-email-thread-segment]",
    ".mail-thread-segment",
    ".mail-thread-item",
    ".mail-reply-item",
    ".mail-conversation-item",
    ".readmail_item",
  ];
  const CURRENT_BODY_ONLY_SELECTORS = [
    "[data-email-current-body]",
    ".mail-current-body",
    ".current-message-body",
  ];
  const LEGACY_HEADER_LABELS = Object.freeze({
    from: ["From", "\u53d1\u4ef6\u4eba"],
    sent_at: ["Date", "Sent", "\u65f6\u95f4", "\u53d1\u9001\u65f6\u95f4"],
    to: ["To", "\u6536\u4ef6\u4eba"],
    subject: ["Subject", "\u4e3b\u9898"],
  });
  const STRUCTURED_FIELD_SELECTORS = Object.freeze({
    from: ["[data-email-from]", ".mail-sender", ".sender", ".from"],
    to: ["[data-email-to]", ".mail-recipient", ".recipient", ".to"],
    sent_at: ["[data-email-sent-at]", "time"],
    timestamp_text: ["[data-email-timestamp-text]", ".mail-time", ".timestamp"],
    subject: ["[data-email-subject]", ".mail-subject", ".subject"],
    body_text: ["[data-email-segment-body]", ".mail-segment-body", ".mail-body"],
  });
  function extractVisibleMessageContext(doc, options) {
    const settings = options || {};
    const currentRoot = findCurrentMessageRoot(doc, settings.currentMessageRoot);
    if (!currentRoot) {
      return emptyVisibleMessageContext();
    }
    const siblingRoots = boundSiblingHistoryRoots(settings, currentRoot, doc);
    const siblingBindingFailed = siblingRoots === null;
    const verifiedSiblingRoots = siblingRoots || [];
    const threadRoot = verifiedThreadRoot(
      settings,
      currentRoot,
      doc,
      verifiedSiblingRoots,
    );
    const contextLimited = settings.threadContextLimited === true ||
      siblingBindingFailed;
    const verifiedCurrentBody = verifiedCurrentBodyText(
      settings,
      currentRoot,
      threadRoot,
      doc,
    );

    const markedCandidates = minimalLegacyCandidates(
      queryAll(threadRoot, THREAD_SEGMENT_SELECTORS),
    );
    const nestedQuotedCandidates = verifiedNestedQuotedCandidates(
      settings,
      currentRoot,
      doc,
    );
    const visibleCandidates = [...markedCandidates, ...nestedQuotedCandidates]
      .filter((candidate, index, values) => values.indexOf(candidate) === index)
      .filter((candidate) => isVisibleWithin(candidate, threadRoot, doc));
    const verifiedAggregate = isVerifiedAggregateRoot(
      settings,
      currentRoot,
      visibleCandidates,
    );
    const candidates = visibleCandidates.filter((candidate) =>
      isVerifiedHistoryCandidate(
        candidate,
        settings,
        currentRoot,
        verifiedCurrentBody,
        verifiedAggregate,
        threadRoot,
        doc,
        verifiedSiblingRoots,
      ),
    );
    if (
      !candidates.length ||
      candidates.length > MAX_THREAD_SEGMENTS ||
      (threadRoot === doc.body && candidates.length !== verifiedSiblingRoots.length)
    ) {
      const limited = contextLimited || candidates.length > MAX_THREAD_SEGMENTS ||
        verifiedSiblingRoots.length > 0;
      return fallbackVisibleMessageContext(
        currentRoot,
        doc,
        verifiedCurrentBody,
        limited,
      );
    }

    const structuredFlags = candidates.map((candidate) =>
      hasStructuredSegmentFields(candidate),
    );
    let ordered;
    if (structuredFlags.every(Boolean)) {
      ordered = structuredSegments(candidates, doc);
    } else if (structuredFlags.some(Boolean)) {
      ordered = null;
    } else {
      ordered = legacySegments(candidates);
    }
    if (!ordered) {
      return fallbackVisibleMessageContext(currentRoot, doc, verifiedCurrentBody, true);
    }
    const positioned = ordered.map((segment, position) => ({
      position,
      from: segment.from,
      to: segment.to,
      sent_at: segment.sent_at,
      timestamp_text: segment.timestamp_text,
      subject: segment.subject,
      body_text: segment.body_text,
    }));
    const latest = positioned[positioned.length - 1];
    const explicitCurrentBody = uniqueExplicitCurrentBody(currentRoot, doc) ||
      verifiedCurrentBody;
    return {
      current_message: explicitCurrentBody !== null ? {
        from: "",
        to: "",
        sent_at: "",
        subject: "",
        body_text: explicitCurrentBody,
      } : {
        from: latest.from,
        to: latest.to,
        sent_at: latest.sent_at,
        subject: latest.subject,
        body_text: latest.body_text,
      },
      thread_segments: positioned,
      thread_context_limited: contextLimited === true,
    };
  }

  function extractVisibleThreadSegments(doc, options) {
    return extractVisibleMessageContext(doc, options).thread_segments;
  }

  function emptyVisibleMessageContext(bodyText, contextLimited) {
    return {
      current_message: {
        from: "",
        to: "",
        sent_at: "",
        subject: "",
        body_text: bodyText || "",
      },
      thread_segments: [],
      thread_context_limited: contextLimited === true,
    };
  }

  function fallbackVisibleMessageContext(
    currentRoot,
    doc,
    verifiedCurrentBody,
    contextLimited,
  ) {
    const explicitCurrentBody = uniqueExplicitCurrentBody(currentRoot, doc) ||
      verifiedCurrentBody;
    if (explicitCurrentBody !== null) {
      return emptyVisibleMessageContext(explicitCurrentBody, contextLimited);
    }
    return emptyVisibleMessageContext("", contextLimited);
  }

  function verifiedThreadRoot(settings, currentRoot, doc, siblingRoots) {
    const suppliedRoot = settings.threadRoot;
    if (
      suppliedRoot &&
      isInside(currentRoot, suppliedRoot) &&
      isVisibleWithin(suppliedRoot, suppliedRoot, doc) &&
      (
        suppliedRoot !== doc.body ||
        (
          settings.verifiedDocumentContext === true &&
          parentOf(currentRoot) === doc.body &&
          siblingRoots.length > 0
        )
      )
    ) {
      return suppliedRoot;
    }
    return currentRoot;
  }

  function boundSiblingHistoryRoots(settings, currentRoot, doc) {
    if (settings.verifiedDocumentContext !== true) {
      return [];
    }
    const supplied = settings.verifiedSiblingHistoryRoots;
    if (!Array.isArray(supplied) || supplied.length === 0) {
      return [];
    }
    const unique = Array.from(new Set(supplied));
    const children = Array.from(doc && doc.body && doc.body.children || []);
    const currentIndex = children.indexOf(currentRoot);
    const indexes = unique.map((candidate) => children.indexOf(candidate));
    const adjacent = currentIndex >= 0
      ? children.slice(currentIndex + 1, currentIndex + 1 + unique.length)
      : [];
    if (
      unique.length !== supplied.length ||
      unique.length > MAX_THREAD_SEGMENTS ||
      currentIndex < 0 ||
      adjacent.length !== unique.length ||
      adjacent.some((candidate, index) => candidate !== unique[index]) ||
      indexes.some((index) => index <= currentIndex) ||
      indexes.some((index, position) => position > 0 && index <= indexes[position - 1]) ||
      unique.some((candidate) => (
        parentOf(candidate) !== doc.body ||
        !isVisibleWithin(candidate, doc.body, doc) ||
        !isThreadSegmentElement(candidate) ||
        !hasCompleteLegacyHeaderBlock(candidate)
      ))
    ) {
      return null;
    }
    return unique;
  }

  function verifiedCurrentBodyText(settings, currentRoot, threadRoot, doc) {
    const candidate = settings.currentBodyRoot;
    if (
      settings.verifiedDocumentContext !== true ||
      !candidate ||
      !isInside(candidate, currentRoot) ||
      !isInside(candidate, threadRoot) ||
      !isVisibleWithin(candidate, threadRoot, doc)
    ) {
      return null;
    }
    const suppliedText = typeof settings.currentBodyText === "string"
      ? settings.currentBodyText
      : elementRawText(candidate);
    return cleanMessageBody(suppliedText) || null;
  }

  function isVerifiedAggregateRoot(settings, currentRoot, candidates) {
    if (
      settings.verifiedDocumentContext !== true ||
      settings.currentBodyRoot ||
      !candidates.length ||
      !candidates.every((candidate) => isInside(candidate, currentRoot))
    ) {
      return false;
    }
    return normalizeText(elementRawText(currentRoot)) ===
      candidates.map((candidate) => normalizeText(elementRawText(candidate))).join(" ");
  }

  function isVerifiedHistoryCandidate(
    candidate,
    settings,
    currentRoot,
    verifiedCurrentBody,
    verifiedAggregate,
    threadRoot,
    doc,
    verifiedSiblingRoots,
  ) {
    if (settings.verifiedDocumentContext !== true) {
      return true;
    }
    const currentBody = settings.currentBodyRoot;
    if (verifiedCurrentBody === null) {
      return Boolean(!currentBody && verifiedAggregate && isInside(candidate, currentRoot));
    }
    if (
      currentBody === currentRoot &&
      isInside(candidate, currentRoot) &&
      isCompleteLegacyQuote(candidate)
    ) {
      return true;
    }
    if (
      threadRoot === doc.body &&
      parentOf(currentRoot) === threadRoot &&
      parentOf(candidate) === threadRoot
    ) {
      return verifiedSiblingRoots.includes(candidate);
    }
    return Boolean(
      currentBody &&
      isInside(currentBody, currentRoot) &&
      !isInside(candidate, currentBody) &&
      !isInside(currentBody, candidate)
    );
  }

  function isThreadSegmentElement(element) {
    if (hasAttribute(element, "data-email-thread-segment")) {
      return true;
    }
    const classes = attribute(element, "class").split(/\s+/).filter(Boolean);
    return [
      "mail-thread-segment", "mail-thread-item", "mail-reply-item",
      "mail-conversation-item", "readmail_item",
    ].some((value) => classes.includes(value));
  }

  function uniqueExplicitCurrentBody(currentRoot, doc) {
    const explicitBodies = queryAll(currentRoot, CURRENT_BODY_ONLY_SELECTORS)
      .filter((candidate) => isVisibleWithin(candidate, currentRoot, doc));
    if (explicitBodies.length !== 1) {
      return null;
    }
    const bodyText = cleanMessageBody(elementRawText(explicitBodies[0]));
    return bodyText || null;
  }

  function minimalLegacyCandidates(candidates) {
    return candidates.filter((candidate) =>
      !candidates.some((other) => other !== candidate && isInside(other, candidate)),
    );
  }

  function verifiedNestedQuotedCandidates(settings, currentRoot, doc) {
    if (
      settings.verifiedDocumentContext !== true ||
      settings.currentBodyRoot !== currentRoot
    ) {
      return [];
    }
    return queryAll(currentRoot, ["blockquote"])
      .filter((candidate) => (
        isCompleteLegacyQuote(candidate) &&
        isVisibleWithin(candidate, currentRoot, doc)
      ));
  }

  function isCompleteLegacyQuote(element) {
    if (String(element && element.tagName || "").toUpperCase() !== "BLOCKQUOTE") {
      return false;
    }
    return hasCompleteLegacyHeaderBlock(element);
  }

  function hasCompleteLegacyHeaderBlock(element) {
    const lines = normalizeBodySource(elementRawText(element))
      .split("\n")
      .slice(0, 20)
      .map(normalizeLine)
      .filter(Boolean)
      .join("\n");
    return (
      /^(?:From|\u53d1\u4ef6\u4eba)\s*[:\uff1a]/im.test(lines) &&
      /^(?:Date|Sent|\u65f6\u95f4|\u53d1\u9001\u65f6\u95f4)\s*[:\uff1a]/im.test(lines) &&
      /^(?:To|\u6536\u4ef6\u4eba)\s*[:\uff1a]/im.test(lines) &&
      /^(?:Subject|\u4e3b\u9898)\s*[:\uff1a]/im.test(lines)
    );
  }

  function legacySegments(candidates) {
    const segments = [];
    let remainingChars = MAX_THREAD_SOURCE_CHARS;
    for (const candidate of candidates) {
      const sourceText = elementRawText(candidate);
      if (!sourceText) {
        return null;
      }
      const segment = parseLegacyMessageBlock(sourceText, remainingChars);
      if (!segment) {
        return null;
      }
      remainingChars -= segment._source_chars;
      segments.push(segment);
    }
    return chronologicalSegments(segments);
  }

  function structuredSegments(candidates, doc) {
    const segments = [];
    let remainingChars = MAX_THREAD_SOURCE_CHARS;
    for (const candidate of candidates) {
      const bodySource = structuredFieldText(candidate, "body_text", doc, candidate, true);
      const bodyText = cleanMessageBody(bodySource);
      const rawPosition = attribute(candidate, "data-email-position") ||
        attribute(candidate, "data-position");
      if (!bodyText || !/^\d+$/.test(rawPosition) || bodySource.length > remainingChars) {
        return null;
      }
      const position = Number(rawPosition);
      if (!Number.isSafeInteger(position) || position < 0) {
        return null;
      }
      const sentAt = boundedText(
        structuredFieldText(candidate, "sent_at", doc, candidate),
        MAX_METADATA_CHARS,
      );
      segments.push({
        _position: position,
        from: boundedText(structuredFieldText(candidate, "from", doc, candidate), MAX_METADATA_CHARS),
        to: boundedText(structuredFieldText(candidate, "to", doc, candidate), MAX_METADATA_CHARS),
        sent_at: sentAt,
        timestamp_text: boundedText(
          structuredFieldText(candidate, "timestamp_text", doc, candidate) || sentAt,
          MAX_METADATA_CHARS,
        ),
        subject: boundedText(
          structuredFieldText(candidate, "subject", doc, candidate),
          MAX_METADATA_CHARS,
        ),
        body_text: boundedBodyText(
          bodyText,
          Math.min(MAX_THREAD_SEGMENT_CHARS, remainingChars),
        ),
      });
      remainingChars -= bodySource.length;
    }
    const ordered = segments.slice().sort((left, right) => left._position - right._position);
    if (ordered.some((segment, index) => segment._position !== index)) {
      return null;
    }
    return ordered;
  }

  function hasStructuredSegmentFields(element) {
    const attributeNames = [
      "data-from", "data-email-from", "data-to", "data-email-to",
      "data-sent-at", "data-email-sent-at", "data-subject", "data-email-subject",
      "data-body-text", "data-email-body-text", "data-email-segment-body",
    ];
    if (attributeNames.some((name) => attribute(element, name))) {
      return true;
    }
    return Object.values(STRUCTURED_FIELD_SELECTORS).some((selectors) =>
      selectors.some((selector) =>
        typeof element.querySelector === "function" && element.querySelector(selector),
      ),
    );
  }

  function structuredFieldText(element, field, doc, currentRoot, preserveLines) {
    const suffix = field.replaceAll("_", "-");
    const attributeValue = attribute(element, `data-email-${suffix}`) ||
      attribute(element, `data-${suffix}`) ||
      (field === "body_text" ? attribute(element, "data-email-segment-body") : "");
    if (attributeValue) {
      return preserveLines ? normalizeBodySource(attributeValue) : normalizeText(attributeValue);
    }
    for (const selector of STRUCTURED_FIELD_SELECTORS[field] || []) {
      const candidate = typeof element.querySelector === "function"
        ? element.querySelector(selector)
        : null;
      if (candidate && isVisibleWithin(candidate, currentRoot, doc)) {
        return preserveLines ? elementRawText(candidate) : elementText(candidate);
      }
    }
    return "";
  }

  function parseLegacyMessageBlock(value, remainingChars) {
    const unquoted = truncateQuotedHistory(normalizeBodySource(value));
    if (!unquoted || unquoted.length > remainingChars) {
      return null;
    }
    const lines = unquoted.split("\n");
    const fields = { from: "", sent_at: "", to: "", subject: "" };
    const seen = new Set();
    let bodyStart = -1;
    let headerStarted = false;

    for (let index = 0; index < Math.min(lines.length, 20); index += 1) {
      const line = normalizeLine(lines[index]);
      if (!line) {
        if (seen.size === 4) {
          bodyStart = index + 1;
          break;
        }
        continue;
      }
      const header = legacyHeaderLine(line);
      if (header) {
        headerStarted = true;
        if (!header.value || seen.has(header.field)) {
          return null;
        }
        seen.add(header.field);
        fields[header.field] = header.value;
        continue;
      }
      if (optionalLegacyHeaderLine(line)) {
        continue;
      }
      if (!headerStarted || seen.size !== 4) {
        return null;
      }
      bodyStart = index;
      break;
    }

    if (seen.size !== 4) {
      return null;
    }
    if (bodyStart < 0) {
      bodyStart = lines.length;
    }
    const bodyText = cleanMessageBody(lines.slice(bodyStart).join("\n"));
    if (!bodyText) {
      return null;
    }
    const timestamp = Date.parse(fields.sent_at);
    return {
      from: boundedText(fields.from, MAX_METADATA_CHARS),
      to: boundedText(fields.to, MAX_METADATA_CHARS),
      sent_at: boundedText(fields.sent_at, MAX_METADATA_CHARS),
      timestamp_text: boundedText(fields.sent_at, MAX_METADATA_CHARS),
      subject: boundedText(fields.subject, MAX_METADATA_CHARS),
      body_text: boundedBodyText(
        bodyText,
        Math.min(MAX_THREAD_SEGMENT_CHARS, remainingChars),
      ),
      _timestamp: Number.isFinite(timestamp) ? timestamp : null,
      _source_chars: unquoted.length,
    };
  }

  function legacyHeaderLine(line) {
    for (const [field, labels] of Object.entries(LEGACY_HEADER_LABELS)) {
      for (const label of labels) {
        const match = line.match(new RegExp(`^${escapeRegex(label)}\\s*[:\\uff1a]\\s*(.+)$`, "i"));
        if (match) {
          return { field, value: normalizeText(match[1]) };
        }
      }
    }
    return null;
  }

  function optionalLegacyHeaderLine(line) {
    return /^(?:Cc|Bcc|Reply-To|\u6284\u9001|\u5bc6\u9001)\s*[:\uff1a]/i.test(line);
  }

  function chronologicalSegments(segments) {
    if (segments.every((segment) => Number.isFinite(segment._timestamp))) {
      const ordered = segments.slice().sort((left, right) => left._timestamp - right._timestamp);
      for (let index = 1; index < ordered.length; index += 1) {
        if (ordered[index - 1]._timestamp === ordered[index]._timestamp) {
          return null;
        }
      }
      return ordered;
    }
    return null;
  }

  function cleanMessageBody(value) {
    const unquoted = truncateQuotedHistory(normalizeBodySource(value));
    const lines = unquoted.split("\n");
    const kept = [];
    const contactTailStart = Math.max(0, lines.length - 8);
    let firstContentHandled = false;
    for (let index = 0; index < lines.length; index += 1) {
      const sourceLine = lines[index];
      const line = normalizeLine(sourceLine);
      if (!firstContentHandled && line) {
        firstContentHandled = true;
        if (salutationLine(line)) {
          continue;
        }
      }
      if (signatureClosing(line)) {
        break;
      }
      if (
        index >= contactTailStart && strongContactLine(line) ||
        imageCaptionLine(line)
      ) {
        continue;
      }
      kept.push(line);
    }
    while (kept.length && !kept[0]) kept.shift();
    while (kept.length && !kept[kept.length - 1]) kept.pop();
    const compact = [];
    for (const line of kept) {
      if (!line && compact[compact.length - 1] === "") {
        continue;
      }
      compact.push(line);
    }
    return compact.join("\n");
  }

  function salutationLine(line) {
    return /^(?:(?:dear|hello|hi)|good\s+(?:morning|afternoon|evening))\s+[^,!?;:\n]{1,80},$/i.test(line);
  }

  function truncateQuotedHistory(value) {
    const lines = normalizeBodySource(value).split("\n");
    for (let index = 0; index < lines.length; index += 1) {
      const line = normalizeLine(lines[index]);
      if (
        /^-{2,}\s*(?:Original Message|Forwarded message)\s*-*$/i.test(line) ||
        /^On\s+.+\s+wrote:\s*$/i.test(line) ||
        /^>/.test(line) ||
        quotedHeaderCluster(lines, index)
      ) {
        return lines.slice(0, index).join("\n");
      }
    }
    return lines.join("\n");
  }

  function quotedHeaderCluster(lines, start) {
    const first = normalizeLine(lines[start]);
    if (!/^(?:From|\u53d1\u4ef6\u4eba)\s*[:\uff1a]/i.test(first) || start === 0) {
      return false;
    }
    const bodyPrecedesHeader = lines.slice(0, start).map(normalizeLine).some((line) =>
      line && !legacyHeaderLine(line) && !optionalLegacyHeaderLine(line),
    );
    if (!bodyPrecedesHeader) {
      return false;
    }
    const windowText = lines.slice(start, start + 8).map(normalizeLine).join("\n");
    return /^(?:From|\u53d1\u4ef6\u4eba)\s*[:\uff1a]/im.test(windowText) &&
      /^(?:Date|Sent|\u65f6\u95f4|\u53d1\u9001\u65f6\u95f4)\s*[:\uff1a]/im.test(windowText) &&
      /^(?:To|\u6536\u4ef6\u4eba)\s*[:\uff1a]/im.test(windowText) &&
      /^(?:Subject|\u4e3b\u9898)\s*[:\uff1a]/im.test(windowText);
  }

  function signatureClosing(line) {
    return /^(?:best|kind|warm)\s+regards[,.!]?$/i.test(line) ||
      /^thanks\s*(?:&|and)\s*regards[,.!]?$/i.test(line) ||
      /^(?:regards|sincerely|yours sincerely)[,.!]?$/i.test(line) ||
      /^(?:\u6b64\u81f4|\u656c\u793c|\u795d\u597d|\u987a\u795d\u5546\u797a)[\uff0c,\u3002.]?$/.test(line);
  }

  function strongContactLine(line) {
    if (/^(?:https?:\/\/|www\.)\S+$/i.test(line)) {
      return true;
    }
    if (/^(?:e-?mail|\u90ae\u7bb1)\s*[:\uff1a]\s*[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i.test(line)) {
      return true;
    }
    if (/^(?:website|web|\u7f51\u5740)\s*[:\uff1a]\s*(?:https?:\/\/|www\.)\S+$/i.test(line)) {
      return true;
    }
    const phone = line.match(
      /^(?:m|mob(?:ile)?(?:\s*(?:no\.?|number))?|phone|tel|telephone|\u7535\u8bdd|\u624b\u673a)\s*[:\uff1a]\s*(.+)$/i,
    );
    if (phone) {
      const value = phone[1];
      return /^[+\d() .-]+$/.test(value) && (value.match(/\d/g) || []).length >= 7;
    }
    return /^(?:wechat|whatsapp|\u5fae\u4fe1)\s*[:\uff1a]\s*(?:[+\d][+\d() .-]{6,}|[A-Z][A-Z0-9._-]{5,})$/i.test(line);
  }

  function imageCaptionLine(line) {
    return /^(?:\[?cid:|image\d{1,4}\.(?:png|jpe?g|gif)|<image|\u56fe\u7247\s*[:\uff1a])/i.test(line);
  }

  function normalizeBodySource(value) {
    return String(value || "").replace(/\r\n?/g, "\n").replace(/\u00a0/g, " ");
  }

  function normalizeLine(value) {
    return String(value || "").replace(/[\t\f\v ]+/g, " ").trim();
  }

  function boundedBodyText(value, limit) {
    return String(value || "").slice(0, limit).trim();
  }

  function elementRawText(element) {
    return String(element ? element.innerText || element.textContent || "" : "");
  }

  function escapeRegex(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  async function collectVisibleResources(doc, options) {
    const settings = options || {};
    const currentRoot = findCurrentMessageRoot(doc, settings.currentMessageRoot);
    const result = { attachment_files: [], resource_limitations: [] };
    if (!currentRoot) {
      return result;
    }

    const currentContainer = settings.currentMessageContainer;
    const currentBodyRoot = verifiedCurrentBodyRoot(
      settings.currentBodyRoot,
      currentRoot,
      doc,
    );
    const verifiedCandidates = Array.isArray(settings.verifiedResourceCandidates)
      ? settings.verifiedResourceCandidates
      : [];
    const revalidateContext = settings.revalidateContext;
    if (
      settings.resourceControlsVerified !== true ||
      settings.verifiedDocumentContext !== true ||
      settings.verifiedDocument !== doc ||
      typeof revalidateContext !== "function" ||
      !safeContextRevalidation(revalidateContext) ||
      !currentContainer ||
      (currentContainer.parentElement || currentContainer.parentNode) !== (doc && doc.body) ||
      !hasVerifiedResourceContainerRelationship(currentRoot, currentContainer, doc) ||
      !hasUniqueVisibleKnownBodyRoot(doc, currentRoot) ||
      !isVisibleWithin(currentContainer, currentContainer, doc)
    ) {
      result.resource_limitations.push(
        limitedMetadata(
          { filename: "resource", type: "unsupported", size: 0 },
          LIMITATION_CODES.unavailable,
          "Resources are unavailable because verified current-message resource controls were not established; body analysis continued.",
        ),
      );
      return result;
    }

    const classifier = root.EmailAssistantExmailVisibleResourceClassifier;
    if (!classifier || typeof classifier.classifyVisibleResource !== "function") {
      result.resource_limitations.push(
        limitedMetadata(
          { filename: "resource", type: "unsupported", size: 0 },
          LIMITATION_CODES.unavailable,
          "Current-message resources could not be classified safely; body analysis continued.",
        ),
      );
      return result;
    }

    const limits = boundedLimits(settings.limits);
    const fetchImpl = typeof settings.fetchImpl === "function" ? settings.fetchImpl : root.fetch;
    const baseHref = settings.locationHref || documentHref(doc);
    const candidates = verifiedCandidates
      .slice(0, MAX_RESOURCE_CANDIDATES)
      .filter((element) =>
        isHostResourceControl(element) &&
        isInside(element, currentContainer) &&
        isVisibleResourceWithin(element, currentContainer, doc),
      );
    const repeatedInlineIdentities = repeatedInlineResourceIdentities(
      candidates,
      currentBodyRoot,
      baseHref,
    );
    const omitted = {
      count: Math.max(0, verifiedCandidates.length - MAX_RESOURCE_CANDIDATES),
    };
    const localOverallDeadline = Date.now() + limits.overallTimeoutMs;
    const suppliedOverallDeadline = Number(settings.overallDeadline);
    const overallDeadline = Number.isFinite(suppliedOverallDeadline)
      ? Math.min(localOverallDeadline, suppliedOverallDeadline)
      : localOverallDeadline;
    let transferCount = 0;
    let totalBytes = 0;
    let inlineImageCount = 0;

    for (let index = 0; index < candidates.length; index += 1) {
      if (Date.now() >= overallDeadline) {
        omitted.count += candidates.length - index;
        break;
      }
      const element = candidates[index];
      const record = classifyResourceCandidate(
        classifier,
        element,
        currentRoot,
        currentBodyRoot,
        currentContainer,
        doc,
        baseHref,
        repeatedInlineIdentities,
      );
      if (!record || record.classification === "rejected") {
        if (record && record.candidateKind === "attachment") {
          addRejectedAttachmentLimitation(result, record, omitted);
        }
        continue;
      }
      const nextInlineOrdinal = record.classification === "inline_business_image"
        ? inlineImageCount + 1
        : 0;
      const metadata = record.classification === "inline_business_image"
        ? inlineResourceMetadata(element, nextInlineOrdinal)
        : resourceMetadata(element);
      if (!metadata.type && !record.deferredTypeValidation) {
        addResourceLimitation(
          result,
          limitedMetadata(metadata, LIMITATION_CODES.unsupported, "Resource type is not supported."),
          omitted,
        );
        continue;
      }

      const resolvedUrl = record.resolvedUrl;
      if (!resolvedUrl) {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.unavailable, "Resource URL must be a same-origin Tencent Exmail HTTPS URL."),
          omitted);
        continue;
      }
      if (!isApprovedResourceEndpoint(resolvedUrl)) {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.unavailable, "Resource URL is not an approved Tencent Exmail attachment endpoint."),
          omitted);
        continue;
      }
      if (metadata.size > limits.maxFileBytes) {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.frontendLimit, `Resource exceeds the ${limits.maxFileBytes}-byte per-file limit.`),
          omitted);
        continue;
      }
      if (transferCount >= limits.maxFiles) {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.frontendLimit, `Resource exceeds the ${limits.maxFiles}-file frontend limit.`),
          omitted);
        continue;
      }

      transferCount += 1;
      if (metadata.size > 0 && totalBytes + metadata.size > limits.maxTotalBytes) {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.frontendLimit, `Resource exceeds the ${limits.maxTotalBytes}-byte total frontend limit.`),
          omitted);
        continue;
      }
      if (typeof fetchImpl !== "function") {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.readFailed, "Resource could not be read from the current Tencent Exmail session."),
          omitted);
        continue;
      }
      if (!safeContextRevalidation(revalidateContext)) {
        return staleContextResult(result);
      }
      if (!resourceCandidateMatches(
        record,
        classifier,
        currentRoot,
        currentBodyRoot,
        currentContainer,
        doc,
        baseHref,
        candidates,
      )) {
        addResourceLimitation(result,
          limitedMetadata(metadata, LIMITATION_CODES.unavailable, "Resource identity changed before collection; body analysis continued."),
          omitted);
        continue;
      }

      const resourceDeadline = Math.min(
        overallDeadline,
        Date.now() + limits.perResourceTimeoutMs,
      );
      const collected = await fetchResource(
        fetchImpl,
        resolvedUrl,
        limits,
        totalBytes,
        resourceDeadline,
        record.deferredTypeValidation,
      );
      if (collected.buffer) {
        if (!safeContextRevalidation(revalidateContext)) {
          clearMutableBuffer(collected.buffer);
          return staleContextResult(result);
        }
        if (!resourceCandidateMatches(
          record,
          classifier,
          currentRoot,
          currentBodyRoot,
          currentContainer,
          doc,
          baseHref,
          candidates,
        )) {
          clearMutableBuffer(collected.buffer);
          addResourceLimitation(result,
            limitedMetadata(metadata, LIMITATION_CODES.unavailable, "Resource identity changed during collection; body analysis continued."),
            omitted);
          continue;
        }
        const byteSize = collected.buffer.byteLength;
        const payloadType = record.deferredTypeValidation ? collected.detectedType : metadata.type;
        const payloadFilename = record.deferredTypeValidation
          ? genericAttachmentFilename(transferCount, collected.detectedExtension)
          : metadata.filename;
        const contentBase64 = arrayBufferToBase64(collected.buffer);
        clearMutableBuffer(collected.buffer);
        result.attachment_files.push({
          filename: payloadFilename,
          type: payloadType,
          size: byteSize,
          content_base64: contentBase64,
        });
        totalBytes += byteSize;
        if (record.classification === "inline_business_image") {
          inlineImageCount = nextInlineOrdinal;
        }
      } else {
        addResourceLimitation(
          result,
          limitedMetadata(metadata, collected.code, collected.limitation),
          omitted,
        );
      }
    }
    if (!safeContextRevalidation(revalidateContext)) {
      return staleContextResult(result);
    }
    appendAggregateOmission(result, omitted.count);
    return result;
  }

  function addRejectedAttachmentLimitation(result, record, omitted) {
    const metadata = record.metadata;
    if (!metadata.type) {
      addResourceLimitation(
        result,
        limitedMetadata(metadata, LIMITATION_CODES.unsupported, "Resource type is not supported."),
        omitted,
      );
      return;
    }
    if (!record.resolvedUrl) {
      addResourceLimitation(
        result,
        limitedMetadata(metadata, LIMITATION_CODES.unavailable, "Resource URL must be a same-origin Tencent Exmail HTTPS URL."),
        omitted,
      );
      return;
    }
    if (!record.approvedEndpoint) {
      addResourceLimitation(
        result,
        limitedMetadata(metadata, LIMITATION_CODES.unavailable, "Resource URL is not an approved Tencent Exmail attachment endpoint."),
        omitted,
      );
    }
  }

  function verifiedCurrentBodyRoot(candidate, currentRoot, doc) {
    return candidate &&
      isInside(candidate, currentRoot) &&
      isVisibleWithin(candidate, currentRoot, doc)
      ? candidate
      : null;
  }

  function hasVerifiedResourceContainerRelationship(currentRoot, currentContainer, doc) {
    if (!currentRoot || !currentContainer || !doc || !doc.body || currentContainer === doc.body) {
      return false;
    }
    if ((currentContainer.parentElement || currentContainer.parentNode) !== doc.body) {
      return false;
    }
    const parent = currentRoot.parentElement || currentRoot.parentNode;
    if (parent === currentContainer) {
      return true;
    }
    if (!isExactTencentQmboxRoot(currentRoot) || !parent) {
      return false;
    }
    return (parent.parentElement || parent.parentNode) === currentContainer;
  }

  function isExactTencentQmboxRoot(element) {
    const classes = attribute(element, "class").split(/\s+/).filter(Boolean);
    return attribute(element, "id") === "mailContentContainer" && classes.includes("qmbox");
  }

  function safeContextRevalidation(revalidateContext) {
    try {
      return revalidateContext() === true;
    } catch (error) {
      return false;
    }
  }

  function staleContextResult(result) {
    result.attachment_files.length = 0;
    result.resource_limitations.length = 0;
    result.resource_limitations.push(limitedMetadata(
      { filename: "resource", type: "unsupported", size: 0 },
      LIMITATION_CODES.unavailable,
      "Verified current-message context changed during resource collection; collected bytes were discarded.",
    ));
    return result;
  }

  function repeatedInlineResourceIdentities(candidates, currentBodyRoot, baseHref) {
    const counts = new Map();
    if (!currentBodyRoot) {
      return new Set();
    }
    for (const element of candidates) {
      if (String(element && element.tagName || "").toUpperCase() !== "IMG" ||
          !isInside(element, currentBodyRoot)) {
        continue;
      }
      for (const identity of inlineResourceIdentities(element, baseHref)) {
        counts.set(identity, (counts.get(identity) || 0) + 1);
      }
    }
    return new Set(
      Array.from(counts.entries())
        .filter((entry) => entry[1] > 1)
        .map((entry) => entry[0]),
    );
  }

  function inlineResourceIdentities(element, baseHref) {
    const identities = [];
    const resolvedUrl = resolveResourceUrl(resourceUrl(element), baseHref);
    if (resolvedUrl) {
      identities.push(`url:${resolvedUrl}`);
    }
    const contentId = normalizeText(attribute(element, "data-cid") || attribute(element, "cid"));
    if (contentId) {
      identities.push(`cid:${contentId.toLowerCase()}`);
    }
    return identities;
  }

  function isRepeatedInlineResource(element, baseHref, repeatedInlineIdentities) {
    return inlineResourceIdentities(element, baseHref).some(
      (identity) => repeatedInlineIdentities.has(identity),
    );
  }

  function classifyResourceCandidate(
    classifier,
    element,
    currentRoot,
    currentBodyRoot,
    currentContainer,
    doc,
    baseHref,
    repeatedInlineIdentities,
  ) {
    const candidateKind = resourceCandidateKind(
      element,
      currentRoot,
      currentBodyRoot,
      currentContainer,
    );
    const resolvedUrl = resolveResourceUrl(resourceUrl(element), baseHref);
    const metadata = resourceMetadata(element);
    const approvedEndpoint = Boolean(resolvedUrl && isApprovedResourceEndpoint(resolvedUrl));
    const dimensions = imageDimensions(element);
    const contactSignals = candidateContactSignalCount(element, currentBodyRoot);
    const visualHint = candidateVisualHint(element, currentBodyRoot);
    const attachmentEvidence = candidateKind === "attachment"
      ? attachmentControlEvidence(element, visualHint, resolvedUrl, metadata)
      : { verified: false, deferredTypeValidation: false };
    const facts = {
      candidateKind,
      resourceType: candidateKind === "inline_image" ? "image" : metadata.type,
      visible: isVisibleResourceWithin(element, currentContainer, doc),
      currentMessageOwned: candidateKind !== "ambiguous",
      approvedUrl: approvedEndpoint,
      ambiguousOwnership: candidateKind === "ambiguous",
      quotedHistory: candidateKind === "inline_image" && isQuotedHistoryMedia(element, currentBodyRoot),
      afterSignatureBoundary: candidateKind === "inline_image" && isAfterSignatureBoundary(element, currentBodyRoot),
      repeated: candidateKind === "inline_image" &&
        isRepeatedInlineResource(element, baseHref, repeatedInlineIdentities),
      width: dimensions.width,
      height: dimensions.height,
      visualHint,
      signatureContext: candidateKind === "inline_image" && isSignatureContext(element, currentBodyRoot),
      contactSignalCount: contactSignals,
      verifiedAttachmentControl: attachmentEvidence.verified,
      deferredTypeValidation: attachmentEvidence.deferredTypeValidation,
    };
    const classification = classifier.classifyVisibleResource(facts);
    return {
      element,
      classification,
      resolvedUrl,
      candidateKind,
      metadata,
      approvedEndpoint,
      deferredTypeValidation: facts.deferredTypeValidation,
      identityKey: resourceIdentityKey(facts, resolvedUrl, element),
    };
  }

  function resourceCandidateMatches(
    expected,
    classifier,
    currentRoot,
    currentBodyRoot,
    currentContainer,
    doc,
    baseHref,
    candidates,
  ) {
    if (!expected || !expected.element || !isInside(expected.element, currentContainer)) {
      return false;
    }
    const current = classifyResourceCandidate(
      classifier,
      expected.element,
      currentRoot,
      currentBodyRoot,
      currentContainer,
      doc,
      baseHref,
      repeatedInlineResourceIdentities(candidates, currentBodyRoot, baseHref),
    );
    return current.classification === expected.classification &&
      current.resolvedUrl === expected.resolvedUrl &&
      current.identityKey === expected.identityKey;
  }

  function resourceCandidateKind(element, currentRoot, currentBodyRoot, currentContainer) {
    const tagName = String(element && element.tagName || "").toUpperCase();
    if (tagName === "IMG" && currentBodyRoot && isInside(element, currentBodyRoot)) {
      return "inline_image";
    }
    if (
      tagName === "A" &&
      isInside(element, currentContainer) &&
      !isInside(element, currentRoot) &&
      !hasKnownBodyAncestor(element, currentRoot, currentContainer)
    ) {
      return "attachment";
    }
    return "ambiguous";
  }

  function resourceIdentityKey(facts, resolvedUrl, element) {
    const attachmentName = facts.candidateKind === "attachment"
      ? resourceMetadata(element).filename
      : "";
    return JSON.stringify([
      facts.candidateKind,
      facts.resourceType,
      facts.visible,
      facts.currentMessageOwned,
      facts.approvedUrl,
      facts.ambiguousOwnership,
      facts.quotedHistory,
      facts.afterSignatureBoundary,
      facts.repeated,
      facts.width,
      facts.height,
      facts.visualHint,
      facts.signatureContext,
      facts.contactSignalCount,
      facts.verifiedAttachmentControl,
      facts.deferredTypeValidation,
      resolvedUrl,
      attachmentName,
    ]);
  }

  function candidateVisualHint(element, currentBodyRoot) {
    const parts = [];
    let current = element;
    while (current && current !== currentBodyRoot) {
      for (const name of ["id", "class", "role", "alt", "title", "name", "data-role"]) {
        const value = attribute(current, name);
        if (value) {
          parts.push(value);
        }
      }
      current = current.parentElement || current.parentNode;
    }
    return normalizeText(parts.join(" ")).slice(0, 1024);
  }

  function attachmentControlEvidence(element, visualHint, resolvedUrl, metadata) {
    if (
      String(element && element.tagName || "").toUpperCase() !== "A" ||
      /(?:^|[^a-z0-9])(?:avatar|contact|footer|headshot|icon|logo|portrait|profile|signature|social|tracker|tracking)(?:[^a-z0-9]|$)/i
        .test(String(visualHint || ""))
    ) {
      return { verified: false, deferredTypeValidation: false };
    }
    const hasDownload = normalizeText(attribute(element, "download")).length > 0;
    const typeEvidence = legacyAttachmentTypeEvidence(element, metadata, hasDownload);
    if (!typeEvidence.valid) {
      return { verified: false, deferredTypeValidation: false };
    }
    if (hasDownload) {
      return { verified: true, deferredTypeValidation: false };
    }
    return legacyTencentDownloadControlEvidence(element, resolvedUrl, metadata, typeEvidence);
  }

  function legacyTencentDownloadControlEvidence(element, resolvedUrl, metadata, existingTypeEvidence) {
    try {
      const url = new URL(String(resolvedUrl || ""));
      const typeEvidence = existingTypeEvidence || legacyAttachmentTypeEvidence(element, metadata);
      const verified = normalizeText(attribute(element, "target")).length > 0 &&
        url.origin === EXMAIL_ORIGIN &&
        url.protocol === "https:" &&
        !url.username && !url.password &&
        url.pathname === "/cgi-bin/download" &&
        url.search.length > 1 &&
        !hasLegacyNegativeAttachmentLabel(element) &&
        typeEvidence.valid;
      return {
        verified,
        deferredTypeValidation: verified && typeEvidence.deferred,
      };
    } catch (error) {
      return { verified: false, deferredTypeValidation: false };
    }
  }

  function legacyAttachmentTypeEvidence(element, metadata, allowUnselectedMetadata) {
    const visible = legacyVisibleAttachmentDescriptor(element);
    const declared = legacyDeclaredTypeDescriptor(element);
    const filename = legacyDataFilenameDescriptor(element);
    const descriptors = [visible.descriptor, declared.descriptor, filename.descriptor].filter(Boolean);
    const selected = descriptors[0] || null;
    const consistent = new Set(descriptors.map((descriptor) => descriptor.canonical)).size <= 1;
    const metadataType = String(metadata && metadata.type || "");
    const metadataConsistent = selected
      ? selected.type === metadataType
      : allowUnselectedMetadata === true || metadataType === "";
    return {
      valid: visible.valid && declared.valid && filename.valid && consistent && metadataConsistent,
      deferred: descriptors.length === 0,
    };
  }

  function legacyDataFilenameDescriptor(element) {
    const value = normalizeText(attribute(element, "data-filename")).toLowerCase();
    if (!value) {
      return { present: false, valid: true, descriptor: null };
    }
    const suffix = value.match(/\.([a-z0-9]+)$/);
    const descriptor = suffix ? normalizeLegacyVisibleAttachmentType(`.${suffix[1]}`) : null;
    return { present: true, valid: Boolean(descriptor), descriptor };
  }

  function legacyVisibleAttachmentDescriptor(element) {
    const descriptors = [];
    for (const label of legacyVisibleAttachmentLabels(element)) {
      const normalized = normalizeText(label);
      if (!normalized) {
        continue;
      }
      const scan = legacyVisibleAttachmentDescriptors(normalized);
      if (!scan.valid) {
        return { valid: false, descriptor: null };
      }
      descriptors.push(...scan.descriptors);
    }
    const canonicalTypes = new Set(descriptors.map((descriptor) => descriptor.canonical));
    const valid = canonicalTypes.size <= 1;
    return {
      valid,
      descriptor: valid && descriptors.length > 0 ? descriptors[0] : null,
    };
  }

  function legacyVisibleAttachmentDescriptors(value) {
    const normalized = normalizeText(value).toLowerCase();
    const exact = normalizeLegacyDeclaredType(normalized);
    if (exact) {
      return { valid: true, descriptors: [exact] };
    }
    const descriptors = [];
    const mimePattern = /(?:^|[\s(])((?:image|application)\/[^\s)\]]+)/gi;
    for (const match of normalized.matchAll(mimePattern)) {
      const descriptor = normalizeLegacyDeclaredType(match[1]);
      if (!descriptor) {
        return { valid: false, descriptors: [] };
      }
      descriptors.push(descriptor);
    }
    const extensionPattern = /(?:^|[\s(])(?:[a-z0-9][a-z0-9_-]*)\.([a-z0-9]{2,5})(?=$|[\s)\]])/gi;
    for (const match of normalized.matchAll(extensionPattern)) {
      const descriptor = normalizeLegacyVisibleAttachmentType(`.${match[1]}`);
      if (!descriptor) {
        return { valid: false, descriptors: [] };
      }
      descriptors.push(descriptor);
    }
    return { valid: true, descriptors };
  }

  function legacyVisibleAttachmentLabels(element) {
    const labels = [];
    if (element && typeof element.innerText === "string") {
      labels.push(element.innerText);
    }
    for (const name of ["aria-label", "title", "alt"]) {
      labels.push(attribute(element, name));
    }
    return labels;
  }

  function normalizeLegacyVisibleAttachmentType(value) {
    const normalized = normalizeText(value).toLowerCase();
    const declaredType = normalizeLegacyDeclaredType(normalized);
    if (declaredType) {
      return declaredType;
    }
    const extension = normalized.match(/\.([a-z0-9]+)(?:$|[\s)\]])/i);
    if (!extension) {
      return null;
    }
    const extensions = {
      pdf: { type: "pdf", canonical: "pdf" },
      docx: { type: "docx", canonical: "docx" },
      xlsx: { type: "xlsx", canonical: "xlsx" },
      bmp: { type: "image", canonical: "image/bmp" },
      gif: { type: "image", canonical: "image/gif" },
      jpg: { type: "image", canonical: "image/jpeg" },
      jpeg: { type: "image", canonical: "image/jpeg" },
      png: { type: "image", canonical: "image/png" },
      tif: { type: "image", canonical: "image/tiff" },
      tiff: { type: "image", canonical: "image/tiff" },
      webp: { type: "image", canonical: "image/webp" },
    };
    return extensions[extension[1]] || null;
  }

  function normalizeLegacyDeclaredType(value) {
    const declaredTypes = {
      "image": { type: "image", canonical: "image" },
      "image/bmp": { type: "image", canonical: "image/bmp" },
      "image/gif": { type: "image", canonical: "image/gif" },
      "image/jpg": { type: "image", canonical: "image/jpeg" },
      "image/jpeg": { type: "image", canonical: "image/jpeg" },
      "image/png": { type: "image", canonical: "image/png" },
      "image/tif": { type: "image", canonical: "image/tiff" },
      "image/tiff": { type: "image", canonical: "image/tiff" },
      "image/webp": { type: "image", canonical: "image/webp" },
      "application/pdf": { type: "pdf", canonical: "pdf" },
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": { type: "xlsx", canonical: "xlsx" },
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": { type: "docx", canonical: "docx" },
      "pdf": { type: "pdf", canonical: "pdf" },
      "xlsx": { type: "xlsx", canonical: "xlsx" },
      "docx": { type: "docx", canonical: "docx" },
    };
    if (Object.prototype.hasOwnProperty.call(declaredTypes, value)) {
      return declaredTypes[value];
    }
    return null;
  }

  function hasLegacyNegativeAttachmentLabel(element) {
    return legacyVisibleAttachmentLabels(element).some((label) => (
      /(?:^|[^a-z0-9])(?:avatar|contact|footer|headshot|icon|logo|portrait|profile|signature|social|tracker|tracking)(?:[^a-z0-9]|$)/i
        .test(String(label || ""))
    ));
  }

  function legacyDeclaredTypeDescriptor(element) {
    const declared = ["data-type", "data-mime-type", "type"]
      .map((name) => normalizeText(attribute(element, name)).toLowerCase())
      .filter(Boolean);
    const descriptors = declared.map((value) => normalizeLegacyDeclaredType(value));
    const valid = descriptors.every(Boolean) &&
      new Set(descriptors.filter(Boolean).map((item) => item.canonical)).size <= 1;
    return { valid, descriptor: valid && descriptors.length ? descriptors[0] : null };
  }

  function isQuotedHistoryMedia(element, currentBodyRoot) {
    if (hasKnownThreadSegmentAncestor(element, currentBodyRoot)) {
      return true;
    }
    const hint = ancestorStructuralHint(element, currentBodyRoot);
    if (/(?:^|[-_\s])(?:quote|quoted|history|original|forwarded|reply)(?:[-_\s]|$)/i.test(hint)) {
      return true;
    }
    const preceding = precedingElementText(element, currentBodyRoot);
    return /-----\s*original message-----|(?:^|\s)(?:from|\u53d1\u4ef6\u4eba)\s*[:\uff1a].*(?:sent|date|\u53d1\u9001\u65f6\u95f4)\s*[:\uff1a]/i.test(preceding);
  }

  function hasKnownThreadSegmentAncestor(element, boundary) {
    let current = element;
    while (current && current !== boundary) {
      if (isKnownThreadSegment(current)) {
        return true;
      }
      current = current.parentElement || current.parentNode;
    }
    return false;
  }

  function isKnownThreadSegment(element) {
    if (isCompleteLegacyQuote(element)) {
      return true;
    }
    if (hasAttribute(element, "data-email-thread-segment")) {
      return true;
    }
    const classes = attribute(element, "class").split(/\s+/).filter(Boolean);
    return THREAD_SEGMENT_SELECTORS
      .filter((selector) => selector.startsWith("."))
      .some((selector) => classes.includes(selector.slice(1)));
  }

  function isAfterSignatureBoundary(element, currentBodyRoot) {
    const preceding = precedingElementText(element, currentBodyRoot);
    return /(?:^|\s)(?:--|best regards|kind regards|regards|sincerely|thank you|thanks|\u6b64\u81f4|\u656c\u793c|\u795d\u597d)(?:\s|$)/i.test(preceding);
  }

  function isSignatureContext(element, currentBodyRoot) {
    const hint = ancestorStructuralHint(element, currentBodyRoot);
    if (/(?:^|[-_\s])(?:signature|footer|vcard|contact-card)(?:[-_\s]|$)/i.test(hint)) {
      return true;
    }
    const parent = element && (element.parentElement || element.parentNode);
    return Boolean(
      parent &&
      parent !== currentBodyRoot &&
      contactSignalCount(elementText(parent)) >= 2
    );
  }

  function candidateContactSignalCount(element, currentBodyRoot) {
    const parent = element && (element.parentElement || element.parentNode);
    return parent && parent !== currentBodyRoot ? contactSignalCount(elementText(parent)) : 0;
  }

  function contactSignalCount(value) {
    const text = String(value || "");
    const signals = [
      /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
      /(?:\b(?:tel|phone|mobile|fax|wechat|whatsapp)\b|\u7535\u8bdd|\u624b\u673a|\u5fae\u4fe1)\s*[:\uff1a]?/i,
      /(?:\baddress\b|\u5730\u5740|\bstreet\b|\broad\b)\s*[:\uff1a]?/i,
      /(?:\bwww\.|https?:\/\/)/i,
    ];
    return signals.filter((pattern) => pattern.test(text)).length;
  }

  function ancestorStructuralHint(element, boundary) {
    const parts = [];
    let current = element;
    while (current && current !== boundary) {
      parts.push(attribute(current, "id"), attribute(current, "class"), attribute(current, "role"));
      current = current.parentElement || current.parentNode;
    }
    return normalizeText(parts.join(" ")).slice(0, 1024);
  }

  function precedingElementText(element, boundary) {
    const parts = [];
    let current = element;
    while (current && current !== boundary) {
      const parent = current.parentElement || current.parentNode;
      if (!parent) {
        break;
      }
      const siblings = Array.from(parent.children || []);
      const index = siblings.indexOf(current);
      for (let offset = 0; offset < index; offset += 1) {
        parts.push(elementText(siblings[offset]));
      }
      current = parent;
    }
    return normalizeText(parts.join(" ")).slice(-2048);
  }

  function imageDimensions(element) {
    const rect = resourceLayoutRect(element);
    return {
      width: positiveDimension(rect && rect.width),
      height: positiveDimension(rect && rect.height),
    };
  }

  function positiveDimension(value) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : 0;
  }

  function inlineResourceMetadata(element, ordinal) {
    return {
      filename: `inline-image-${ordinal}.${inlineImageExtension(element)}`,
      type: "image",
      size: declaredByteSize(attribute(element, "data-size")),
    };
  }

  function inlineImageExtension(element) {
    const declared = normalizeText(
      attribute(element, "data-type") ||
      attribute(element, "data-mime-type") ||
      attribute(element, "type"),
    ).toLowerCase();
    const mapping = {
      "image/bmp": "bmp",
      "image/gif": "gif",
      "image/jpeg": "jpg",
      "image/jpg": "jpg",
      "image/png": "png",
      "image/tiff": "tiff",
      "image/webp": "webp",
    };
    return mapping[declared] || "jpg";
  }

  function findCurrentMessageRoot(doc, suppliedRoot) {
    if (!doc) {
      return null;
    }
    if (suppliedRoot) {
      return isVisibleWithin(suppliedRoot, suppliedRoot, doc) ? suppliedRoot : null;
    }
    if (typeof doc.querySelector !== "function") {
      return null;
    }
    for (const selector of CURRENT_MESSAGE_SELECTORS) {
      const candidate = doc.querySelector(selector);
      if (candidate && isVisibleWithin(candidate, candidate, doc)) {
        return candidate;
      }
    }
    return null;
  }

  function queryAll(container, selectors) {
    if (!container || typeof container.querySelectorAll !== "function") {
      return [];
    }
    return Array.from(container.querySelectorAll(selectors.join(", ")) || []);
  }

  function isVisibleWithin(element, boundary, doc) {
    let current = element;
    let reachedBoundary = false;
    let reachedDocumentBody = !doc || !doc.body;
    while (current) {
      if (current.hidden || hasAttribute(current, "hidden")) {
        return false;
      }
      if (attribute(current, "aria-hidden").toLowerCase() === "true") {
        return false;
      }
      if (styleHides(current, doc)) {
        return false;
      }
      if (current === boundary) {
        reachedBoundary = true;
      }
      if (doc && current === doc.body) {
        reachedDocumentBody = true;
      }
      current = current.parentElement || current.parentNode;
    }
    return reachedBoundary && reachedDocumentBody;
  }

  function isVisibleResourceWithin(element, boundary, doc) {
    const requireViewportIntersection = String(element && element.tagName || "").toUpperCase() === "IMG";
    return isVisibleWithin(element, boundary, doc) &&
      hasVisibleResourceLayout(element, doc, requireViewportIntersection);
  }

  function hasVisibleResourceLayout(element, doc, requireViewportIntersection) {
    const rect = resourceLayoutRect(element);
    if (!rect) {
      return false;
    }
    const values = [rect.left, rect.top, rect.right, rect.bottom, rect.width, rect.height]
      .map((value) => Number(value));
    if (!values.every(Number.isFinite)) {
      return false;
    }
    const [left, top, right, bottom, width, height] = values;
    if (width <= 0 || height <= 0) {
      return false;
    }
    if (requireViewportIntersection !== true) {
      return true;
    }
    const view = doc && doc.defaultView;
    const documentElement = doc && doc.documentElement;
    const body = doc && doc.body;
    const viewportWidth = positiveDimension(
      view && view.innerWidth,
    ) || positiveDimension(documentElement && documentElement.clientWidth) ||
      positiveDimension(body && body.clientWidth);
    const viewportHeight = positiveDimension(
      view && view.innerHeight,
    ) || positiveDimension(documentElement && documentElement.clientHeight) ||
      positiveDimension(body && body.clientHeight);
    return Boolean(viewportWidth && viewportHeight) &&
      right > 0 && bottom > 0 && left < viewportWidth && top < viewportHeight;
  }

  function resourceLayoutRect(element) {
    if (!element || typeof element.getBoundingClientRect !== "function") {
      return null;
    }
    try {
      return element.getBoundingClientRect();
    } catch (error) {
      return null;
    }
  }

  function isInside(element, boundary) {
    let current = element;
    while (current) {
      if (current === boundary) {
        return true;
      }
      current = current.parentElement || current.parentNode;
    }
    return false;
  }

  function parentOf(element) {
    return element && (element.parentElement || element.parentNode) || null;
  }

  function isHostResourceControl(element) {
    const tagName = String(element && element.tagName || "").toUpperCase();
    if (tagName === "A") {
      return Boolean(attribute(element, "href"));
    }
    if (tagName === "IMG") {
      return Boolean(attribute(element, "src"));
    }
    return false;
  }

  function hasKnownBodyAncestor(element, currentRoot, container) {
    let current = element;
    while (current) {
      if (current === currentRoot || isKnownBodyRoot(current)) {
        return true;
      }
      if (current === container) {
        return false;
      }
      current = current.parentElement || current.parentNode;
    }
    return false;
  }

  function hasUniqueVisibleKnownBodyRoot(doc, currentRoot) {
    const roots = queryAll(doc && doc.body, KNOWN_BODY_ROOT_SELECTORS)
      .filter((candidate) => isVisibleWithin(candidate, candidate, doc));
    return roots.length === 1 && roots[0] === currentRoot;
  }

  function isKnownBodyRoot(element) {
    const id = attribute(element, "id");
    if (["mailContentContainer", "mailContent"].includes(id)) {
      return true;
    }
    const classes = attribute(element, "class").split(/\s+/).filter(Boolean);
    return [
      "qm_con_body", "mail-detail-content", "mail-content", "mail_content", "readmail_content",
    ].some((className) => classes.includes(className));
  }

  function styleHides(element, doc) {
    const inlineStyle = element.style || {};
    if (
      inlineStyle.display === "none" ||
      hiddenVisibility(inlineStyle.visibility) ||
      String(inlineStyle.opacity) === "0"
    ) {
      return true;
    }
    const view = doc && doc.defaultView;
    if (!view || typeof view.getComputedStyle !== "function") {
      return false;
    }
    try {
      const computed = view.getComputedStyle(element);
      return computed.display === "none" ||
        hiddenVisibility(computed.visibility) ||
        String(computed.opacity) === "0";
    } catch (error) {
      return false;
    }
  }

  function hiddenVisibility(value) {
    return value === "hidden" || value === "collapse";
  }

  function resourceMetadata(element) {
    const filename = safeFilename(
      attribute(element, "data-filename") ||
        attribute(element, "download") ||
        attribute(element, "aria-label") ||
        attribute(element, "title") ||
        attribute(element, "alt") ||
        elementText(element),
    );
    const declaredType =
      attribute(element, "data-type") ||
      attribute(element, "data-mime-type") ||
      attribute(element, "type");
    return {
      filename,
      type: normalizeResourceType(declaredType, filename),
      size: declaredByteSize(attribute(element, "data-size")),
    };
  }

  function resourceUrl(element) {
    const tagName = String(element && element.tagName || "").toUpperCase();
    if (tagName === "A") {
      return attribute(element, "href");
    }
    if (tagName === "IMG") {
      return attribute(element, "src");
    }
    return "";
  }

  function normalizeResourceType(value, filename) {
    const declared = normalizeText(value).toLowerCase();
    if (declared) {
      if (declared === "image" || declared.startsWith("image/")) {
        return "image";
      }
      if (declared === "pdf" || declared === "application/pdf") {
        return "pdf";
      }
      if (
        declared === "xlsx" ||
        declared === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      ) {
        return "xlsx";
      }
      if (
        declared === "docx" ||
        declared === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      ) {
        return "docx";
      }
      return "";
    }

    const extension = filename.toLowerCase().match(/\.([a-z0-9]+)$/);
    if (!extension) {
      return "";
    }
    if (["png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff"].includes(extension[1])) {
      return "image";
    }
    return SUPPORTED_RESOURCE_TYPES.includes(extension[1]) ? extension[1] : "";
  }

  async function fetchResource(
    fetchImpl,
    url,
    limits,
    totalBytes,
    deadline,
    deferredTypeValidation,
  ) {
    const controller = typeof root.AbortController === "function"
      ? new root.AbortController()
      : null;
    try {
      const options = { credentials: "include", redirect: "error" };
      if (controller) {
        options.signal = controller.signal;
      }
      const response = await withDeadline(
        fetchImpl(url, options),
        deadline,
        () => abortController(controller),
      );
      if (!response || response.ok !== true || !responseMatchesRequestedEndpoint(response, url)) {
        return {
          code: LIMITATION_CODES.readFailed,
          limitation: "Resource could not be read from the current Tencent Exmail session.",
        };
      }
      const announcedSize = responseByteSize(response);
      if (announcedSize !== null) {
        const announcedLimitation = byteLimitation(announcedSize, limits, totalBytes);
        if (announcedLimitation) {
          cancelResponseBody(response);
          return { code: LIMITATION_CODES.frontendLimit, limitation: announcedLimitation };
        }
      }
      const bodyResult = await readBoundedResponse(
        response,
        limits,
        totalBytes,
        deadline,
        controller,
      );
      if (bodyResult.limitation) {
        return bodyResult;
      }
      const buffer = bodyResult.buffer;
      const byteSize = buffer && Number.isSafeInteger(buffer.byteLength) ? buffer.byteLength : 0;
      if (byteSize <= 0) {
        return { code: LIMITATION_CODES.readFailed, limitation: "Resource is empty or unreadable." };
      }
      const actualLimitation = byteLimitation(byteSize, limits, totalBytes);
      if (actualLimitation) {
        clearMutableBuffer(buffer);
        return { code: LIMITATION_CODES.frontendLimit, limitation: actualLimitation };
      }
      if (deferredTypeValidation === true) {
        const detected = detectDeferredResponseType(response, buffer);
        if (!detected.type) {
          clearMutableBuffer(buffer);
          return { code: detected.code, limitation: detected.limitation };
        }
        return {
          buffer,
          detectedType: detected.type,
          detectedExtension: detected.extension,
        };
      }
      return { buffer };
    } catch (error) {
      if (isDeadlineError(error)) {
        return {
          code: LIMITATION_CODES.timeout,
          limitation: "Resource collection deadline expired; body analysis continued without this resource.",
        };
      }
      return {
        code: LIMITATION_CODES.readFailed,
        limitation: "Resource could not be read from the current Tencent Exmail session.",
      };
    }
  }

  function detectDeferredResponseType(response, buffer) {
    const contentType = normalizeSingleContentType(responseHeader(response, "content-type"));
    if (!contentType.valid) {
      return unsupportedDeferredType();
    }
    const signature = detectedSignature(buffer);
    const exactTypes = {
      "application/pdf": { type: "pdf", extension: "pdf", signature: "pdf" },
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        type: "docx", extension: "docx", signature: "zip",
      },
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        type: "xlsx", extension: "xlsx", signature: "zip",
      },
      "image/bmp": { type: "image", extension: "bmp", signature: "bmp" },
      "image/gif": { type: "image", extension: "gif", signature: "gif" },
      "image/jpeg": { type: "image", extension: "jpg", signature: "jpeg" },
      "image/jpg": { type: "image", extension: "jpg", signature: "jpeg" },
      "image/png": { type: "image", extension: "png", signature: "png" },
      "image/tiff": { type: "image", extension: "tiff", signature: "tiff" },
      "image/webp": { type: "image", extension: "webp", signature: "webp" },
    };
    if (contentType.value && contentType.value !== "application/octet-stream") {
      const expected = exactTypes[contentType.value];
      if (!expected) {
        return unsupportedDeferredType();
      }
      return signature && signature.kind === expected.signature
        ? { type: expected.type, extension: expected.extension }
        : conflictingDeferredType();
    }
    if (!signature) {
      return unsupportedDeferredType();
    }
    if (signature.type) {
      return { type: signature.type, extension: signature.extension };
    }
    if (signature.kind === "zip") {
      const officeExtension = strictOfficeDispositionExtension(
        responseHeader(response, "content-disposition"),
      );
      return officeExtension
        ? { type: officeExtension, extension: officeExtension }
        : unsupportedDeferredType();
    }
    return unsupportedDeferredType();
  }

  function normalizeSingleContentType(value) {
    const raw = normalizeText(value).toLowerCase();
    if (!raw) {
      return { valid: true, value: "" };
    }
    if (raw.includes(",")) {
      return { valid: false, value: "" };
    }
    const token = raw.split(";", 1)[0].trim();
    return {
      valid: /^[a-z0-9!#$&^_.+-]+\/[a-z0-9!#$&^_.+-]+$/.test(token),
      value: token,
    };
  }

  function responseHeader(response, name) {
    const headers = response && response.headers;
    if (!headers || typeof headers.get !== "function") {
      return "";
    }
    try {
      return String(headers.get(name) || "");
    } catch (error) {
      return "";
    }
  }

  function detectedSignature(buffer) {
    const bytes = buffer instanceof ArrayBuffer ? new Uint8Array(buffer) : null;
    if (!bytes) {
      return null;
    }
    if (hasBytePrefix(bytes, [0x25, 0x50, 0x44, 0x46, 0x2d])) {
      return { kind: "pdf", type: "pdf", extension: "pdf" };
    }
    if (hasBytePrefix(bytes, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) {
      return { kind: "png", type: "image", extension: "png" };
    }
    if (hasBytePrefix(bytes, [0xff, 0xd8, 0xff])) {
      return { kind: "jpeg", type: "image", extension: "jpg" };
    }
    if (
      hasBytePrefix(bytes, [0x47, 0x49, 0x46, 0x38, 0x37, 0x61]) ||
      hasBytePrefix(bytes, [0x47, 0x49, 0x46, 0x38, 0x39, 0x61])
    ) {
      return { kind: "gif", type: "image", extension: "gif" };
    }
    if (hasBytePrefix(bytes, [0x42, 0x4d])) {
      return { kind: "bmp", type: "image", extension: "bmp" };
    }
    if (
      hasBytePrefix(bytes, [0x49, 0x49, 0x2a, 0x00]) ||
      hasBytePrefix(bytes, [0x4d, 0x4d, 0x00, 0x2a])
    ) {
      return { kind: "tiff", type: "image", extension: "tiff" };
    }
    if (
      hasBytePrefix(bytes, [0x52, 0x49, 0x46, 0x46]) &&
      bytes.length >= 12 &&
      hasBytesAt(bytes, 8, [0x57, 0x45, 0x42, 0x50])
    ) {
      return { kind: "webp", type: "image", extension: "webp" };
    }
    if (hasBytePrefix(bytes, [0x50, 0x4b, 0x03, 0x04])) {
      return { kind: "zip", type: "", extension: "" };
    }
    return null;
  }

  function hasBytePrefix(bytes, expected) {
    return hasBytesAt(bytes, 0, expected);
  }

  function hasBytesAt(bytes, offset, expected) {
    if (bytes.length < offset + expected.length) {
      return false;
    }
    return expected.every((value, index) => bytes[offset + index] === value);
  }

  function strictOfficeDispositionExtension(value) {
    const parameters = strictDispositionParameters(value);
    if (!parameters) {
      return "";
    }
    const fields = parameters
      .filter((parameter) => parameter.name === "filename" || parameter.name === "filename*")
      .map((parameter) => parameter.value);
    if (fields.length !== 1) {
      return "";
    }
    const suffix = fields[0].toLowerCase().match(/\.([a-z0-9]+)$/);
    return suffix && ["docx", "xlsx"].includes(suffix[1]) ? suffix[1] : "";
  }

  function strictDispositionParameters(value) {
    const raw = String(value || "");
    let index = skipDispositionWhitespace(raw, 0);
    const dispositionEnd = readDispositionTokenEnd(raw, index);
    if (dispositionEnd === index) {
      return null;
    }
    index = skipDispositionWhitespace(raw, dispositionEnd);
    const parameters = [];
    const names = new Set();
    while (index < raw.length) {
      if (raw[index] !== ";") {
        return null;
      }
      index = skipDispositionWhitespace(raw, index + 1);
      const nameEnd = readDispositionTokenEnd(raw, index);
      if (nameEnd === index) {
        return null;
      }
      const name = raw.slice(index, nameEnd).toLowerCase();
      index = skipDispositionWhitespace(raw, nameEnd);
      if (raw[index] !== "=") {
        return null;
      }
      index = skipDispositionWhitespace(raw, index + 1);
      const parsed = readDispositionValue(raw, index);
      if (!parsed) {
        return null;
      }
      index = skipDispositionWhitespace(raw, parsed.end);
      if (index < raw.length && raw[index] !== ";") {
        return null;
      }
      if (names.has(name)) {
        return null;
      }
      names.add(name);
      parameters.push({ name, value: parsed.value });
    }
    return parameters;
  }

  function readDispositionValue(raw, start) {
    if (raw[start] !== '"') {
      const end = readDispositionTokenEnd(raw, start);
      return end === start ? null : { value: raw.slice(start, end), end };
    }
    let index = start + 1;
    let decoded = "";
    while (index < raw.length) {
      const character = raw[index];
      if (character === '"') {
        return { value: decoded, end: index + 1 };
      }
      if (character === "\\") {
        index += 1;
        if (index >= raw.length || isDispositionControl(raw[index])) {
          return null;
        }
        decoded += raw[index];
        index += 1;
        continue;
      }
      if (isDispositionControl(character)) {
        return null;
      }
      decoded += character;
      index += 1;
    }
    return null;
  }

  function readDispositionTokenEnd(raw, start) {
    let index = start;
    while (index < raw.length && isDispositionTokenCharacter(raw[index])) {
      index += 1;
    }
    return index;
  }

  function isDispositionTokenCharacter(character) {
    return /^[!#$%&'*+\-.^_`|~0-9A-Za-z]$/.test(character);
  }

  function skipDispositionWhitespace(raw, start) {
    let index = start;
    while (index < raw.length && (raw[index] === " " || raw[index] === "\t")) {
      index += 1;
    }
    return index;
  }

  function isDispositionControl(character) {
    const code = character.charCodeAt(0);
    return code < 0x20 || code === 0x7f;
  }

  function unsupportedDeferredType() {
    return {
      code: LIMITATION_CODES.unsupported,
      limitation: "Resource type is not supported.",
    };
  }

  function conflictingDeferredType() {
    return {
      code: LIMITATION_CODES.readFailed,
      limitation: "Resource response type did not match its content.",
    };
  }

  function genericAttachmentFilename(ordinal, extension) {
    return `attachment-${ordinal}.${extension}`;
  }

  function clearMutableBuffer(buffer) {
    if (!(buffer instanceof ArrayBuffer)) {
      return;
    }
    try {
      new Uint8Array(buffer).fill(0);
    } catch (error) {
      return;
    }
  }

  async function readBoundedResponse(response, limits, totalBytes, deadline, controller) {
    const body = response.body;
    if (body && typeof body.getReader === "function") {
      return readBoundedStream(body, limits, totalBytes, deadline, controller);
    }
    return {
      code: LIMITATION_CODES.readFailed,
      limitation: "Resource response body could not be read with bounded streaming.",
    };
  }

  async function readBoundedStream(body, limits, totalBytes, deadline, controller) {
    const reader = body.getReader();
    const chunks = [];
    let byteSize = 0;
    try {
      while (true) {
        const item = await withDeadline(
          reader.read(),
          deadline,
          () => {
            abortController(controller);
            cancelReader(reader);
          },
        );
        if (!item || item.done) {
          break;
        }
        const chunk = streamChunk(item.value);
        if (!chunk) {
          await cancelReader(reader);
          return {
            code: LIMITATION_CODES.readFailed,
            limitation: "Resource could not be read from the current Tencent Exmail session.",
          };
        }
        const nextSize = byteSize + chunk.byteLength;
        const limitation = byteLimitation(nextSize, limits, totalBytes);
        if (limitation) {
          await cancelReader(reader);
          return { code: LIMITATION_CODES.frontendLimit, limitation };
        }
        if (chunk.byteLength > 0) {
          chunks.push(new Uint8Array(chunk));
          byteSize = nextSize;
        }
      }
      return { buffer: concatenateChunks(chunks, byteSize) };
    } catch (error) {
      cancelReader(reader);
      if (isDeadlineError(error)) {
        return {
          code: LIMITATION_CODES.timeout,
          limitation: "Resource collection deadline expired; body analysis continued without this resource.",
        };
      }
      return {
        code: LIMITATION_CODES.readFailed,
        limitation: "Resource could not be read from the current Tencent Exmail session.",
      };
    } finally {
      releaseReader(reader);
    }
  }

  function streamChunk(value) {
    if (value instanceof Uint8Array) {
      return value;
    }
    if (value instanceof ArrayBuffer) {
      return new Uint8Array(value);
    }
    if (value && ArrayBuffer.isView(value)) {
      return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    }
    return null;
  }

  function concatenateChunks(chunks, byteSize) {
    const combined = new Uint8Array(byteSize);
    let offset = 0;
    for (const chunk of chunks) {
      combined.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return combined.buffer;
  }

  function cancelResponseBody(response) {
    const body = response && response.body;
    if (!body) {
      return;
    }
    if (typeof body.cancel === "function") {
      try {
        Promise.resolve(body.cancel()).catch(() => {});
      } catch (error) {
        return;
      }
      return;
    }
    if (typeof body.getReader === "function") {
      const reader = body.getReader();
      cancelReader(reader);
      releaseReader(reader);
    }
  }

  function cancelReader(reader) {
    if (!reader || typeof reader.cancel !== "function") {
      return;
    }
    try {
      Promise.resolve(reader.cancel()).catch(() => {});
    } catch (error) {
      return;
    }
  }

  function releaseReader(reader) {
    if (!reader || typeof reader.releaseLock !== "function") {
      return;
    }
    try {
      reader.releaseLock();
    } catch (error) {
      return;
    }
  }

  function byteLimitation(byteSize, limits, totalBytes) {
    if (!byteSize) {
      return "";
    }
    if (byteSize > limits.maxFileBytes) {
      return `Resource exceeds the ${limits.maxFileBytes}-byte per-file limit.`;
    }
    if (totalBytes + byteSize > limits.maxTotalBytes) {
      return `Resource exceeds the ${limits.maxTotalBytes}-byte total frontend limit.`;
    }
    return "";
  }

  function responseByteSize(response) {
    const headers = response.headers;
    if (!headers || typeof headers.get !== "function") {
      return null;
    }
    const value = normalizeText(headers.get("content-length"));
    if (!/^\d+$/.test(value)) {
      return null;
    }
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : null;
  }

  function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    const chunkSize = 32768;
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return root.btoa(binary);
  }

  function resolveResourceUrl(value, baseHref) {
    if (!value || !baseHref) {
      return "";
    }
    try {
      const base = new URL(baseHref);
      const resolved = new URL(value, base);
      if (base.origin !== EXMAIL_ORIGIN || resolved.origin !== EXMAIL_ORIGIN) {
        return "";
      }
      if (resolved.protocol !== "https:" || resolved.username || resolved.password) {
        return "";
      }
      return resolved.href;
    } catch (error) {
      return "";
    }
  }

  function isApprovedResourceEndpoint(value) {
    try {
      const url = new URL(value);
      return url.origin === EXMAIL_ORIGIN &&
        APPROVED_RESOURCE_PATHS.includes(url.pathname) &&
        url.search.length > 1;
    } catch (error) {
      return false;
    }
  }

  function responseMatchesRequestedEndpoint(response, requestedUrl) {
    if (response.redirected === true) {
      return false;
    }
    if (typeof response.url !== "string" || !response.url) {
      return true;
    }
    const resolved = resolveResourceUrl(response.url, requestedUrl);
    return resolved === requestedUrl && isApprovedResourceEndpoint(resolved);
  }

  function documentHref(doc) {
    if (doc && typeof doc.baseURI === "string" && doc.baseURI) {
      return doc.baseURI;
    }
    if (doc && doc.location && typeof doc.location.href === "string") {
      return doc.location.href;
    }
    return "";
  }

  function boundedLimits(value) {
    const requested = value || {};
    return {
      maxFiles: downwardLimit(requested.maxFiles, MAX_RESOURCE_COUNT),
      maxFileBytes: downwardLimit(requested.maxFileBytes, MAX_RESOURCE_BYTES),
      maxTotalBytes: downwardLimit(requested.maxTotalBytes, MAX_TOTAL_RESOURCE_BYTES),
      perResourceTimeoutMs: downwardLimit(
        requested.perResourceTimeoutMs,
        MAX_PER_RESOURCE_TIMEOUT_MS,
      ),
      overallTimeoutMs: downwardLimit(
        requested.overallTimeoutMs,
        MAX_OVERALL_RESOURCE_TIMEOUT_MS,
      ),
    };
  }

  function addResourceLimitation(result, limitation, omitted) {
    if (result.resource_limitations.length < MAX_RESOURCE_LIMITATIONS) {
      result.resource_limitations.push(limitation);
      return;
    }
    omitted.count += 1;
  }

  function appendAggregateOmission(result, omittedCount) {
    if (omittedCount <= 0) {
      return;
    }
    if (result.resource_limitations.length >= MAX_RESOURCE_LIMITATIONS) {
      result.resource_limitations.pop();
    }
    result.resource_limitations.push(limitedMetadata(
      { filename: "additional-resources", type: "unsupported", size: 0 },
      LIMITATION_CODES.candidateOmission,
      "One or more additional current-message resource candidates were omitted by bounded collection.",
    ));
  }

  function withDeadline(promise, deadline, onTimeout) {
    const remaining = Math.max(0, deadline - Date.now());
    return new Promise((resolve, reject) => {
      let settled = false;
      const timer = root.setTimeout(() => {
        if (settled) {
          return;
        }
        settled = true;
        try {
          onTimeout();
        } finally {
          reject(deadlineError());
        }
      }, remaining);
      Promise.resolve(promise).then(
        (value) => {
          if (!settled) {
            settled = true;
            root.clearTimeout(timer);
            resolve(value);
          }
        },
        (error) => {
          if (!settled) {
            settled = true;
            root.clearTimeout(timer);
            reject(error);
          }
        },
      );
    });
  }

  function abortController(controller) {
    if (controller && typeof controller.abort === "function") {
      controller.abort();
    }
  }

  function deadlineError() {
    const error = new Error("Resource collection deadline expired.");
    error.name = "ResourceDeadlineError";
    return error;
  }

  function isDeadlineError(error) {
    return Boolean(error && error.name === "ResourceDeadlineError");
  }

  function downwardLimit(value, maximum) {
    return Number.isSafeInteger(value) && value > 0 ? Math.min(value, maximum) : maximum;
  }

  function declaredByteSize(value) {
    const normalized = normalizeText(value);
    if (!/^\d+$/.test(normalized)) {
      return 0;
    }
    const parsed = Number(normalized);
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
  }

  function limitedMetadata(metadata, code, limitation) {
    return {
      code,
      filename: metadata.filename,
      type: metadata.type || "unsupported",
      size: metadata.size,
      limitation,
    };
  }

  function safeFilename(value) {
    const normalized = normalizeText(value).replace(/[\u0000-\u001f\u007f]/g, "");
    const basename = normalized.replaceAll("\\", "/").split("/").pop() || "";
    const safe = basename.replace(/[<>:"|?*]/g, "_").replace(/^\.+/, "").trim();
    return safe.slice(0, 120) || "resource";
  }

  function boundedText(value, limit) {
    return normalizeText(value).slice(0, limit);
  }

  function elementText(element) {
    return normalizeText(element ? element.innerText || element.textContent || "" : "");
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function attribute(element, name) {
    if (!element || typeof element.getAttribute !== "function") {
      return "";
    }
    return String(element.getAttribute(name) || "");
  }

  function hasAttribute(element, name) {
    return Boolean(element && typeof element.hasAttribute === "function" && element.hasAttribute(name));
  }

  root.EmailAssistantCurrentMessageCollector = Object.freeze({
    MAX_THREAD_SEGMENTS,
    MAX_RESOURCE_COUNT,
    MAX_RESOURCE_CANDIDATES,
    MAX_RESOURCE_LIMITATIONS,
    MAX_RESOURCE_BYTES,
    MAX_TOTAL_RESOURCE_BYTES,
    SUPPORTED_RESOURCE_TYPES,
    normalizeResourceType,
    cleanVisibleMessageBody: cleanMessageBody,
    extractVisibleMessageContext,
    extractVisibleThreadSegments,
    collectVisibleResources,
  });
})(window);
