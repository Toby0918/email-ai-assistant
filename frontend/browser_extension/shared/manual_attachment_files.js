(function (root) {
  "use strict";

  const MAX_RESOURCE_COUNT = 5;
  const MAX_RESOURCE_BYTES = 10 * 1024 * 1024;
  const MAX_TOTAL_RESOURCE_BYTES = 25 * 1024 * 1024;
  const MAX_RESOURCE_LIMITATIONS = 8;
  const MAX_BASE64_CHARACTERS = Math.ceil(MAX_RESOURCE_BYTES / 3) * 4;
  const RESOURCE_TYPES = Object.freeze(["image", "pdf", "xlsx", "docx"]);
  const FORBIDDEN_FILENAME_CONTROLS = /[\p{Cc}\p{Cf}\p{Cs}\p{Zl}\p{Zp}]/gu;
  const LIMITATION_TEXT = Object.freeze({
    unsupported_type: "Resource type is not supported.",
    frontend_limit: "Resource exceeded a configured frontend limit.",
    resource_unavailable: "Resource was unavailable from verified current-message controls.",
    resource_read_failed: "Resource could not be read.",
    collection_timeout: "Resource collection timed out.",
    candidate_omission: "Additional current-message resources were omitted by bounded collection.",
  });
  const EXTENSIONS = Object.freeze({
    png: Object.freeze({ type: "image", mime: "image/png" }),
    jpg: Object.freeze({ type: "image", mime: "image/jpeg" }),
    jpeg: Object.freeze({ type: "image", mime: "image/jpeg" }),
    gif: Object.freeze({ type: "image", mime: "image/gif" }),
    webp: Object.freeze({ type: "image", mime: "image/webp" }),
    bmp: Object.freeze({ type: "image", mime: "image/bmp" }),
    tif: Object.freeze({ type: "image", mime: "image/tiff" }),
    tiff: Object.freeze({ type: "image", mime: "image/tiff" }),
    pdf: Object.freeze({ type: "pdf", mime: "application/pdf" }),
    xlsx: Object.freeze({
      type: "xlsx",
      mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
    docx: Object.freeze({
      type: "docx",
      mime: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }),
  });

  async function readSelectedFiles(fileList) {
    const files = boundedSelectedFiles(fileList);
    const attachmentFiles = [];
    const limitations = [];
    let totalBytes = 0;
    try {
      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        if (index >= MAX_RESOURCE_COUNT) {
          pushLimitation(limitations, fixedLimitation("frontend_limit", safeRawMetadata(file)));
          break;
        }
        const rawSize = safeNumberProperty(file, "size");
        if (!Number.isSafeInteger(rawSize) || rawSize < 0) {
          pushLimitation(
            limitations,
            fixedLimitation("resource_read_failed", safeRawMetadata(file)),
          );
          continue;
        }
        const metadata = safeSelectedFileMetadata(file, rawSize);
        if (!metadata) {
          pushLimitation(limitations, fixedLimitation("unsupported_type", safeRawMetadata(file)));
          continue;
        }
        if (
          metadata.size > MAX_RESOURCE_BYTES ||
          totalBytes + metadata.size > MAX_TOTAL_RESOURCE_BYTES
        ) {
          pushLimitation(limitations, fixedLimitation("frontend_limit", metadata));
          continue;
        }

        let bytes = null;
        try {
          const read = file && file.arrayBuffer;
          if (typeof read !== "function") {
            throw new TypeError("Selected resource is unreadable.");
          }
          bytes = new Uint8Array(await read.call(file));
          if (bytes.byteLength <= 0 || bytes.byteLength !== metadata.size) {
            pushLimitation(limitations, fixedLimitation("resource_read_failed", metadata));
            continue;
          }
          const contentBase64 = boundedBase64(bytes);
          attachmentFiles.push({
            filename: metadata.filename,
            type: metadata.type,
            size: metadata.size,
            content_base64: contentBase64,
          });
          totalBytes += bytes.byteLength;
        } catch (error) {
          pushLimitation(limitations, fixedLimitation("resource_read_failed", metadata));
        } finally {
          if (bytes) {
            bytes.fill(0);
          }
        }
      }
      return {
        attachment_files: attachmentFiles,
        resource_limitations: limitations,
      };
    } finally {
      files.length = 0;
    }
  }

  function mergeAttachmentFiles(manualFiles, automaticFiles, limitations) {
    const merged = [];
    const mergedLimitations = projectedLimitations(limitations);
    const seen = new Set();
    let totalBytes = 0;
    for (const source of [boundedItems(manualFiles), boundedItems(automaticFiles)]) {
      try {
        for (const raw of source) {
          const item = projectedAttachmentFile(raw);
          if (!item) {
            continue;
          }
          const deduplicationKey = [item.filename.toLowerCase(), item.type, item.size].join("\u0000");
          if (seen.has(deduplicationKey)) {
            continue;
          }
          seen.add(deduplicationKey);
          if (
            item.size > MAX_RESOURCE_BYTES ||
            merged.length >= MAX_RESOURCE_COUNT ||
            totalBytes + item.size > MAX_TOTAL_RESOURCE_BYTES
          ) {
            pushLimitation(mergedLimitations, fixedLimitation("frontend_limit", item));
            continue;
          }
          merged.push(item);
          totalBytes += item.size;
        }
      } finally {
        source.length = 0;
      }
    }
    return {
      attachment_files: merged,
      resource_limitations: mergedLimitations,
    };
  }

  function boundedSelectedFiles(fileList) {
    if (!fileList || !["object", "function"].includes(typeof fileList)) {
      return [];
    }
    let length;
    try {
      length = fileList.length;
    } catch (error) {
      return [];
    }
    if (!Number.isSafeInteger(length) || length < 0) {
      return [];
    }
    const files = [];
    try {
      for (let index = 0; index < Math.min(length, MAX_RESOURCE_COUNT + 1); index += 1) {
        files.push(fileList[index]);
      }
      return files;
    } catch (error) {
      files.length = 0;
      return files;
    }
  }

  function boundedItems(value) {
    return Array.isArray(value) ? value.slice(0, MAX_RESOURCE_COUNT + 1) : [];
  }

  function safeSelectedFileMetadata(file, size) {
    const raw = safeRawMetadata(file);
    const extension = supportedExtension(raw.filename);
    if (!extension) {
      return null;
    }
    const declaredMime = safeStringProperty(file, "type").trim().toLowerCase();
    if (declaredMime && declaredMime !== extension.mime) {
      return null;
    }
    return { filename: raw.filename, type: extension.type, size };
  }

  function safeRawMetadata(file) {
    const rawSize = safeNumberProperty(file, "size");
    return {
      filename: safeFilename(safeStringProperty(file, "name")),
      type: "unsupported",
      size: Number.isSafeInteger(rawSize) && rawSize >= 0 ? rawSize : 0,
    };
  }

  function projectedAttachmentFile(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }
    const filename = safeFilename(ownDataProperty(value, "filename", "string"));
    const type = ownDataProperty(value, "type", "string").trim().toLowerCase();
    const size = ownDataProperty(value, "size", "number");
    const contentBase64 = ownDataProperty(value, "content_base64", "string");
    const extension = supportedExtension(filename);
    if (
      !extension || extension.type !== type || !RESOURCE_TYPES.includes(type) ||
      !Number.isSafeInteger(size) || size <= 0 || size > MAX_RESOURCE_BYTES ||
      canonicalBase64DecodedSize(contentBase64) !== size
    ) {
      return null;
    }
    return { filename, type, size, content_base64: contentBase64 };
  }

  function projectedLimitations(value) {
    const projected = [];
    if (!Array.isArray(value)) {
      return projected;
    }
    for (const raw of value.slice(0, MAX_RESOURCE_LIMITATIONS)) {
      const code = ownDataProperty(raw, "code", "string").trim().toLowerCase();
      if (!Object.prototype.hasOwnProperty.call(LIMITATION_TEXT, code)) {
        continue;
      }
      const metadata = {
        filename: safeFilename(ownDataProperty(raw, "filename", "string")),
        type: normalizedResourceType(ownDataProperty(raw, "type", "string")),
        size: safeSize(ownDataProperty(raw, "size", "number")),
      };
      pushLimitation(projected, fixedLimitation(code, metadata));
    }
    return projected;
  }

  function fixedLimitation(code, metadata) {
    const safeCode = Object.prototype.hasOwnProperty.call(LIMITATION_TEXT, code)
      ? code
      : "resource_read_failed";
    const unsupported = ["unsupported_type", "candidate_omission"].includes(safeCode);
    return {
      code: safeCode,
      filename: safeFilename(metadata && metadata.filename),
      type: unsupported ? "unsupported" : normalizedResourceType(metadata && metadata.type),
      size: safeSize(metadata && metadata.size),
      limitation: LIMITATION_TEXT[safeCode],
    };
  }

  function pushLimitation(target, limitation) {
    if (target.length < MAX_RESOURCE_LIMITATIONS) {
      target.push(limitation);
    }
  }

  function supportedExtension(filename) {
    const match = String(filename || "").toLowerCase().match(/\.([a-z0-9]+)$/);
    if (!match || !Object.prototype.hasOwnProperty.call(EXTENSIONS, match[1])) {
      return null;
    }
    return EXTENSIONS[match[1]];
  }

  function normalizedResourceType(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return RESOURCE_TYPES.includes(normalized) ? normalized : "unsupported";
  }

  function safeFilename(value) {
    const normalized = String(value || "").replace(FORBIDDEN_FILENAME_CONTROLS, "");
    const basename = normalized.replaceAll("\\", "/").split("/").pop() || "";
    const safe = basename.replace(/[<>:"|?*]/g, "_").replace(/^\.+/, "").trim();
    return safe.slice(0, 120) || "resource";
  }

  function safeSize(value) {
    return Number.isSafeInteger(value) && value >= 0 ? value : 0;
  }

  function safeStringProperty(value, key) {
    try {
      return typeof value[key] === "string" ? value[key] : "";
    } catch (error) {
      return "";
    }
  }

  function safeNumberProperty(value, key) {
    try {
      return typeof value[key] === "number" ? value[key] : -1;
    } catch (error) {
      return -1;
    }
  }

  function ownDataProperty(value, key, expectedType) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return expectedType === "number" ? -1 : "";
    }
    try {
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      return descriptor && Object.prototype.hasOwnProperty.call(descriptor, "value") &&
        typeof descriptor.value === expectedType
        ? descriptor.value
        : expectedType === "number" ? -1 : "";
    } catch (error) {
      return expectedType === "number" ? -1 : "";
    }
  }

  function boundedBase64(bytes) {
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return root.btoa(binary);
  }

  function canonicalBase64DecodedSize(value) {
    if (!value || value.length > MAX_BASE64_CHARACTERS || value.length % 4 !== 0) {
      return -1;
    }
    const padding = value.endsWith("==") ? 2 : value.endsWith("=") ? 1 : 0;
    const dataLength = value.length - padding;
    for (let index = 0; index < dataLength; index += 1) {
      if (base64AlphabetValue(value[index]) < 0) {
        return -1;
      }
    }
    for (let index = dataLength; index < value.length; index += 1) {
      if (value[index] !== "=") {
        return -1;
      }
    }
    const lastValue = base64AlphabetValue(value[dataLength - 1]);
    if ((padding === 2 && (lastValue & 15) !== 0) || (padding === 1 && (lastValue & 3) !== 0)) {
      return -1;
    }
    return (value.length / 4) * 3 - padding;
  }

  function base64AlphabetValue(character) {
    const code = String(character || "").charCodeAt(0);
    if (code >= 65 && code <= 90) return code - 65;
    if (code >= 97 && code <= 122) return code - 71;
    if (code >= 48 && code <= 57) return code + 4;
    if (code === 43) return 62;
    if (code === 47) return 63;
    return -1;
  }

  root.EmailAssistantManualAttachmentFiles = Object.freeze({
    readSelectedFiles,
    mergeAttachmentFiles,
  });
})(typeof window !== "undefined" ? window : globalThis);
