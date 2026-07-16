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

    const candidates = minimalLegacyCandidates(
      queryAll(currentRoot, THREAD_SEGMENT_SELECTORS),
    ).filter((candidate) => isVisibleWithin(candidate, currentRoot, doc));
    if (!candidates.length || candidates.length > MAX_THREAD_SEGMENTS) {
      return fallbackVisibleMessageContext(currentRoot, doc);
    }

    const structuredFlags = candidates.map((candidate) =>
      hasStructuredSegmentFields(candidate),
    );
    let ordered;
    if (structuredFlags.every(Boolean)) {
      ordered = structuredSegments(candidates, doc, currentRoot);
    } else if (structuredFlags.some(Boolean)) {
      ordered = null;
    } else {
      ordered = legacySegments(candidates);
    }
    if (!ordered) {
      return fallbackVisibleMessageContext(currentRoot, doc);
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
    const explicitCurrentBody = uniqueExplicitCurrentBody(currentRoot, doc);
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
    };
  }

  function extractVisibleThreadSegments(doc, options) {
    return extractVisibleMessageContext(doc, options).thread_segments;
  }

  function emptyVisibleMessageContext(bodyText) {
    return {
      current_message: {
        from: "",
        to: "",
        sent_at: "",
        subject: "",
        body_text: bodyText || "",
      },
      thread_segments: [],
    };
  }

  function fallbackVisibleMessageContext(currentRoot, doc) {
    const explicitCurrentBody = uniqueExplicitCurrentBody(currentRoot, doc);
    if (explicitCurrentBody !== null) {
      return emptyVisibleMessageContext(explicitCurrentBody);
    }
    return emptyVisibleMessageContext();
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

  function legacySegments(candidates) {
    const segments = [];
    let remainingChars = MAX_THREAD_SOURCE_CHARS;
    for (const candidate of candidates) {
      const sourceText = elementRawText(candidate);
      if (!sourceText || sourceText.length > remainingChars) {
        return null;
      }
      const segment = parseLegacyMessageBlock(sourceText, remainingChars);
      if (!segment) {
        return null;
      }
      remainingChars -= sourceText.length;
      segments.push(segment);
    }
    return chronologicalSegments(segments);
  }

  function structuredSegments(candidates, doc, currentRoot) {
    const segments = [];
    let remainingChars = MAX_THREAD_SOURCE_CHARS;
    for (const candidate of candidates) {
      const bodySource = structuredFieldText(candidate, "body_text", doc, currentRoot, true);
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
        structuredFieldText(candidate, "sent_at", doc, currentRoot),
        MAX_METADATA_CHARS,
      );
      segments.push({
        _position: position,
        from: boundedText(structuredFieldText(candidate, "from", doc, currentRoot), MAX_METADATA_CHARS),
        to: boundedText(structuredFieldText(candidate, "to", doc, currentRoot), MAX_METADATA_CHARS),
        sent_at: sentAt,
        timestamp_text: boundedText(
          structuredFieldText(candidate, "timestamp_text", doc, currentRoot) || sentAt,
          MAX_METADATA_CHARS,
        ),
        subject: boundedText(
          structuredFieldText(candidate, "subject", doc, currentRoot),
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
    for (let index = 0; index < lines.length; index += 1) {
      const sourceLine = lines[index];
      const line = normalizeLine(sourceLine);
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
    const verifiedCandidates = Array.isArray(settings.verifiedResourceCandidates)
      ? settings.verifiedResourceCandidates
      : [];
    if (
      settings.resourceControlsVerified !== true ||
      settings.topLevelDocument !== doc ||
      !currentContainer ||
      (currentContainer.parentElement || currentContainer.parentNode) !== (doc && doc.body) ||
      !isInside(currentRoot, currentContainer) ||
      (currentRoot.parentElement || currentRoot.parentNode) !== currentContainer ||
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

    const limits = boundedLimits(settings.limits);
    const fetchImpl = typeof settings.fetchImpl === "function" ? settings.fetchImpl : root.fetch;
    const baseHref = settings.locationHref || documentHref(doc);
    const candidates = verifiedCandidates
      .slice(0, MAX_RESOURCE_CANDIDATES)
      .filter((element) =>
        isHostResourceControl(element) &&
        isInside(element, currentContainer) &&
        !hasKnownBodyAncestor(element, currentRoot, currentContainer) &&
        isVisibleWithin(element, currentContainer, doc),
      );
    const omitted = {
      count: Math.max(0, verifiedCandidates.length - MAX_RESOURCE_CANDIDATES),
    };
    const overallDeadline = Date.now() + limits.overallTimeoutMs;
    let transferCount = 0;
    let totalBytes = 0;

    for (let index = 0; index < candidates.length; index += 1) {
      if (Date.now() >= overallDeadline) {
        omitted.count += candidates.length - index;
        break;
      }
      const element = candidates[index];
      const metadata = resourceMetadata(element);
      if (!metadata.type) {
        addResourceLimitation(
          result,
          limitedMetadata(metadata, LIMITATION_CODES.unsupported, "Resource type is not supported."),
          omitted,
        );
        continue;
      }

      const resolvedUrl = resolveResourceUrl(resourceUrl(element), baseHref);
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

      const resourceDeadline = Math.min(
        overallDeadline,
        Date.now() + limits.perResourceTimeoutMs,
      );
      const collected = await fetchResource(
        fetchImpl,
        resolvedUrl,
        metadata,
        limits,
        totalBytes,
        resourceDeadline,
      );
      if (collected.file) {
        result.attachment_files.push(collected.file);
        totalBytes += collected.file.size;
      } else {
        addResourceLimitation(
          result,
          limitedMetadata(metadata, collected.code, collected.limitation),
          omitted,
        );
      }
    }
    appendAggregateOmission(result, omitted.count);
    return result;
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
      "mail-detail-content", "mail-content", "mail_content", "readmail_content",
    ].some((className) => classes.includes(className));
  }

  function styleHides(element, doc) {
    const inlineStyle = element.style || {};
    if (inlineStyle.display === "none" || hiddenVisibility(inlineStyle.visibility)) {
      return true;
    }
    const view = doc && doc.defaultView;
    if (!view || typeof view.getComputedStyle !== "function") {
      return false;
    }
    try {
      const computed = view.getComputedStyle(element);
      return computed.display === "none" || hiddenVisibility(computed.visibility);
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
    return (
      attribute(element, "data-resource-url") ||
      attribute(element, "href") ||
      attribute(element, "src")
    );
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

  async function fetchResource(fetchImpl, url, metadata, limits, totalBytes, deadline) {
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
        return { code: LIMITATION_CODES.frontendLimit, limitation: actualLimitation };
      }
      return {
        file: {
          filename: metadata.filename,
          type: metadata.type,
          size: byteSize,
          content_base64: arrayBufferToBase64(buffer),
        },
      };
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
