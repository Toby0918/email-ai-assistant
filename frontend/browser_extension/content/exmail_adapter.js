/* global chrome */
(function () {
  const MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL";
  const EMPTY_PAYLOAD = {
    subject: "",
    from: "",
    to: [],
    sent_at: "",
    body_text: "",
  };
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

    sendResponse(extractCurrentEmail());
    return false;
  });

  function extractCurrentEmail() {
    const documents = collectAccessibleDocuments(window);
    for (const doc of documents) {
      const payload = extractFromDocument(doc);
      if (payload.body_text) {
        return { ok: true, source: "dom", payload };
      }
    }

    const selected = getSelectedEmailContent(documents);
    if (selected) {
      return {
        ok: true,
        source: "selected_text",
        payload: {
          subject: document.title || "Tencent Exmail selected email content",
          from: "",
          to: [],
          sent_at: "",
          body_text: selected,
        },
      };
    }

    return {
      ok: false,
      error: "Open a Tencent Exmail message or select email body text from that opened message first. The fallback is user-selected email content only, not arbitrary webpage analysis.",
    };
  }

  function collectAccessibleDocuments(rootWindow) {
    const documents = [];
    visitWindow(rootWindow, documents);
    return documents;
  }

  function visitWindow(targetWindow, documents) {
    try {
      if (targetWindow.document) {
        documents.push(targetWindow.document);
      }
      for (let index = 0; index < targetWindow.frames.length; index += 1) {
        visitWindow(targetWindow.frames[index], documents);
      }
    } catch (error) {
      return;
    }
  }

  function extractFromDocument(doc) {
    if (!hasMessageContext(doc)) {
      return EMPTY_PAYLOAD;
    }

    const body = findBody(doc);
    if (!body) {
      return EMPTY_PAYLOAD;
    }

    return {
      subject: findSubject(doc) || doc.title || "Tencent Exmail message",
      from: findLabeledText(doc, ["From", "\u53d1\u4ef6\u4eba"]),
      to: splitRecipients(findLabeledText(doc, ["To", "\u6536\u4ef6\u4eba"])),
      sent_at: findLabeledText(doc, ["Date", "Sent", "\u65f6\u95f4", "\u53d1\u9001\u65f6\u95f4"]),
      body_text: body,
    };
  }

  function findSubject(doc) {
    return firstText(doc, SUBJECT_SELECTORS);
  }

  function findBody(doc) {
    const element = findBodyElement(doc);
    const body = normalizeText(element ? element.innerText || element.textContent : "");
    if (body.length >= 5) {
      return body;
    }
    return "";
  }

  function findBodyElement(doc) {
    for (const selector of BODY_SELECTORS) {
      const element = doc.querySelector(selector);
      const text = normalizeText(element ? element.innerText || element.textContent : "");
      if (text.length >= 5) {
        return element;
      }
    }
    return null;
  }

  function hasMessageContext(doc) {
    const markerText = normalizeText(doc.body ? doc.body.innerText : "");
    if (!markerText) {
      return false;
    }

    return Boolean((hasSubjectContext(doc) || hasHeaderContext(doc)) && findBodyElement(doc));
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
      if (text) {
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

  function getSelectedEmailContent(documents) {
    for (const doc of documents) {
      if (!hasMessageContext(doc)) {
        continue;
      }

      const view = doc.defaultView;
      if (!view || !view.getSelection) {
        continue;
      }

      const selection = view.getSelection();
      const text = normalizeText(selection.toString());
      if (text && selectionBelongsToMessage(doc, selection)) {
        return text;
      }
    }
    return "";
  }

  function selectionBelongsToMessage(doc, selection) {
    const bodyElement = findBodyElement(doc);
    if (!bodyElement) {
      return false;
    }
    if (!selection.rangeCount) {
      return false;
    }

    const node = selection.getRangeAt(0).commonAncestorContainer;
    const element = node.nodeType === 1 ? node : node.parentElement || node.parentNode;
    return Boolean(element && (element === bodyElement || bodyElement.contains(element)));
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }
})();
