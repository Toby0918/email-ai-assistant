(function (root) {
  "use strict";

  const EXMAIL_ORIGIN = "https://exmail.qq.com";
  const MAIN_FRAME_NAME = "mainFrame";
  const MIN_BODY_LENGTH = 5;
  const SUBJECT_SELECTOR_GROUPS = [
    ["#subject"],
    [".mail_subject", ".mail-subject"],
  ];
  const HEADER_SELECTORS = [
    "#mailHeader",
    ".read-header",
    ".readmailinfo",
    ".mail-header",
    ".mail-detail-header",
    ".qm_header",
  ];
  const BODY_SELECTORS = [
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
  const EXPLICIT_CURRENT_BODY_SELECTORS = [
    "[data-email-current-body]",
    ".mail-current-body",
    ".current-message-body",
  ];
  const THREAD_SEGMENT_SELECTORS = [
    "[data-email-thread-segment]",
    ".mail-thread-segment",
    ".mail-thread-item",
    ".mail-reply-item",
    ".mail-conversation-item",
    ".readmail_item",
  ];
  const OWNED_TEXT_BLOCK_TAGS = new Set([
    "ADDRESS", "ARTICLE", "BLOCKQUOTE", "DIV", "DL", "FIELDSET", "FIGCAPTION",
    "FIGURE", "FOOTER", "FORM", "H1", "H2", "H3", "H4", "H5", "H6",
    "HEADER", "HR", "LI", "MAIN", "NAV", "OL", "P", "PRE", "SECTION",
    "TABLE", "TBODY", "TD", "TFOOT", "TH", "THEAD", "TR", "UL",
  ]);

  function resolveVerifiedDocumentContext(rootWindow) {
    if (!rootWindow) {
      return null;
    }
    const topDocument = safeDocument(rootWindow);
    if (!topDocument || documentOrigin(topDocument) !== EXMAIL_ORIGIN) {
      return null;
    }

    const topContext = verifyReadDocument(
      topDocument,
      rootWindow,
      null,
    );
    if (topContext) {
      return topContext;
    }

    const visibleFrames = queryAll(topDocument, "iframe, frame")
      .filter((frame) => frameName(frame) === MAIN_FRAME_NAME)
      .filter((frame) => isVisibleInDocument(frame, topDocument));
    if (visibleFrames.length !== 1) {
      return null;
    }

    const frameElement = visibleFrames[0];
    const frameWindow = safeContentWindow(frameElement);
    const frameDocument = safeDocument(frameWindow);
    if (
      !frameWindow ||
      !frameDocument ||
      documentOrigin(frameDocument) !== EXMAIL_ORIGIN
    ) {
      return null;
    }
    return verifyReadDocument(frameDocument, frameWindow, frameElement);
  }

  function revalidateVerifiedDocumentContext(rootWindow, context) {
    if (!context || !context.contextToken) {
      return false;
    }
    const current = resolveVerifiedDocumentContext(rootWindow);
    if (!current || !current.contextToken) {
      return false;
    }
    const expected = context.contextToken;
    const actual = current.contextToken;
    return (
      current.document === context.document &&
      current.frameWindow === context.frameWindow &&
      current.frameElement === context.frameElement &&
      current.subjectRoot === context.subjectRoot &&
      current.headerRoot === context.headerRoot &&
      current.currentMessageRoot === context.currentMessageRoot &&
      current.currentBodyRoot === context.currentBodyRoot &&
      current.threadRoot === context.threadRoot &&
      actual.documentIdentity === expected.documentIdentity &&
      actual.frameIdentity === expected.frameIdentity &&
      actual.subjectIdentity === expected.subjectIdentity &&
      actual.headerIdentity === expected.headerIdentity &&
      actual.currentBodyIdentity === expected.currentBodyIdentity &&
      actual.locationHref === expected.locationHref &&
      actual.subjectText === expected.subjectText &&
      actual.headerText === expected.headerText &&
      actual.currentBodyText === expected.currentBodyText
    );
  }

  function verifyReadDocument(doc, frameWindow, frameElement) {
    if (
      !doc ||
      !doc.body ||
      !isVisibleInDocument(doc.body, doc)
    ) {
      return null;
    }
    const subject = uniqueSubjectEvidence(doc);
    if (!subject) {
      return null;
    }
    const explicitHeader = uniqueHeaderEvidence(doc, null);
    let bodyCandidates = uniqueElements(queryAll(doc, BODY_SELECTORS.join(", ")))
      .filter((element) => (
        isVisibleInDocument(element, doc) &&
        normalizedText(element).length >= MIN_BODY_LENGTH &&
        !containsElement(element, subject) &&
        !(explicitHeader && containsElement(element, explicitHeader))
      ));
    bodyCandidates = bodyCandidates.filter((candidate) => (
      !bodyCandidates.some((other) => (
        other !== candidate && containsElement(other, candidate)
      ))
    ));
    if (bodyCandidates.length === 0 && explicitHeader) {
      const inferred = inferUnmarkedBody(subject, explicitHeader, doc);
      if (inferred) {
        bodyCandidates = [inferred];
      }
    }
    if (bodyCandidates.length !== 1) {
      return null;
    }
    const currentMessageRoot = bodyCandidates[0];
    if (containsElement(currentMessageRoot, subject)) {
      return null;
    }
    const header = uniqueHeaderEvidence(doc, currentMessageRoot);
    if (!header) {
      return null;
    }
    const commonRoot = minimumCommonAncestor(
      [subject, header, currentMessageRoot],
      doc,
    );
    if (!commonRoot) {
      return null;
    }
    const threadRoot = commonRoot === doc.body ? currentMessageRoot : commonRoot;
    const explicitBodies = uniqueElements(
      queryAll(currentMessageRoot, EXPLICIT_CURRENT_BODY_SELECTORS.join(", ")),
    ).filter((element) => (
      isVisibleInDocument(element, doc) &&
      normalizedText(element).length >= MIN_BODY_LENGTH
    ));
    if (explicitBodies.length > 1) {
      return null;
    }
    const nestedThreadSegments = queryAll(currentMessageRoot, THREAD_SEGMENT_SELECTORS.join(", "))
      .filter((element) => isVisibleInDocument(element, doc));
    const currentBodyRoot = explicitBodies[0] || (
      isPureThreadAggregate(currentMessageRoot, nestedThreadSegments)
        ? null
        : currentMessageRoot
    );
    const currentBodyText = currentBodyRoot
      ? ownedCurrentBodyText(currentBodyRoot, doc)
      : null;
    if (currentBodyRoot && (!currentBodyText || currentBodyText.length < MIN_BODY_LENGTH)) {
      return null;
    }
    const contextToken = Object.freeze({
      documentIdentity: doc,
      frameIdentity: frameElement || frameWindow,
      subjectIdentity: subject,
      headerIdentity: header,
      currentBodyIdentity: currentBodyRoot || currentMessageRoot,
      locationHref: documentHref(doc),
      subjectText: normalizedText(subject),
      headerText: normalizedText(header),
      currentBodyText: currentBodyRoot
        ? normalizeEvidenceText(currentBodyText)
        : normalizedText(currentMessageRoot),
    });
    return Object.freeze({
      document: doc,
      frameWindow,
      frameElement: frameElement || null,
      subjectRoot: subject,
      headerRoot: header,
      currentMessageRoot,
      currentBodyRoot,
      currentBodyText,
      threadRoot,
      contextToken,
    });
  }

  function uniqueSubjectEvidence(doc) {
    for (const selectors of SUBJECT_SELECTOR_GROUPS) {
      const candidates = uniqueElements(queryAll(doc, selectors.join(", ")))
        .filter((element) => (
          isVisibleInDocument(element, doc) &&
          normalizedText(element)
        ));
      if (candidates.length > 0) {
        return candidates.length === 1 ? candidates[0] : null;
      }
    }
    return null;
  }

  function uniqueHeaderEvidence(doc, currentMessageRoot) {
    const explicit = uniqueElements(queryAll(doc, HEADER_SELECTORS.join(", ")))
      .filter((element) => (
        !containsElement(currentMessageRoot, element) &&
        !containsElement(element, currentMessageRoot) &&
        isVisibleInDocument(element, doc) &&
        hasHeaderLabels(element)
      ));
    if (explicit.length === 1) {
      return explicit[0];
    }
    if (explicit.length > 1) {
      return null;
    }
    return null;
  }

  function inferUnmarkedBody(subject, header, doc) {
    const container = minimumCommonAncestor([subject, header], doc);
    if (!container) {
      return null;
    }
    const candidates = Array.from(container.children || []).filter((element) => {
      const tagName = String(element && element.tagName || "").toUpperCase();
      return (
        element !== subject &&
        element !== header &&
        !["IFRAME", "FRAME", "SCRIPT", "STYLE"].includes(tagName) &&
        !hasHeaderLabels(element) &&
        isVisibleInDocument(element, doc) &&
        normalizedText(element).length >= MIN_BODY_LENGTH
      );
    });
    return candidates.length === 1 ? candidates[0] : null;
  }

  function isPureThreadAggregate(currentRoot, candidates) {
    if (!candidates.length) {
      return false;
    }
    const minimal = candidates.filter((candidate) => (
      !candidates.some((other) => (
        other !== candidate && containsElement(candidate, other)
      ))
    ));
    return normalizedText(currentRoot) ===
      minimal.map((candidate) => normalizedText(candidate)).filter(Boolean).join(" ");
  }

  function ownedCurrentBodyText(currentBodyRoot, doc) {
    if (!currentBodyRoot || !currentBodyRoot.childNodes) {
      return normalizeOwnedBodyText(
        currentBodyRoot && (currentBodyRoot.innerText || currentBodyRoot.textContent),
      );
    }
    const parts = [];
    const signatureBoundary = linkedSignatureBoundary(currentBodyRoot, doc);
    appendOwnedText(currentBodyRoot, currentBodyRoot, doc, parts, signatureBoundary);
    return normalizeOwnedBodyText(parts.join(""));
  }

  function appendOwnedText(node, currentBodyRoot, doc, parts, signatureBoundary) {
    if (!node) {
      return;
    }
    if (node.nodeType === 3) {
      parts.push(String(node.nodeValue || node.textContent || ""));
      return;
    }
    if (node.nodeType !== 1) {
      return;
    }
    if (
      node !== currentBodyRoot &&
      (
        matchesAny(node, BODY_SELECTORS) ||
        matchesAny(node, THREAD_SEGMENT_SELECTORS)
      )
    ) {
      return;
    }
    const tagName = String(node.tagName || "").toUpperCase();
    if (
      node !== currentBodyRoot &&
      tagName === "BLOCKQUOTE" &&
      hasCompleteLegacyHeaderCluster(node)
    ) {
      return;
    }
    if (tagName === "BR") {
      if (hasVisibleStylePathToBody(node, doc)) {
        parts.push("\n");
      }
      return;
    }
    if (!isVisibleInDocument(node, doc)) {
      return;
    }
    const isBlock = OWNED_TEXT_BLOCK_TAGS.has(tagName);
    if (isBlock) {
      parts.push("\n");
    }
    for (const child of Array.from(node.childNodes || [])) {
      if (node === currentBodyRoot && child === signatureBoundary) {
        break;
      }
      appendOwnedText(child, currentBodyRoot, doc, parts, signatureBoundary);
    }
    if (isBlock) {
      parts.push("\n");
    }
  }

  function linkedSignatureBoundary(currentBodyRoot, doc) {
    const children = Array.from(currentBodyRoot.children || []);
    for (let index = 0; index < children.length; index += 1) {
      const candidate = children[index];
      if (
        String(candidate.tagName || "").toUpperCase() !== "HR" ||
        !isVisibleInDocument(candidate, doc)
      ) {
        continue;
      }
      const quoteIndex = children.findIndex((element, position) => (
        position > index &&
        String(element.tagName || "").toUpperCase() === "BLOCKQUOTE" &&
        hasCompleteLegacyHeaderCluster(element)
      ));
      if (quoteIndex < 0) {
        continue;
      }
      const tail = children.slice(index + 1, quoteIndex).filter((element) => (
        isVisibleInDocument(element, doc) &&
        !["SCRIPT", "STYLE"].includes(String(element.tagName || "").toUpperCase())
      ));
      const priorTextExists = children.slice(0, index).some((element) => (
        normalizedText(element).length >= MIN_BODY_LENGTH
      ));
      const tailCharacters = tail.reduce(
        (total, element) => total + normalizedText(element).length,
        0,
      );
      const hasSignatureResource = tail.some((element) => (
        queryAll(element, "a, img").length > 0
      ));
      if (
        priorTextExists &&
        tail.length > 0 &&
        tail.length <= 4 &&
        tailCharacters <= 800 &&
        hasSignatureResource
      ) {
        return candidate;
      }
    }
    return null;
  }

  function normalizeOwnedBodyText(value) {
    return String(value || "")
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map((line) => line.replace(/[\t\f\v ]+/g, " ").trim())
      .join("\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function normalizeEvidenceText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function minimumCommonAncestor(elements, doc) {
    let current = elements[0];
    while (current) {
      if (
        elements.every((element) => containsElement(current, element)) &&
        isVisibleInDocument(current, doc)
      ) {
        return current;
      }
      current = parentOf(current);
    }
    return null;
  }

  function hasHeaderLabels(element) {
    const text = normalizedText(element);
    return (
      /(?:^|\s)(?:From|\u53d1\s*\u4ef6\s*\u4eba)\s*[:\uff1a]/i.test(text) &&
      /(?:^|\s)(?:To|\u6536\s*\u4ef6\s*\u4eba)\s*[:\uff1a]/i.test(text)
    );
  }

  function hasCompleteLegacyHeaderCluster(element) {
    const lines = String(element && (element.innerText || element.textContent) || "")
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .slice(0, 20)
      .map((line) => line.replace(/\s+/g, " ").trim())
      .filter(Boolean)
      .join("\n");
    return (
      /^(?:From|\u53d1\u4ef6\u4eba)\s*[:\uff1a]/im.test(lines) &&
      /^(?:Date|Sent|\u65f6\u95f4|\u53d1\u9001\u65f6\u95f4)\s*[:\uff1a]/im.test(lines) &&
      /^(?:To|\u6536\u4ef6\u4eba)\s*[:\uff1a]/im.test(lines) &&
      /^(?:Subject|\u4e3b\u9898)\s*[:\uff1a]/im.test(lines)
    );
  }

  function safeContentWindow(frameElement) {
    try {
      return frameElement ? frameElement.contentWindow || null : null;
    } catch (error) {
      return null;
    }
  }

  function safeDocument(targetWindow) {
    try {
      return targetWindow && targetWindow.document || null;
    } catch (error) {
      return null;
    }
  }

  function documentOrigin(doc) {
    try {
      return new URL(documentHref(doc)).origin;
    } catch (error) {
      return "";
    }
  }

  function documentHref(doc) {
    if (doc && doc.location && typeof doc.location.href === "string") {
      return doc.location.href;
    }
    return doc && typeof doc.baseURI === "string" ? doc.baseURI : "";
  }

  function frameName(frame) {
    return String(
      attribute(frame, "name") ||
      frame && frame.name ||
      attribute(frame, "id"),
    );
  }

  function queryAll(container, selector) {
    if (!container || typeof container.querySelectorAll !== "function") {
      return [];
    }
    try {
      return Array.from(container.querySelectorAll(selector) || []);
    } catch (error) {
      return [];
    }
  }

  function descendants(element) {
    if (!element) {
      return [];
    }
    const values = [];
    for (const child of Array.from(element.children || [])) {
      values.push(child, ...descendants(child));
    }
    return values;
  }

  function matchesAny(element, selectors) {
    return selectors.some((selector) => {
      if (typeof element.matches === "function") {
        try {
          return element.matches(selector);
        } catch (error) {
          return false;
        }
      }
      const id = attribute(element, "id");
      const classes = attribute(element, "class").split(/\s+/).filter(Boolean);
      if (selector.startsWith("#")) return id === selector.slice(1);
      if (selector.startsWith(".")) return classes.includes(selector.slice(1));
      if (selector.startsWith("[")) {
        const name = selector.slice(1, selector.indexOf("]")).split("=")[0];
        return Boolean(attribute(element, name));
      }
      return false;
    });
  }

  function isVisibleInDocument(element, doc) {
    return hasVisibleStylePathToBody(element, doc) &&
      hasRenderedViewportIntersection(element, doc);
  }

  function hasVisibleStylePathToBody(element, doc) {
    if (!element) {
      return false;
    }
    let current = element;
    let reachedBody = false;
    while (current) {
      if (
        current.hidden ||
        hasAttribute(current, "hidden") ||
        attribute(current, "aria-hidden").toLowerCase() === "true" ||
        styleHides(current, doc)
      ) {
        return false;
      }
      if (current === doc.body) {
        reachedBody = true;
      }
      current = parentOf(current);
    }
    return reachedBody;
  }

  function styleHides(element, doc) {
    const inline = element.style || {};
    if (
      inline.display === "none" ||
      hiddenVisibility(inline.visibility) ||
      zeroOpacity(inline.opacity)
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
        zeroOpacity(computed.opacity);
    } catch (error) {
      return false;
    }
  }

  function hiddenVisibility(value) {
    return value === "hidden" || value === "collapse";
  }

  function zeroOpacity(value) {
    if (value === undefined || value === null || value === "") {
      return false;
    }
    const opacity = Number(value);
    return Number.isFinite(opacity) && opacity <= 0;
  }

  function hasRenderedViewportIntersection(element, doc) {
    if (!element || typeof element.getBoundingClientRect !== "function") {
      return false;
    }
    try {
      const rect = element.getBoundingClientRect();
      const left = Number(rect.left);
      const top = Number(rect.top);
      const right = Number(rect.right);
      const bottom = Number(rect.bottom);
      const width = Number.isFinite(Number(rect.width))
        ? Number(rect.width)
        : right - left;
      const height = Number.isFinite(Number(rect.height))
        ? Number(rect.height)
        : bottom - top;
      const view = doc && doc.defaultView;
      const viewportWidth = Number(
        view && view.innerWidth ||
        doc && doc.documentElement && doc.documentElement.clientWidth,
      );
      const viewportHeight = Number(
        view && view.innerHeight ||
        doc && doc.documentElement && doc.documentElement.clientHeight,
      );
      return (
        [left, top, right, bottom, width, height, viewportWidth, viewportHeight]
          .every(Number.isFinite) &&
        width > 0 &&
        height > 0 &&
        viewportWidth > 0 &&
        viewportHeight > 0 &&
        right > 0 &&
        bottom > 0 &&
        left < viewportWidth &&
        top < viewportHeight
      );
    } catch (error) {
      return false;
    }
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
      current = parentOf(current);
    }
    return false;
  }

  function parentOf(element) {
    return element && (element.parentElement || element.parentNode) || null;
  }

  function normalizedText(element) {
    return String(element ? element.innerText || element.textContent || "" : "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function attribute(element, name) {
    if (!element || typeof element.getAttribute !== "function") {
      return "";
    }
    return String(element.getAttribute(name) || "");
  }

  function hasAttribute(element, name) {
    return Boolean(
      element &&
      typeof element.hasAttribute === "function" &&
      element.hasAttribute(name)
    );
  }

  function uniqueElements(values) {
    return Array.from(new Set(values));
  }

  root.EmailAssistantExmailVisibleContext = Object.freeze({
    resolveVerifiedDocumentContext,
    revalidateVerifiedDocumentContext,
  });
})(window);
