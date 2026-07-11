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
  const THREAD_SEGMENT_SELECTORS = [
    "[data-email-thread-segment]",
    ".mail-thread-segment",
    ".mail-thread-item",
    ".mail-reply-item",
    ".mail-conversation-item",
    ".readmail_item",
  ];
  const FIELD_SELECTORS = Object.freeze({
    from: ["[data-email-from]", ".mail-sender", ".sender", ".from"],
    to: ["[data-email-to]", ".mail-recipient", ".recipient", ".to"],
    sent_at: ["[data-email-sent-at]", "time"],
    timestamp_text: ["[data-email-timestamp-text]", ".mail-time", ".timestamp"],
    subject: ["[data-email-subject]", ".mail-subject", ".subject"],
    body_text: ["[data-email-segment-body]", ".mail-segment-body", ".mail-body"],
  });

  function extractVisibleThreadSegments(doc, options) {
    const settings = options || {};
    const currentRoot = findCurrentMessageRoot(doc, settings.currentMessageRoot);
    if (!currentRoot) {
      return [];
    }

    const candidates = queryAll(currentRoot, THREAD_SEGMENT_SELECTORS);
    const visibleCandidates = candidates.length ? candidates : [currentRoot];
    const segments = [];
    let remainingChars = MAX_THREAD_SOURCE_CHARS;

    for (const candidate of visibleCandidates) {
      if (segments.length >= MAX_THREAD_SEGMENTS || remainingChars <= 0) {
        break;
      }
      if (!isVisibleWithin(candidate, currentRoot, doc)) {
        continue;
      }
      const segment = normalizeThreadSegment(candidate, doc, currentRoot, segments.length, remainingChars);
      if (!segment) {
        continue;
      }
      remainingChars -= segment.body_text.length;
      segments.push(segment);
    }
    return segments;
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
      !currentContainer ||
      !isInside(currentRoot, currentContainer) ||
      !isVisibleWithin(currentContainer, currentContainer, doc)
    ) {
      result.resource_limitations.push(
        limitedMetadata(
          { filename: "resource", type: "unsupported", size: 0 },
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
        !isInside(element, currentRoot) &&
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
          limitedMetadata(metadata, "Resource type is not supported."),
          omitted,
        );
        continue;
      }

      const resolvedUrl = resolveResourceUrl(resourceUrl(element), baseHref);
      if (!resolvedUrl) {
        addResourceLimitation(result,
          limitedMetadata(metadata, "Resource URL must be a same-origin Tencent Exmail HTTPS URL."),
          omitted);
        continue;
      }
      if (!isApprovedResourceEndpoint(resolvedUrl)) {
        addResourceLimitation(result,
          limitedMetadata(metadata, "Resource URL is not an approved Tencent Exmail attachment endpoint."),
          omitted);
        continue;
      }
      if (metadata.size > limits.maxFileBytes) {
        addResourceLimitation(result,
          limitedMetadata(metadata, `Resource exceeds the ${limits.maxFileBytes}-byte per-file limit.`),
          omitted);
        continue;
      }
      if (transferCount >= limits.maxFiles) {
        addResourceLimitation(result,
          limitedMetadata(metadata, `Resource exceeds the ${limits.maxFiles}-file frontend limit.`),
          omitted);
        continue;
      }

      transferCount += 1;
      if (metadata.size > 0 && totalBytes + metadata.size > limits.maxTotalBytes) {
        addResourceLimitation(result,
          limitedMetadata(metadata, `Resource exceeds the ${limits.maxTotalBytes}-byte total frontend limit.`),
          omitted);
        continue;
      }
      if (typeof fetchImpl !== "function") {
        addResourceLimitation(result,
          limitedMetadata(metadata, "Resource could not be read from the current Tencent Exmail session."),
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
          limitedMetadata(metadata, collected.limitation),
          omitted,
        );
      }
    }
    appendAggregateOmission(result, omitted.count);
    return result;
  }

  function normalizeThreadSegment(element, doc, currentRoot, position, remainingChars) {
    const bodyText = boundedText(
      fieldText(element, "body_text", doc, currentRoot) || elementText(element),
      Math.min(MAX_THREAD_SEGMENT_CHARS, remainingChars),
    );
    const subject = boundedText(fieldText(element, "subject", doc, currentRoot), MAX_METADATA_CHARS);
    if (!bodyText && !subject) {
      return null;
    }
    return {
      position,
      from: boundedText(fieldText(element, "from", doc, currentRoot), MAX_METADATA_CHARS),
      to: boundedText(fieldText(element, "to", doc, currentRoot), MAX_METADATA_CHARS),
      sent_at: boundedText(fieldText(element, "sent_at", doc, currentRoot), MAX_METADATA_CHARS),
      timestamp_text: boundedText(
        fieldText(element, "timestamp_text", doc, currentRoot),
        MAX_METADATA_CHARS,
      ),
      subject,
      body_text: bodyText,
    };
  }

  function fieldText(element, field, doc, currentRoot) {
    const attributeName = `data-${field.replaceAll("_", "-")}`;
    const attributeValue = attribute(element, attributeName);
    if (attributeValue) {
      return normalizeText(attributeValue);
    }
    for (const selector of FIELD_SELECTORS[field] || []) {
      const candidate = typeof element.querySelector === "function" ? element.querySelector(selector) : null;
      if (candidate && isVisibleWithin(candidate, currentRoot, doc)) {
        return elementText(candidate);
      }
    }
    return "";
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
    return hasAttribute(element, "data-email-host-attachment") ||
      hasAttribute(element, "data-email-host-inline-resource");
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
        return { limitation: "Resource could not be read from the current Tencent Exmail session." };
      }
      const announcedSize = responseByteSize(response);
      if (announcedSize !== null) {
        const announcedLimitation = byteLimitation(announcedSize, limits, totalBytes);
        if (announcedLimitation) {
          await cancelResponseBody(response);
          return { limitation: announcedLimitation };
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
        return { limitation: bodyResult.limitation };
      }
      const buffer = bodyResult.buffer;
      const byteSize = buffer && Number.isSafeInteger(buffer.byteLength) ? buffer.byteLength : 0;
      if (byteSize <= 0) {
        return { limitation: "Resource is empty or unreadable." };
      }
      const actualLimitation = byteLimitation(byteSize, limits, totalBytes);
      if (actualLimitation) {
        return { limitation: actualLimitation };
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
        return { limitation: "Resource collection deadline expired; body analysis continued without this resource." };
      }
      return { limitation: "Resource could not be read from the current Tencent Exmail session." };
    }
  }

  async function readBoundedResponse(response, limits, totalBytes, deadline, controller) {
    const body = response.body;
    if (body && typeof body.getReader === "function") {
      return readBoundedStream(body, limits, totalBytes, deadline, controller);
    }
    return { limitation: "Resource response body could not be read with bounded streaming." };
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
          async () => {
            abortController(controller);
            await cancelReader(reader);
          },
        );
        if (!item || item.done) {
          break;
        }
        const chunk = streamChunk(item.value);
        if (!chunk) {
          await cancelReader(reader);
          return { limitation: "Resource could not be read from the current Tencent Exmail session." };
        }
        const nextSize = byteSize + chunk.byteLength;
        const limitation = byteLimitation(nextSize, limits, totalBytes);
        if (limitation) {
          await cancelReader(reader);
          return { limitation };
        }
        if (chunk.byteLength > 0) {
          chunks.push(new Uint8Array(chunk));
          byteSize = nextSize;
        }
      }
      return { buffer: concatenateChunks(chunks, byteSize) };
    } catch (error) {
      await cancelReader(reader);
      if (isDeadlineError(error)) {
        return { limitation: "Resource collection deadline expired; body analysis continued without this resource." };
      }
      return { limitation: "Resource could not be read from the current Tencent Exmail session." };
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

  async function cancelResponseBody(response) {
    const body = response && response.body;
    if (!body) {
      return;
    }
    if (typeof body.cancel === "function") {
      try {
        await body.cancel();
      } catch (error) {
        return;
      }
      return;
    }
    if (typeof body.getReader === "function") {
      const reader = body.getReader();
      await cancelReader(reader);
      releaseReader(reader);
    }
  }

  async function cancelReader(reader) {
    if (!reader || typeof reader.cancel !== "function") {
      return;
    }
    try {
      await reader.cancel();
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
      "One or more additional current-message resource candidates were omitted by bounded collection.",
    ));
  }

  function withDeadline(promise, deadline, onTimeout) {
    const remaining = Math.max(0, deadline - Date.now());
    return new Promise((resolve, reject) => {
      let settled = false;
      const timer = root.setTimeout(async () => {
        if (settled) {
          return;
        }
        settled = true;
        try {
          await onTimeout();
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

  function limitedMetadata(metadata, limitation) {
    return {
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
    extractVisibleThreadSegments,
    collectVisibleResources,
  });
})(window);
