(function (root) {
  const CLASSIFICATIONS = Object.freeze({
    visibleAttachment: "visible_attachment",
    inlineBusinessImage: "inline_business_image",
    rejected: "rejected",
  });
  const SUPPORTED_ATTACHMENT_TYPES = Object.freeze(["image", "pdf", "xlsx", "docx"]);
  const BLOCKED_VISUAL_HINT = /(?:^|[^a-z0-9])(?:avatar|badge|brandmark|button|contact|footer|headshot|icon|logo|portrait|profile|qrcode|qr-code|signature|social|sprite|tracker|tracking|wordmark)(?:[^a-z0-9]|$)/i;
  const MIN_INLINE_WIDTH = 320;
  const MIN_INLINE_HEIGHT = 180;
  const MIN_INLINE_AREA = 100000;
  const MAX_INLINE_ASPECT_RATIO = 4;

  function classifyVisibleResource(value) {
    const facts = value && typeof value === "object" && !Array.isArray(value) ? value : {};
    if (!passesCommonBoundary(facts)) {
      return CLASSIFICATIONS.rejected;
    }
    if (facts.candidateKind === "attachment") {
      if (
        facts.verifiedAttachmentControl !== true ||
        facts.signatureContext === true ||
        contactSignalCount(facts) >= 2 ||
        BLOCKED_VISUAL_HINT.test(String(facts.visualHint || ""))
      ) {
        return CLASSIFICATIONS.rejected;
      }
      return SUPPORTED_ATTACHMENT_TYPES.includes(facts.resourceType) ||
        (facts.resourceType === "" && facts.deferredTypeValidation === true)
        ? CLASSIFICATIONS.visibleAttachment
        : CLASSIFICATIONS.rejected;
    }
    if (facts.candidateKind !== "inline_image" || facts.resourceType !== "image") {
      return CLASSIFICATIONS.rejected;
    }
    if (facts.signatureContext === true || contactSignalCount(facts) >= 2) {
      return CLASSIFICATIONS.rejected;
    }
    if (BLOCKED_VISUAL_HINT.test(String(facts.visualHint || ""))) {
      return CLASSIFICATIONS.rejected;
    }
    const width = safeDimension(facts.width);
    const height = safeDimension(facts.height);
    if (
      width < MIN_INLINE_WIDTH ||
      height < MIN_INLINE_HEIGHT ||
      width * height < MIN_INLINE_AREA ||
      Math.max(width / height, height / width) > MAX_INLINE_ASPECT_RATIO
    ) {
      return CLASSIFICATIONS.rejected;
    }
    return CLASSIFICATIONS.inlineBusinessImage;
  }

  function passesCommonBoundary(facts) {
    return facts.visible === true &&
      facts.currentMessageOwned === true &&
      facts.approvedUrl === true &&
      facts.ambiguousOwnership === false &&
      facts.quotedHistory === false &&
      facts.afterSignatureBoundary === false &&
      facts.repeated === false;
  }

  function contactSignalCount(facts) {
    const value = Number(facts.contactSignalCount);
    return Number.isSafeInteger(value) && value >= 0 ? value : 0;
  }

  function safeDimension(value) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : 0;
  }

  root.EmailAssistantExmailVisibleResourceClassifier = Object.freeze({
    CLASSIFICATIONS,
    classifyVisibleResource,
  });
})(window);
