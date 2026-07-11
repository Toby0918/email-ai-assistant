/* global chrome */
(function () {
  const MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL";
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
  const CURRENT_MESSAGE_CONTAINER_ATTRIBUTE = "data-email-current-message-container";
  const HOST_RESOURCE_CONTROLS_SELECTOR = "[data-email-host-resource-controls='true']";
  const HOST_RESOURCE_SELECTOR = [
    "[data-email-host-attachment='true']",
    "[data-email-host-inline-resource='true']",
  ].join(", ");
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
    if (!message || message.type !== MESSAGE_TYPE) {
      return false;
    }

    extractCurrentEmail()
      .catch(() => safeExtractionFailure())
      .then(sendResponse);
    return true;
  });

  async function extractCurrentEmail() {
    const extraction = findCurrentEmail();
    if (!extraction.result.ok) {
      return extraction.result;
    }
    return collectCurrentMessageContext(extraction);
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
        safeResourceLimitation("Current-message resources could not be collected without a verified collector and message root."),
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
        safeResourceLimitation("Visible thread segments could not be collected safely."),
      );
    }

    try {
      const resourceContext = findVerifiedResourceContext(
        extraction.document,
        extraction.currentMessageRoot,
      );
      if (!resourceContext) {
        payload.resource_limitations.push(
          safeResourceLimitation(
            "Resources are unavailable because verified current-message resource controls were not established; body analysis continued.",
          ),
        );
        return { ...extraction.result, payload };
      }
      const resources = await collector.collectVisibleResources(extraction.document, {
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
          "filename", "type", "size", "limitation",
        ]),
      );
    } catch (error) {
      payload.resource_limitations.push(
        safeResourceLimitation("Current-message resources could not be collected safely."),
      );
    }
    return { ...extraction.result, payload };
  }

  function findVerifiedResourceContext(doc, currentMessageRoot) {
    const currentMessageContainer = findMarkedAncestor(
      currentMessageRoot,
      CURRENT_MESSAGE_CONTAINER_ATTRIBUTE,
      "true",
    );
    if (!currentMessageContainer || !isVisibleElementInDocument(currentMessageContainer, doc)) {
      return null;
    }

    const controlContainers = querySelectorAll(currentMessageContainer, HOST_RESOURCE_CONTROLS_SELECTOR);
    const controls = controlContainers.find((candidate) =>
      !containsElement(currentMessageRoot, candidate) &&
      isVisibleElementInDocument(candidate, doc),
    );
    if (!controls) {
      return null;
    }

    const collector = window.EmailAssistantCurrentMessageCollector;
    const candidateCap = collector && Number.isInteger(collector.MAX_RESOURCE_CANDIDATES)
      ? collector.MAX_RESOURCE_CANDIDATES
      : 20;
    const verifiedResourceCandidates = querySelectorAll(controls, HOST_RESOURCE_SELECTOR)
      .slice(0, candidateCap + 1)
      .filter(
      (candidate) =>
        !containsElement(currentMessageRoot, candidate) &&
        containsElement(currentMessageContainer, candidate) &&
        isVisibleElementInDocument(candidate, doc),
      );
    return { currentMessageContainer, verifiedResourceCandidates };
  }

  function findMarkedAncestor(element, attributeName, expectedValue) {
    let current = element;
    while (current) {
      if (
        typeof current.getAttribute === "function" &&
        String(current.getAttribute(attributeName) || "") === expectedValue
      ) {
        return current;
      }
      current = current.parentElement || current.parentNode;
    }
    return null;
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

  function safeResourceLimitation(limitation) {
    return { filename: "resource", type: "unsupported", size: 0, limitation };
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
