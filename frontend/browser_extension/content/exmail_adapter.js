/* global chrome */
(function () {
  const MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL";
  const REVALIDATE_MESSAGE_TYPE = "REVALIDATE_CURRENT_EMAIL";
  const MIN_BODY_LENGTH = 5;
  const EMPTY_PAYLOAD = {
    subject: "",
    from: "",
    to: [],
    cc: [],
    sent_at: "",
    body_text: "",
    attachments: [],
  };
  const MAX_ATTACHMENTS = 8;
  const MAX_RESOURCE_PHASE_MS = 20000;
  const MAX_RESOURCE_DISCOVERY_NODES = 200;
  const MAX_RESOURCE_DISCOVERY_DEPTH = 20;
  const EXMAIL_ORIGIN = "https://exmail.qq.com";
  const APPROVED_RESOURCE_PATHS = ["/cgi-bin/download", "/cgi-bin/viewfile"];
  const ATTACHMENT_PATTERN =
    /([A-Za-z0-9][A-Za-z0-9 _.,()[\]\-+&'#]*\.(pdf|docx?|xlsx?|pptx?|csv|zip|rar|7z|png|jpe?g|gif|txt))(?:\s*\(([^)\n]{1,40})\))?/gi;
  const BODY_SELECTORS = [
    "#mailContentContainer",
    "#mailContent",
    "#qm_con_body",
    ".qm_con_body",
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
    if (!revalidateExtractionContext(extraction)) {
      return safeExtractionFailure();
    }
    if (!hasUsableCurrentBody(result)) {
      return safeExtractionFailure();
    }
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
    if (!revalidateExtractionContext(extraction)) {
      return safeRevalidationFailure();
    }
    if (!hasUsableCurrentBody(result)) {
      return safeRevalidationFailure();
    }
    return {
      ok: true,
      message_fingerprint: messageFingerprint(result.payload),
    };
  }

  function findCurrentEmail() {
    const visibleContextApi = window.EmailAssistantExmailVisibleContext;
    const verifiedContext = visibleContextApi &&
      typeof visibleContextApi.resolveVerifiedDocumentContext === "function"
      ? visibleContextApi.resolveVerifiedDocumentContext(window)
      : null;
    if (!verifiedContext) {
      return extractionContext({
        ok: false,
        error: "Open a Tencent Exmail message or select email body text from that opened message first. The fallback is user-selected email content only, not arbitrary webpage analysis.",
      });
    }
    const selectedDocument = verifiedContext.document;
    const selected = getSelectedEmailContent([selectedDocument]);
    if (selected) {
      const metadata = extractFromDocument(
        selected.document,
        true,
        verifiedContext.currentBodyRoot || verifiedContext.currentMessageRoot,
        verifiedContext,
      );
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
      }, verifiedContext);
    }

    const payload = extractFromDocument(
      selectedDocument,
      true,
      verifiedContext.currentBodyRoot || verifiedContext.currentMessageRoot,
      verifiedContext,
    );
    if (payload.body_text) {
      return extractionContext(
        { ok: true, source: "dom", payload },
        verifiedContext,
      );
    }

    return extractionContext({
      ok: false,
      error: "Open a Tencent Exmail message or select email body text from that opened message first. The fallback is user-selected email content only, not arbitrary webpage analysis.",
    });
  }

  function extractionContext(result, verifiedContext) {
    return {
      result,
      document: verifiedContext ? verifiedContext.document : null,
      currentMessageRoot: verifiedContext ? verifiedContext.currentMessageRoot : null,
      currentBodyRoot: verifiedContext ? verifiedContext.currentBodyRoot : null,
      threadRoot: verifiedContext ? verifiedContext.threadRoot : null,
      siblingHistoryRoots: verifiedContext ? verifiedContext.siblingHistoryRoots : [],
      threadContextLimited: Boolean(
        verifiedContext && verifiedContext.threadContextLimited === true,
      ),
      verifiedContext: verifiedContext || null,
    };
  }

  async function collectCurrentMessageContext(extraction) {
    const payload = {
      ...extraction.result.payload,
      thread_segments: [],
      thread_context_limited: extraction.threadContextLimited === true,
      attachment_files: [],
      resource_limitations: [],
    };
    const collector = window.EmailAssistantCurrentMessageCollector;
    if (!collector || !extraction.currentMessageRoot) {
      payload.thread_context_limited = true;
      payload.resource_limitations.push(
        safeResourceLimitation(
          "resource_unavailable",
          "Current-message resources could not be collected without a verified collector and message root.",
        ),
      );
      return { ...extraction.result, payload };
    }

    try {
      const collectionOptions = {
        currentMessageRoot: extraction.currentMessageRoot,
        currentBodyRoot: extraction.currentBodyRoot,
        currentBodyText: extraction.verifiedContext && extraction.verifiedContext.currentBodyText,
        threadRoot: extraction.threadRoot,
        verifiedSiblingHistoryRoots: extraction.siblingHistoryRoots,
        threadContextLimited: extraction.threadContextLimited,
        verifiedDocumentContext: true,
      };
      const messageContext = typeof collector.extractVisibleMessageContext === "function"
        ? collector.extractVisibleMessageContext(extraction.document, collectionOptions)
        : {
            current_message: null,
            thread_context_limited: extraction.threadContextLimited === true,
            thread_segments: collector.extractVisibleThreadSegments(
              extraction.document,
              collectionOptions,
            ),
          };
      payload.thread_segments = projectItems(
        messageContext && messageContext.thread_segments,
        ["position", "from", "to", "sent_at", "timestamp_text", "subject", "body_text"],
      );
      payload.thread_context_limited = Boolean(
        extraction.threadContextLimited === true ||
        messageContext && messageContext.thread_context_limited === true,
      );
      applyCurrentMessageContext(payload, messageContext && messageContext.current_message, {
        preserveSelectedBody: extraction.result.source === "selected_text",
        preserveVerifiedMetadata: Boolean(extraction.verifiedContext),
        cleanSelectedBody: collector.cleanVisibleMessageBody,
      });
    } catch (error) {
      payload.thread_segments = [];
      payload.thread_context_limited = true;
      payload.body_text = safeCurrentBodyAfterCollectorFailure(extraction);
      payload.resource_limitations.push(
        safeResourceLimitation("resource_unavailable", "Visible thread segments could not be collected safely."),
      );
    }

    if (!revalidateExtractionContext(extraction)) {
      payload.thread_context_limited = true;
      payload.resource_limitations.push(
        safeResourceLimitation(
          "resource_unavailable",
          "Resources are unavailable because the verified current-message context changed; body analysis continued.",
        ),
      );
      return { ...extraction.result, payload };
    }

    const resourceDeadline = Date.now() + MAX_RESOURCE_PHASE_MS;
    try {
      const resourceContext = findVerifiedResourceContext(
        extraction.verifiedContext,
        resourceDeadline,
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
        verifiedDocument: extraction.document,
        verifiedDocumentContext: true,
        revalidateContext: () => revalidateExtractionContext(extraction),
        currentMessageRoot: extraction.currentMessageRoot,
        currentBodyRoot: extraction.currentBodyRoot,
        currentMessageContainer: resourceContext.currentMessageContainer,
        verifiedResourceCandidates: resourceContext.verifiedResourceCandidates,
        resourceControlsVerified: true,
        overallDeadline: resourceDeadline,
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

  function revalidateExtractionContext(extraction) {
    const visibleContextApi = window.EmailAssistantExmailVisibleContext;
    return Boolean(
      extraction &&
      extraction.verifiedContext &&
      visibleContextApi &&
      typeof visibleContextApi.revalidateVerifiedDocumentContext === "function" &&
      visibleContextApi.revalidateVerifiedDocumentContext(
        window,
        extraction.verifiedContext,
      )
    );
  }

  function safeCurrentBodyAfterCollectorFailure(extraction) {
    const explicitBodies = uniqueElements(
      querySelectorAll(
        extraction.currentMessageRoot,
        "[data-email-current-body], .mail-current-body, .current-message-body",
      ),
    ).filter((candidate) => isVisibleElementInDocument(candidate, extraction.document));
    if (explicitBodies.length === 1) {
      return normalizeBodyLines(explicitBodies[0].innerText || explicitBodies[0].textContent || "");
    }
    return "";
  }

  function normalizeBodyLines(value) {
    return String(value || "")
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map((line) => line.replace(/[\t\f\v ]+/g, " ").trim())
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function applyCurrentMessageContext(payload, currentMessage, options) {
    if (!currentMessage || typeof currentMessage !== "object" || Array.isArray(currentMessage)) {
      return;
    }
    const settings = options || {};
    if (settings.preserveSelectedBody) {
      if (typeof settings.cleanSelectedBody === "function") {
        payload.body_text = String(settings.cleanSelectedBody(payload.body_text) || "");
      }
    } else if (Object.prototype.hasOwnProperty.call(currentMessage, "body_text")) {
      payload.body_text = String(currentMessage.body_text || "");
    }
    if (settings.preserveVerifiedMetadata) {
      return;
    }

    const subject = normalizeText(currentMessage.subject);
    const sender = normalizeText(currentMessage.from);
    const sentAt = normalizeText(currentMessage.sent_at);
    const recipients = splitRecipients(normalizeText(currentMessage.to));
    if (subject) payload.subject = subject;
    if (sender) payload.from = sender;
    if (sentAt) payload.sent_at = sentAt;
    if (recipients.length) payload.to = recipients;
  }

  function findVerifiedResourceContext(verifiedContext, resourceDeadline) {
    const doc = verifiedContext && verifiedContext.document;
    const currentMessageRoot = verifiedContext && verifiedContext.currentMessageRoot;
    const currentBodyRoot = verifiedContext && verifiedContext.currentBodyRoot;
    const currentMessageContainer = verifiedResourceContainer(currentMessageRoot, doc);
    if (
      !verifiedContext ||
      !verifiedContext.contextToken ||
      !doc ||
      !doc.body ||
      !currentMessageContainer ||
      (currentMessageContainer.parentElement || currentMessageContainer.parentNode) !== (doc && doc.body) ||
      verifiedResourceContainer(currentMessageRoot, doc) !== currentMessageContainer ||
      !currentBodyRoot ||
      !containsElement(currentMessageRoot, currentBodyRoot) ||
      !hasUniqueVisibleKnownBodyRoot(doc, currentMessageRoot) ||
      Date.now() >= resourceDeadline
    ) {
      return null;
    }

    const collector = window.EmailAssistantCurrentMessageCollector;
    const candidateCap = collector && Number.isInteger(collector.MAX_RESOURCE_CANDIDATES)
      ? collector.MAX_RESOURCE_CANDIDATES
      : 20;
    const baseHref = documentHref(doc);
    const discovery = {
      candidates: [],
      deadline: resourceDeadline,
      maxCandidates: candidateCap + 1,
      nodesVisited: 0,
      visited: new Set(),
    };
    boundedResourceCandidates(
      currentMessageContainer.children || [],
      "A",
      baseHref,
      doc,
      discovery,
      currentMessageRoot,
    );
    boundedResourceCandidates(
      [currentBodyRoot],
      "IMG",
      baseHref,
      doc,
      discovery,
    );
    const verifiedResourceCandidates = discovery.candidates;
    if (verifiedResourceCandidates.length === 0) {
      return null;
    }
    return { currentMessageContainer, verifiedResourceCandidates };
  }

  function verifiedResourceContainer(currentMessageRoot, doc) {
    if (!currentMessageRoot || !doc || !doc.body) {
      return null;
    }
    const parent = currentMessageRoot.parentElement || currentMessageRoot.parentNode;
    if (parent && (parent.parentElement || parent.parentNode) === doc.body) {
      return parent;
    }
    if (!isExactTencentQmboxRoot(currentMessageRoot) || !parent) {
      return null;
    }
    const container = parent.parentElement || parent.parentNode;
    return container && (container.parentElement || container.parentNode) === doc.body
      ? container
      : null;
  }

  function isExactTencentQmboxRoot(element) {
    if (!element || typeof element.getAttribute !== "function") {
      return false;
    }
    const id = String(element.getAttribute("id") || element.id || "");
    const classes = String(element.getAttribute("class") || element.className || "")
      .split(/\s+/)
      .filter(Boolean);
    return id === "mailContentContainer" && classes.includes("qmbox");
  }

  function hasUniqueVisibleKnownBodyRoot(doc, currentMessageRoot) {
    const roots = uniqueElements(querySelectorAll(doc && doc.body, BODY_SELECTORS.join(", ")))
      .filter((candidate) => isVisibleElementInDocument(candidate, doc));
    return roots.length === 1 && roots[0] === currentMessageRoot;
  }

  function boundedResourceCandidates(roots, requiredTag, baseHref, doc, state, excludedSubtree) {
    const stack = [];
    pushDiscoveryElements(stack, roots, 0, state);
    while (
      stack.length > 0 &&
      state.candidates.length < state.maxCandidates &&
      state.nodesVisited < MAX_RESOURCE_DISCOVERY_NODES &&
      Date.now() < state.deadline
    ) {
      const item = stack.pop();
      const element = item && item.element;
      if (!element || state.visited.has(element)) {
        continue;
      }
      state.nodesVisited += 1;
      if (element === excludedSubtree) {
        continue;
      }
      state.visited.add(element);
      if (
        String(element.tagName || "").toUpperCase() === requiredTag &&
        isApprovedResourceControl(element, baseHref, doc) &&
        (requiredTag !== "A" || hasPositiveAttachmentControlEvidence(element, baseHref))
      ) {
        state.candidates.push(element);
        if (state.candidates.length >= state.maxCandidates) {
          break;
        }
      }
      if (item.depth < MAX_RESOURCE_DISCOVERY_DEPTH) {
        pushDiscoveryElements(stack, element.children || [], item.depth + 1, state);
      }
    }
  }

  function pushDiscoveryElements(stack, elements, depth, state) {
    const remaining = Math.max(
      0,
      MAX_RESOURCE_DISCOVERY_NODES - state.nodesVisited - stack.length,
    );
    const count = Math.min(collectionLength(elements), remaining);
    for (
      let index = count - 1;
      index >= 0 && Date.now() < state.deadline;
      index -= 1
    ) {
      const element = collectionElement(elements, index);
      if (element) {
        stack.push({ element, depth });
      }
    }
  }

  function collectionLength(value) {
    const length = Number(value && value.length);
    return Number.isSafeInteger(length) && length > 0 ? length : 0;
  }

  function collectionElement(value, index) {
    try {
      return value[index] || null;
    } catch (error) {
      return null;
    }
  }

  function isApprovedResourceControl(element, baseHref, doc) {
    const tagName = String(element && element.tagName || "").toUpperCase();
    if (
      !element ||
      !isVisibleElementInDocument(element, doc) ||
      !hasVisibleResourceLayout(element, doc, tagName === "IMG")
    ) {
      return false;
    }
    const attributeName = tagName === "A" ? "href" : tagName === "IMG" ? "src" : "";
    if (!attributeName || typeof element.getAttribute !== "function") {
      return false;
    }
    return isApprovedResourceUrl(element.getAttribute(attributeName), baseHref);
  }

  function hasPositiveAttachmentControlEvidence(element, baseHref) {
    if (
      !element ||
      String(element.tagName || "").toUpperCase() !== "A" ||
      typeof element.getAttribute !== "function"
    ) {
      return false;
    }
    const hint = ["id", "class", "role", "alt", "title", "name", "data-role"]
      .map((name) => String(element.getAttribute(name) || ""))
      .join(" ");
    if (/(?:^|[^a-z0-9])(?:avatar|contact|footer|headshot|icon|logo|portrait|profile|signature|social|tracker|tracking)(?:[^a-z0-9]|$)/i.test(hint)) {
      return false;
    }
    const typeEvidence = legacyAttachmentTypeEvidence(element);
    if (!typeEvidence.valid) {
      return false;
    }
    return Boolean(normalizeText(element.getAttribute("download"))) ||
      isLegacyTencentDownloadControl(element, baseHref);
  }

  function isLegacyTencentDownloadControl(element, baseHref) {
    try {
      const resolved = new URL(String(element.getAttribute("href") || ""), baseHref);
      const typeEvidence = legacyAttachmentTypeEvidence(element);
      return normalizeText(element.getAttribute("target")).length > 0 &&
        resolved.origin === EXMAIL_ORIGIN &&
        resolved.protocol === "https:" &&
        !resolved.username && !resolved.password &&
        resolved.pathname === "/cgi-bin/download" &&
        resolved.search.length > 1 &&
        !hasLegacyNegativeAttachmentLabel(element) &&
        typeEvidence.valid;
    } catch (error) {
      return false;
    }
  }

  function legacyAttachmentTypeEvidence(element) {
    const visible = legacyVisibleAttachmentDescriptor(element);
    const declared = legacyDeclaredTypeDescriptor(element);
    const filename = legacyDataFilenameDescriptor(element);
    const descriptors = [visible.descriptor, declared.descriptor, filename.descriptor].filter(Boolean);
    const consistent = new Set(descriptors.map((descriptor) => descriptor.canonical)).size <= 1;
    return {
      valid: visible.valid && declared.valid && filename.valid && consistent &&
        !hasNonVisibleAttachmentTypeHint(element),
      deferred: descriptors.length === 0,
    };
  }

  function legacyDataFilenameDescriptor(element) {
    const value = normalizeText(
      element && typeof element.getAttribute === "function"
        ? element.getAttribute("data-filename") || ""
        : "",
    ).toLowerCase();
    if (!value) {
      return { present: false, valid: true, descriptor: null };
    }
    const suffix = value.match(/\.([a-z0-9]+)$/);
    const descriptor = suffix ? normalizeLegacyVisibleAttachmentType(`.${suffix[1]}`) : null;
    return { present: true, valid: Boolean(descriptor), descriptor };
  }

  function hasNonVisibleAttachmentTypeHint(element) {
    const renderedText = normalizeText(element && element.innerText);
    const completeText = normalizeText(element && element.textContent);
    if (!completeText || completeText === renderedText) {
      return false;
    }
    const scan = legacyVisibleAttachmentDescriptors(completeText);
    return !scan.valid || scan.descriptors.length > 0;
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
      if (element && typeof element.getAttribute === "function") {
        labels.push(element.getAttribute(name) || "");
      }
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
      .map((name) => normalizeText(
        element && typeof element.getAttribute === "function" ? element.getAttribute(name) || "" : "",
      ).toLowerCase())
      .filter(Boolean);
    const descriptors = declared.map((value) => normalizeLegacyDeclaredType(value));
    const valid = descriptors.every(Boolean) &&
      new Set(descriptors.filter(Boolean).map((item) => item.canonical)).size <= 1;
    return { valid, descriptor: valid && descriptors.length ? descriptors[0] : null };
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

  function hasVisibleResourceLayout(element, doc, requireViewportIntersection) {
    if (!element || typeof element.getBoundingClientRect !== "function") {
      return false;
    }
    let rect;
    try {
      rect = element.getBoundingClientRect();
    } catch (error) {
      return false;
    }
    const view = doc && doc.defaultView;
    const documentElement = doc && doc.documentElement;
    const body = doc && doc.body;
    const viewportWidth = positiveNumber(view && view.innerWidth) ||
      positiveNumber(documentElement && documentElement.clientWidth) ||
      positiveNumber(body && body.clientWidth);
    const viewportHeight = positiveNumber(view && view.innerHeight) ||
      positiveNumber(documentElement && documentElement.clientHeight) ||
      positiveNumber(body && body.clientHeight);
    const values = rect
      ? [rect.left, rect.top, rect.right, rect.bottom, rect.width, rect.height]
        .map((value) => Number(value))
      : [];
    if (values.length !== 6 || !values.every(Number.isFinite)) {
      return false;
    }
    const [left, top, right, bottom, width, height] = values;
    const rendered = width > 0 && height > 0;
    return rendered && (
      requireViewportIntersection !== true ||
      (Boolean(viewportWidth && viewportHeight) &&
        right > 0 && bottom > 0 && left < viewportWidth && top < viewportHeight)
    );
  }

  function positiveNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : 0;
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

  function hasUsableCurrentBody(result) {
    return Boolean(
      result &&
      result.ok === true &&
      result.payload &&
      typeof result.payload === "object" &&
      normalizeText(result.payload.body_text).length >= MIN_BODY_LENGTH
    );
  }

  function messageFingerprint(payload) {
    const email = payload || {};
    const source = JSON.stringify([
      fingerprintValues([email.subject, email.from, email.to, email.cc, email.sent_at, email.body_text]),
      fingerprintValues([email.thread_context_limited === true]),
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

  function extractFromDocument(
    doc,
    allowDocumentBodyFallback,
    suppliedBodyElement,
    verifiedContext,
  ) {
    if (!hasMessageContext(doc, allowDocumentBodyFallback, suppliedBodyElement)) {
      return EMPTY_PAYLOAD;
    }

    const verifiedBodyText = verifiedContext && verifiedContext.currentBodyRoot
      ? String(verifiedContext.currentBodyText || "")
      : "";
    const body = verifiedBodyText ||
      findBody(doc, allowDocumentBodyFallback, suppliedBodyElement);
    if (!body) {
      return EMPTY_PAYLOAD;
    }
    const bodyElement = findBodyElement(doc, allowDocumentBodyFallback, suppliedBodyElement);
    const subjectText = verifiedContext
      ? normalizeText(
          verifiedContext.subjectRoot &&
          (verifiedContext.subjectRoot.innerText || verifiedContext.subjectRoot.textContent),
        )
      : findSubject(doc);
    const headerRoot = verifiedContext ? verifiedContext.headerRoot : null;

    return {
      subject: subjectText || doc.title || "Tencent Exmail message",
      from: findLabeledTextInElement(headerRoot, ["From", "\u53d1\u4ef6\u4eba"]),
      to: splitRecipients(findLabeledTextInElement(headerRoot, ["To", "\u6536\u4ef6\u4eba"])),
      cc: splitRecipients(findLabeledTextInElement(headerRoot, ["Cc", "\u6284\u9001"])),
      sent_at: findLabeledTextInElement(
        headerRoot,
        ["Date", "Sent", "\u65f6\u95f4", "\u53d1\u9001\u65f6\u95f4"],
      ),
      body_text: body,
      attachments: findAttachments(doc, bodyElement),
    };
  }

  function findSubject(doc) {
    return firstText(doc, SUBJECT_SELECTORS);
  }

  function findBody(doc, allowDocumentBodyFallback, suppliedBodyElement) {
    const element = findBodyElement(doc, allowDocumentBodyFallback, suppliedBodyElement);
    const body = normalizeText(element ? element.innerText || element.textContent : "");
    if (body.length >= MIN_BODY_LENGTH) {
      return body;
    }
    return "";
  }

  function findBodyElement(doc, allowDocumentBodyFallback, suppliedBodyElement) {
    if (
      suppliedBodyElement &&
      isVisibleElementInDocument(suppliedBodyElement, doc) &&
      normalizeText(
        suppliedBodyElement.innerText || suppliedBodyElement.textContent,
      ).length >= MIN_BODY_LENGTH
    ) {
      return suppliedBodyElement;
    }
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

  function hasMessageContext(doc, allowDocumentBodyFallback, suppliedBodyElement) {
    return Boolean(
      isReadMessageDocument(doc) &&
      findBodyElement(doc, allowDocumentBodyFallback, suppliedBodyElement)
    );
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

  function findLabeledTextInElement(element, labels) {
    const lines = String(element ? element.innerText || element.textContent || "" : "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    const accepted = new Set(labels.map(compactHeaderLabel));
    for (let index = 0; index < lines.length; index += 1) {
      const parsed = splitHeaderLine(lines[index]);
      if (!parsed || !accepted.has(parsed.label)) {
        continue;
      }
      if (parsed.value) {
        return parsed.value;
      }
      for (let next = index + 1; next < lines.length; next += 1) {
        const value = normalizeText(lines[next]);
        if (!value) {
          continue;
        }
        const followingHeader = splitHeaderLine(value);
        return followingHeader && isKnownHeaderLabel(followingHeader.label)
          ? ""
          : value;
      }
      return "";
    }
    return "";
  }

  function splitHeaderLine(value) {
    const normalized = normalizeText(value);
    const separators = [normalized.indexOf(":"), normalized.indexOf("\uff1a")]
      .filter((index) => index >= 0);
    if (!separators.length) {
      return null;
    }
    const separator = Math.min(...separators);
    const label = compactHeaderLabel(normalized.slice(0, separator));
    if (!label) {
      return null;
    }
    return {
      label,
      value: normalizeText(normalized.slice(separator + 1)),
    };
  }

  function compactHeaderLabel(value) {
    return normalizeText(value).replace(/\s+/g, "").toLocaleLowerCase();
  }

  function isKnownHeaderLabel(value) {
    return [
      "from", "\u53d1\u4ef6\u4eba", "to", "\u6536\u4ef6\u4eba",
      "cc", "\u6284\u9001", "date", "sent", "\u65f6\u95f4",
      "\u53d1\u9001\u65f6\u95f4", "subject", "\u4e3b\u9898",
      "attachments", "\u9644\u4ef6",
    ].includes(value);
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
    if (
      style.display === "none" ||
      hiddenVisibility(style.visibility) ||
      String(style.opacity) === "0"
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

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }
})();
