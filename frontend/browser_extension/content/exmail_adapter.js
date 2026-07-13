/* global chrome */
(function () {
  const MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL";
  const REVALIDATE_MESSAGE_TYPE = "REVALIDATE_CURRENT_EMAIL";
  const MIN_BODY_LENGTH = 5;
  const EMPTY_PAYLOAD = {
    subject: "",
    from: "",
    to: [],
    sent_at: "",
    body_text: "",
    attachments: [],
  };
  const MAX_ATTACHMENTS = 8;
  const EXMAIL_ORIGIN = "https://exmail.qq.com";
  const APPROVED_RESOURCE_PATHS = ["/cgi-bin/download", "/cgi-bin/viewfile"];
  const ATTACHMENT_PATTERN =
    /([A-Za-z0-9][A-Za-z0-9 _.,()[\]\-+&'#]*\.(pdf|docx?|xlsx?|pptx?|csv|zip|rar|7z|png|jpe?g|gif|txt))(?:\s*\(([^)\n]{1,40})\))?/gi;
  const BODY_SELECTORS = [
    "#mailContentContainer",
    "#mailContent",
    ".mail_content",
    ".mail-detail-content",
    ".mail-content",
    ".readmail_content",
  ];
  const SUBJECT_SELECTORS = [
    "#subject",
    ".subject",
    ".mail_subject",
    ".mail-subject",
    "[role='heading']",
    "h1",
    "h2",
  ];
  const MESSAGE_CONTEXT_SUBJECT_SELECTORS = [
    "#subject",
    ".subject",
    ".mail_subject",
    ".mail-subject",
  ];

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || ![MESSAGE_TYPE, REVALIDATE_MESSAGE_TYPE].includes(message.type)) {
      return false;
    }

    const task = message.type === MESSAGE_TYPE
      ? extractCurrentEmail()
      : revalidateCurrentEmail();
    task
      .catch(() => message.type === MESSAGE_TYPE ? safeExtractionFailure() : safeRevalidationFailure())
      .then(sendResponse);
    return true;
  });

  async function extractCurrentEmail() {
    const extraction = findCurrentEmail();
    if (!extraction.result.ok) {
      return extraction.result;
    }
    const result = await collectCurrentMessageContext(extraction);
    return {
      ...result,
      message_fingerprint: messageFingerprint(result.payload),
    };
  }

  async function revalidateCurrentEmail() {
    const extraction = findCurrentEmail();
    if (!extraction.result.ok) {
      return safeRevalidationFailure();
    }
    const result = await collectCurrentMessageContext(extraction);
    return {
      ok: true,
      message_fingerprint: messageFingerprint(result.payload),
    };
  }

  function findCurrentEmail() {
    const documents = collectAccessibleDocuments(window);
    const selected = getSelectedEmailContent(documents);
    if (selected) {
      const metadata = extractFromDocument(selected.document, true);
      return extractionContext({
        ok: true,
        source: "selected_text",
        payload: {
          subject: metadata.subject || selected.document.title || document.title || "Tencent Exmail selected email content",
          from: metadata.from || "",
          to: metadata.to || [],
          sent_at: metadata.sent_at || "",
          body_text: selected.text,
          attachments: metadata.attachments || [],
        },
      }, selected.document, findKnownBodyElement(selected.document));
    }

    for (const doc of documents) {
      const payload = extractFromDocument(doc, false);
      if (payload.body_text) {
        return extractionContext(
          { ok: true, source: "dom", payload },
          doc,
          findKnownBodyElement(doc),
        );
      }
    }

    for (const doc of documents) {
      const payload = extractFromDocument(doc, true);
      if (payload.body_text) {
        return extractionContext(
          { ok: true, source: "dom_fallback", payload },
          doc,
          findKnownBodyElement(doc),
        );
      }
    }

    return extractionContext({
      ok: false,
      error: "Open a Tencent Exmail message or select email body text from that opened message first. The fallback is user-selected email content only, not arbitrary webpage analysis.",
    });
  }

  function extractionContext(result, selectedDocument, currentMessageRoot) {
    return { result, document: selectedDocument || null, currentMessageRoot: currentMessageRoot || null };
  }

  async function collectCurrentMessageContext(extraction) {
    const payload = {
      ...extraction.result.payload,
      thread_segments: [],
      attachment_files: [],
      resource_limitations: [],
    };
    const collector = window.EmailAssistantCurrentMessageCollector;
    if (!collector || !extraction.currentMessageRoot) {
      payload.resource_limitations.push(
        safeResourceLimitation(
          "resource_unavailable",
          "Current-message resources could not be collected without a verified collector and message root.",
        ),
      );
      return { ...extraction.result, payload };
    }

    try {
      payload.thread_segments = projectItems(
        collector.extractVisibleThreadSegments(extraction.document, {
          currentMessageRoot: extraction.currentMessageRoot,
        }),
        ["position", "from", "to", "sent_at", "timestamp_text", "subject", "body_text"],
      );
    } catch (error) {
      payload.resource_limitations.push(
        safeResourceLimitation("resource_unavailable", "Visible thread segments could not be collected safely."),
      );
    }

    if (extraction.document !== document) {
      payload.resource_limitations.push(
        safeResourceLimitation(
          "resource_unavailable",
          "Resources are unavailable outside the verified top-level current-message document; body analysis continued.",
        ),
      );
      return { ...extraction.result, payload };
    }

    try {
      const resourceContext = findVerifiedResourceContext(
        extraction.document,
        extraction.currentMessageRoot,
      );
      if (!resourceContext) {
        payload.resource_limitations.push(
          safeResourceLimitation(
            "resource_unavailable",
            "Resources are unavailable because verified current-message resource controls were not established; body analysis continued.",
          ),
        );
        return { ...extraction.result, payload };
      }
      const resources = await collector.collectVisibleResources(extraction.document, {
        topLevelDocument: document,
        currentMessageRoot: extraction.currentMessageRoot,
        currentMessageContainer: resourceContext.currentMessageContainer,
        verifiedResourceCandidates: resourceContext.verifiedResourceCandidates,
        resourceControlsVerified: true,
      });
      payload.attachment_files = projectItems(resources && resources.attachment_files, [
        "filename", "type", "size", "content_base64",
      ]);
      payload.resource_limitations.push(
        ...projectItems(resources && resources.resource_limitations, [
          "code", "filename", "type", "size", "limitation",
        ]),
      );
    } catch (error) {
      payload.resource_limitations.push(
        safeResourceLimitation("resource_read_failed", "Current-message resources could not be collected safely."),
      );
    }
    return { ...extraction.result, payload };
  }

  function findVerifiedResourceContext(doc, currentMessageRoot) {
    const subject = uniqueVisibleSubject(doc, currentMessageRoot);
    const header = uniqueVisibleHeaderEvidence(doc, currentMessageRoot);
    if (!subject || !header) {
      return null;
    }
    const currentMessageContainer = minimumCommonVisibleAncestor(
      currentMessageRoot,
      subject,
      header,
      doc,
    );
    if (
      !currentMessageContainer ||
      (currentMessageContainer.parentElement || currentMessageContainer.parentNode) !== (doc && doc.body) ||
      (currentMessageRoot.parentElement || currentMessageRoot.parentNode) !== currentMessageContainer ||
      hasAmbiguousBodyRoots(doc && doc.body, currentMessageRoot, doc)
    ) {
      return null;
    }

    const collector = window.EmailAssistantCurrentMessageCollector;
    const candidateCap = collector && Number.isInteger(collector.MAX_RESOURCE_CANDIDATES)
      ? collector.MAX_RESOURCE_CANDIDATES
      : 20;
    const baseHref = documentHref(doc);
    const verifiedResourceCandidates = resourceSiblingSubtrees(
      currentMessageRoot,
      currentMessageContainer,
    )
      .flatMap((subtree) => [subtree, ...descendantElements(subtree)])
      .filter((candidate) => isApprovedResourceControl(candidate, baseHref, doc))
      .slice(0, candidateCap + 1)
    if (verifiedResourceCandidates.length === 0) {
      return null;
    }
    return { currentMessageContainer, verifiedResourceCandidates };
  }

  function uniqueVisibleSubject(doc, currentMessageRoot) {
    const candidates = uniqueElements(
      querySelectorAll(doc && doc.body, MESSAGE_CONTEXT_SUBJECT_SELECTORS.join(", ")),
    ).filter((candidate) =>
      !containsElement(currentMessageRoot, candidate) &&
      !containsElement(candidate, currentMessageRoot) &&
      isVisibleElementInDocument(candidate, doc) &&
      normalizeText(candidate.innerText || candidate.textContent),
    );
    return candidates.length === 1 ? candidates[0] : null;
  }

  function uniqueVisibleHeaderEvidence(doc, currentMessageRoot) {
    const candidates = descendantElements(doc && doc.body).filter((candidate) =>
      !containsElement(currentMessageRoot, candidate) &&
      !containsElement(candidate, currentMessageRoot) &&
      isVisibleElementInDocument(candidate, doc) &&
      hasHeaderLabels(candidate),
    );
    const minimal = candidates.filter((candidate) =>
      !candidates.some((other) => other !== candidate && containsElement(candidate, other)),
    );
    return minimal.length === 1 ? minimal[0] : null;
  }

  function hasHeaderLabels(element) {
    const text = normalizeText(element ? element.innerText || element.textContent : "");
    const hasFrom = /(?:^|\s)(?:From|\u53d1\u4ef6\u4eba)\s*[:\uff1a]/i.test(text);
    const hasTo = /(?:^|\s)(?:To|\u6536\u4ef6\u4eba)\s*[:\uff1a]/i.test(text);
    return hasFrom && hasTo;
  }

  function minimumCommonVisibleAncestor(bodyRoot, subject, header, doc) {
    let current = bodyRoot;
    while (current) {
      if (
        containsElement(current, subject) &&
        containsElement(current, header) &&
        isVisibleElementInDocument(current, doc)
      ) {
        const tagName = String(current.tagName || "").toUpperCase();
        return current !== (doc && doc.body) && !["BODY", "HTML"].includes(tagName)
          ? current
          : null;
      }
      current = current.parentElement || current.parentNode;
    }
    return null;
  }

  function hasAmbiguousBodyRoots(container, currentMessageRoot, doc) {
    const roots = uniqueElements([
      ...(isKnownBodyRoot(container) ? [container] : []),
      ...querySelectorAll(container, BODY_SELECTORS.join(", ")),
    ])
      .filter((candidate) =>
        isVisibleElementInDocument(candidate, doc) &&
        normalizeText(candidate.innerText || candidate.textContent).length >= MIN_BODY_LENGTH,
      );
    return roots.length !== 1 || roots[0] !== currentMessageRoot;
  }

  function isKnownBodyRoot(element) {
    if (!element) {
      return false;
    }
    const id = String(
      element.id || (typeof element.getAttribute === "function" ? element.getAttribute("id") : "") || "",
    );
    const className = String(
      element.className ||
      (typeof element.getAttribute === "function" ? element.getAttribute("class") : "") ||
      "",
    );
    const classes = className.split(/\s+/).filter(Boolean);
    return BODY_SELECTORS.some((selector) =>
      selector.startsWith("#")
        ? id === selector.slice(1)
        : selector.startsWith(".") && classes.includes(selector.slice(1)),
    );
  }

  function resourceSiblingSubtrees(bodyRoot, container) {
    const parent = bodyRoot && (bodyRoot.parentElement || bodyRoot.parentNode);
    if (parent !== container) {
      return [];
    }
    return Array.from(container.children || []).filter((child) => child !== bodyRoot);
  }

  function isApprovedResourceControl(element, baseHref, doc) {
    if (!element || !isVisibleElementInDocument(element, doc)) {
      return false;
    }
    const tagName = String(element.tagName || "").toUpperCase();
    const attributeName = tagName === "A" ? "href" : tagName === "IMG" ? "src" : "";
    if (!attributeName || typeof element.getAttribute !== "function") {
      return false;
    }
    return isApprovedResourceUrl(element.getAttribute(attributeName), baseHref);
  }

  function isApprovedResourceUrl(value, baseHref) {
    try {
      const resolved = new URL(String(value || ""), baseHref);
      return resolved.origin === EXMAIL_ORIGIN &&
        resolved.protocol === "https:" &&
        !resolved.username &&
        !resolved.password &&
        APPROVED_RESOURCE_PATHS.includes(resolved.pathname) &&
        resolved.search.length > 1;
    } catch (error) {
      return false;
    }
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

  function descendantElements(root) {
    if (!root) {
      return [];
    }
    const descendants = [];
    for (const child of Array.from(root.children || [])) {
      descendants.push(child, ...descendantElements(child));
    }
    return descendants;
  }

  function uniqueElements(values) {
    return Array.from(new Set(values));
  }

  function querySelectorAll(container, selector) {
    if (!container || typeof container.querySelectorAll !== "function") {
      return [];
    }
    return Array.from(container.querySelectorAll(selector) || []);
  }

  function containsElement(container, element) {
    if (!container || !element) {
      return false;
    }
    if (typeof container.contains === "function") {
      return container.contains(element);
    }
    let current = element;
    while (current) {
      if (current === container) {
        return true;
      }
      current = current.parentElement || current.parentNode;
    }
    return false;
  }

  function projectItems(value, allowedFields) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .filter((item) => item && typeof item === "object" && !Array.isArray(item))
      .map((item) => {
        const projected = {};
        for (const field of allowedFields) {
          projected[field] = Object.prototype.hasOwnProperty.call(item, field)
            ? primitiveValue(item[field])
            : "";
        }
        return projected;
      });
  }

  function safeResourceLimitation(code, limitation) {
    return { code, filename: "resource", type: "unsupported", size: 0, limitation };
  }

  function primitiveValue(value) {
    return ["string", "number", "boolean"].includes(typeof value) ? value : "";
  }

  function safeExtractionFailure() {
    return {
      ok: false,
      error: "Current Tencent Exmail message extraction failed safely. Please reopen the message and try again.",
    };
  }

  function safeRevalidationFailure() {
    return {
      ok: false,
      error: "Current Tencent Exmail message could not be revalidated safely.",
    };
  }

  function messageFingerprint(payload) {
    const email = payload || {};
    const source = JSON.stringify([
      fingerprintValues([email.subject, email.from, email.to, email.sent_at, email.body_text]),
      fingerprintItems(email.attachments, ["filename", "size", "type"]),
      fingerprintItems(email.thread_segments, [
        "position", "from", "to", "sent_at", "timestamp_text", "subject", "body_text",
      ]),
      fingerprintItems(email.attachment_files, ["filename", "type", "size", "content_base64"]),
      fingerprintItems(email.resource_limitations, [
        "code", "filename", "type", "size", "limitation",
      ]),
    ]);
    const first = fingerprintHash(source, 0x811c9dc5);
    const second = fingerprintHash(source, 0x9e3779b9);
    return `msg-v1-${hex32(first)}${hex32(second)}`;
  }

  function fingerprintItems(items, fields) {
    return Array.isArray(items)
      ? items.map((item) => fingerprintValues(fields.map((field) => item && item[field])))
      : [];
  }

  function fingerprintValues(values) {
    return (Array.isArray(values) ? values : [values]).map((value) => {
      if (Array.isArray(value)) {
        return fingerprintValues(value);
      }
      return ["string", "number", "boolean"].includes(typeof value)
        ? normalizeText(String(value))
        : "";
    });
  }

  function fingerprintHash(value, seed) {
    let hash = seed >>> 0;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193) >>> 0;
    }
    return hash;
  }

  function hex32(value) {
    return (value >>> 0).toString(16).padStart(8, "0");
  }

  function collectAccessibleDocuments(rootWindow) {
    const documents = [];
    visitWindow(rootWindow, documents, true);
    return documents;
  }

  function visitWindow(targetWindow, documents, isRootWindow) {
    try {
      if (!isRootWindow && !isVisibleFrameWindow(targetWindow)) {
        return;
      }
      if (targetWindow.document) {
        documents.push(targetWindow.document);
      }
      for (let index = 0; index < targetWindow.frames.length; index += 1) {
        visitWindow(targetWindow.frames[index], documents, false);
      }
    } catch (error) {
      return;
    }
  }

  function isVisibleFrameWindow(targetWindow) {
    const frame = targetWindow.frameElement;
    return Boolean(frame && isVisibleElementInDocument(frame, frame.ownerDocument || null));
  }

  function extractFromDocument(doc, allowDocumentBodyFallback) {
    if (!hasMessageContext(doc, allowDocumentBodyFallback)) {
      return EMPTY_PAYLOAD;
    }

    const body = findBody(doc, allowDocumentBodyFallback);
    if (!body) {
      return EMPTY_PAYLOAD;
    }
    const bodyElement = findBodyElement(doc, allowDocumentBodyFallback);

    return {
      subject: findSubject(doc) || doc.title || "Tencent Exmail message",
      from: findLabeledText(doc, ["From", "\u53d1\u4ef6\u4eba"]),
      to: splitRecipients(findLabeledText(doc, ["To", "\u6536\u4ef6\u4eba"])),
      sent_at: findLabeledText(doc, ["Date", "Sent", "\u65f6\u95f4", "\u53d1\u9001\u65f6\u95f4"]),
      body_text: body,
      attachments: findAttachments(doc, bodyElement),
    };
  }

  function findSubject(doc) {
    return firstText(doc, SUBJECT_SELECTORS);
  }

  function findBody(doc, allowDocumentBodyFallback) {
    const element = findBodyElement(doc, allowDocumentBodyFallback);
    const body = normalizeText(element ? element.innerText || element.textContent : "");
    if (body.length >= MIN_BODY_LENGTH) {
      return body;
    }
    return "";
  }

  function findBodyElement(doc, allowDocumentBodyFallback) {
    const knownBody = findKnownBodyElement(doc);
    if (knownBody) {
      return knownBody;
    }
    if (hasKnownBodyCandidate(doc)) {
      return null;
    }

    if (
      allowDocumentBodyFallback &&
      isReadMessageDocument(doc) &&
      doc.body &&
      isVisibleElementInDocument(doc.body, doc) &&
      normalizeText(doc.body.innerText || doc.body.textContent).length >= MIN_BODY_LENGTH
    ) {
      return doc.body;
    }

    return null;
  }

  function findKnownBodyElement(doc) {
    for (const selector of BODY_SELECTORS) {
      const element = doc.querySelector(selector);
      const text = normalizeText(element ? element.innerText || element.textContent : "");
      if (text.length >= MIN_BODY_LENGTH && isVisibleElementInDocument(element, doc)) {
        return element;
      }
    }
    return null;
  }

  function hasKnownBodyCandidate(doc) {
    return BODY_SELECTORS.some((selector) => {
      const element = doc.querySelector(selector);
      return normalizeText(element ? element.innerText || element.textContent : "").length >= MIN_BODY_LENGTH;
    });
  }

  function hasMessageContext(doc, allowDocumentBodyFallback) {
    return Boolean(isReadMessageDocument(doc) && findBodyElement(doc, allowDocumentBodyFallback));
  }

  function isReadMessageDocument(doc) {
    const markerText = normalizeText(doc.body ? doc.body.innerText : "");
    if (!markerText) {
      return false;
    }

    return Boolean(hasSubjectContext(doc) || hasHeaderContext(doc));
  }

  function hasSubjectContext(doc) {
    return Boolean(firstText(doc, MESSAGE_CONTEXT_SUBJECT_SELECTORS));
  }

  function hasHeaderContext(doc) {
    const lines = String(doc.body ? doc.body.innerText || "" : "")
      .split(/\r?\n/)
      .map((line) => normalizeText(line))
      .filter(Boolean);

    return lines.some((line) => {
      return (
        line.startsWith("From:") ||
        line.startsWith("To:") ||
        line.startsWith("\u53d1\u4ef6\u4eba") ||
        line.startsWith("\u6536\u4ef6\u4eba")
      );
    });
  }

  function firstText(doc, selectors) {
    for (const selector of selectors) {
      const element = doc.querySelector(selector);
      const text = normalizeText(element ? element.innerText || element.textContent : "");
      if (text && isVisibleElementInDocument(element, doc)) {
        return text;
      }
    }
    return "";
  }

  function findLabeledText(doc, labels) {
    const lines = String(doc.body ? doc.body.innerText || "" : "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    for (const label of labels) {
      for (const line of lines) {
        const normalized = normalizeText(line);
        if (normalized.startsWith(`${label}:`) || normalized.startsWith(`${label}\uff1a`)) {
          return normalized.slice(label.length + 1).trim();
        }
      }
    }
    return "";
  }

  function splitRecipients(value) {
    if (!value) {
      return [];
    }
    return value.split(/[;,\uff1b\uff0c]/).map((item) => item.trim()).filter(Boolean);
  }

  function findAttachments(doc, bodyElement) {
    const sources = [];
    if (bodyElement) {
      sources.push(bodyElement.innerText || bodyElement.textContent || "");
    } else if (doc.body) {
      sources.push(doc.body.innerText || doc.body.textContent || "");
    }

    const attachments = [];
    const seen = new Set();
    for (const source of sources) {
      ATTACHMENT_PATTERN.lastIndex = 0;
      let match = ATTACHMENT_PATTERN.exec(String(source || ""));
      while (match && attachments.length < MAX_ATTACHMENTS) {
        const filename = normalizeAttachmentFilename(match[1]);
        const type = String(match[2] || "").toLowerCase();
        const size = normalizeText(match[3] || "");
        const key = filename.toLowerCase();
        if (filename && !seen.has(key)) {
          attachments.push({ filename, size, type });
          seen.add(key);
        }
        match = ATTACHMENT_PATTERN.exec(String(source || ""));
      }
    }
    return attachments;
  }

  function normalizeAttachmentFilename(value) {
    return normalizeText(value).replace(/^[\s:：,，;；-]+|[\s:：,，;；-]+$/g, "");
  }

  function getSelectedEmailContent(documents) {
    for (const doc of documents) {
      if (!isReadMessageDocument(doc)) {
        continue;
      }

      const view = doc.defaultView;
      if (!view || !view.getSelection) {
        continue;
      }

      const selection = view.getSelection();
      const text = normalizeText(selection.toString());
      if (text && selectionBelongsToMessage(doc, selection)) {
        return { document: doc, text };
      }
    }
    return null;
  }

  function selectionBelongsToMessage(doc, selection) {
    if (!selection.rangeCount) {
      return false;
    }

    const node = selection.getRangeAt(0).commonAncestorContainer;
    const element = node.nodeType === 1 ? node : node.parentElement || node.parentNode;
    if (!isVisibleElementInDocument(element, doc)) {
      return false;
    }
    const bodyElement = findKnownBodyElement(doc);
    if (bodyElement) {
      return Boolean(element && (element === bodyElement || bodyElement.contains(element)));
    }

    return Boolean(
      element &&
        doc.body &&
        (element === doc.body || doc.body.contains(element)) &&
        !isLikelyExcludedUiElement(element, doc.body)
    );
  }

  function isLikelyExcludedUiElement(element, stopElement) {
    let current = element;
    while (current && current !== stopElement) {
      const marker = `${current.id || ""} ${current.className || ""}`.toLowerCase();
      if (/(folder|nav|menu|toolbar|sidebar|compose|search|maillist|mail-list)/.test(marker)) {
        return true;
      }
      current = current.parentElement || current.parentNode;
    }
    return false;
  }

  function isVisibleElementInDocument(element, doc) {
    if (!element) {
      return false;
    }
    let current = element;
    let reachedBody = !doc || !doc.body;
    while (current) {
      if (current.hidden || (current.hasAttribute && current.hasAttribute("hidden"))) {
        return false;
      }
      if (current.getAttribute && String(current.getAttribute("aria-hidden") || "").toLowerCase() === "true") {
        return false;
      }
      if (elementStyleHides(current, doc)) {
        return false;
      }
      if (doc && current === doc.body) {
        reachedBody = true;
      }
      current = current.parentElement || current.parentNode;
    }
    return reachedBody;
  }

  function elementStyleHides(element, doc) {
    const style = element.style || {};
    if (style.display === "none" || hiddenVisibility(style.visibility)) {
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

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }
})();
