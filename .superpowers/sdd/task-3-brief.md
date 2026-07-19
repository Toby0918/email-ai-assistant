### Task 3: Classify business images and collect only approved resources

**Files:**
- Create: `frontend/browser_extension/content/exmail_visible_resource_classifier.js`
- Modify: `frontend/browser_extension/manifest.json`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/content/current_message_collector.js`
- Create: `tests/test_browser_extension_visible_resource_classifier.py`
- Modify: `tests/test_browser_extension_current_message_collector.py`
- Modify: `tests/test_browser_extension_task6_adapter.py`
- Modify: `tests/test_browser_extension_static.py`

**Interfaces:**
- Classifier output is internal only: `visible_attachment`, `inline_business_image`, or rejected.
- Accepted inline images become existing `attachment_files` with opaque safe names such as `inline-image-1.jpg`; no role, URL, DOM selector, or original filename is sent.
- Approved URLs remain same-origin HTTPS Tencent `/cgi-bin/download` or `/cgi-bin/viewfile` with a non-empty query and no credentials.

- [x] Add the inclusion matrix for a large current-body product/packaging photo and visible attachment control.
- [x] Add exclusion fixtures for the three supplied signature patterns, repeated images, signature-boundary media, logos, avatars, icons, 1x1 trackers, hidden media, quoted-history signatures, external sources, and ambiguous ownership; run RED.
- [x] Implement the pure classifier and integrate it only into the verified context from Task 2.
- [x] Preserve 20 candidates, 5 downloads, 10 MiB per resource, 25 MiB total, and 20-second resource-phase bounds.
- [x] Revalidate before and after fetch and discard redirected or stale resources.
- [x] Run extension suites and syntax checks GREEN; commit `feat: collect visible business media safely`.
