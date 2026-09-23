const assert = require('node:assert/strict');
const { test } = require('node:test');
const { harness, fixture, descendants, loadPage } = require('./render_harness.cjs');

function copyPage(surface) {
  const h = harness();
  const state = {
    tab: { id: 1, url: 'https://exmail.qq.com/' }, fingerprint: 'msg-v1-0123456789abcdef',
    analysis: fixture(), writes: [], events: [], duringRevalidation: async () => {},
  };
  h.context.fetch = async () => ({ json: async () => ({ ok: true, analysis: state.analysis }) });
  h.context.EmailAssistantApi = { analyzeCurrentEmail: async () => ({ ok: true, analysis: state.analysis }) };
  h.context.chrome = { tabs: {
    query: async () => { state.events.push('active tab'); return state.tab ? [state.tab] : []; },
    sendMessage: async (_tabId, message) => {
      if (message.type === 'REVALIDATE_CURRENT_EMAIL') {
        state.events.push('message fingerprint');
        const fingerprint = state.fingerprint;
        await state.duringRevalidation();
        return { ok: true, message_fingerprint: fingerprint };
      }
      assert.equal(message.type, 'EXTRACT_CURRENT_EMAIL');
      return { ok: true, message_fingerprint: state.fingerprint, payload: { body_text: 'Synthetic current email' } };
    },
  } };
  const get = loadPage(h, surface);
  h.context.navigator.clipboard.writeText = async text => { state.events.push('clipboard'); state.writes.push(text); };
  return { ...h, get, state };
}

function assertCleared(get) {
  assert.equal(get('draft').value, '');
  assert.equal(get('work-conclusion').textContent, '暂无分析');
  assert.equal(get('work-next-steps').textContent, '-');
  assert.equal(get('copy-draft-button').disabled, true);
}

test('draft card preserves the visible body and always requires human review', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  analysis.reply_draft = {
    subject: 'Re: SYN-001', body: '  Please review.\n\nThank you.\n', needs_human_review: false,
    review_reasons: ['核实日期', '核实数量'], hidden_metadata: 'Never copy this',
  };
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.draftBody.value, '  Please review.\n\nThank you.\n');
  assert.equal(fields.draftSubject.textContent, 'Re: SYN-001');
  assert.equal(fields.draftReviewStatus.textContent, '需要人工审核');
  assert.match(fields.draftReviewReasons.textContent, /核实日期/);
  assert.match(fields.draftReviewReasons.textContent, /核实数量/);
  assert.equal(fields.copyButton.disabled, false);
  renderer.clearAnalysis(fields);
  assert.equal(fields.draftBody.value, '');
  assert.equal(fields.copyButton.disabled, true);
});

test('untrusted draft objects cannot supply inherited text, getters or automatic approval', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  const forbidden = () => { throw Error('untrusted accessor'); };
  analysis.reply_draft = Object.create({ subject: 'Hidden subject', body: 'Hidden body', review_reasons: ['Hidden reason'] });
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.draftBody.value, '');
  assert.equal(fields.draftSubject.textContent, '-');
  assert.equal(fields.copyButton.disabled, true);
  const draft = {};
  for (const name of ['subject', 'body', 'needs_human_review', 'review_reasons']) {
    Object.defineProperty(draft, name, { get: forbidden });
  }
  analysis.reply_draft = draft;
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.draftBody.value, '');
  assert.equal(fields.draftReviewStatus.textContent, '需要人工审核');
  assert.equal(fields.draftReviewReasons.textContent, '请人工核对草稿内容');
  Object.defineProperty(analysis, 'reply_draft', { get: forbidden });
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.copyButton.disabled, true);
});

test('both pages copy the exact visible body only and never copy on Analyze', async () => {
  for (const surface of ['popup', 'local']) {
    const { get, state } = copyPage(surface);
    state.analysis.reply_draft.body = '  Hello,\n\nPlease review.\n';
    state.analysis.reply_draft.hidden_metadata = 'private synthetic metadata';
    await get('analyze-button').dispatch('click');
    assert.deepEqual(state.writes, []);
    assert.equal(get('copy-draft-button').disabled, false);
    for (let click = 0; click < 2; click++) {
      state.events = [];
      await get('copy-draft-button').dispatch('click');
      assert.equal(state.writes[click], '  Hello,\n\nPlease review.\n');
      if (surface === 'popup') assert.ok(state.events.indexOf('message fingerprint') < state.events.indexOf('clipboard'));
      assert.equal(get('status').textContent, 'Draft copied');
    }
  }
});

test('switching the active tab while its old fingerprint is returning prevents clipboard access', async () => {
  const { get, state } = copyPage('popup');
  await get('analyze-button').dispatch('click');
  state.duringRevalidation = async () => { state.tab = { id: 2, url: 'https://exmail.qq.com/' }; };
  await get('copy-draft-button').dispatch('click');
  assert.deepEqual(state.writes, []);
  assert.equal(get('status').textContent, 'Email changed; analyze again');
  assertCleared(get);
});

test('clipboard completion cannot overwrite a newer email state on either page', async () => {
  for (const surface of ['popup', 'local']) {
    for (const outcome of ['success', 'failure']) {
      const { get, state, context } = copyPage(surface);
      await get('analyze-button').dispatch('click');
      let started, finish, fail;
      const writing = new Promise(resolve => { started = resolve; });
      context.navigator.clipboard.writeText = text => {
        state.writes.push(text);
        started();
        return new Promise((resolve, reject) => { finish = resolve; fail = reject; });
      };
      const copying = get('copy-draft-button').dispatch('click');
      await writing;
      if (surface === 'local') {
        await get('body').dispatch('input');
      } else {
        state.fingerprint = 'msg-v1-fedcba9876543210';
        await get('copy-draft-button').dispatch('click');
      }
      assert.equal(get('status').textContent, 'Email changed; analyze again');
      if (outcome === 'success') finish();
      else fail(new Error('private clipboard diagnostic'));
      await copying;
      assert.equal(get('status').textContent, 'Email changed; analyze again');
      assert.equal(state.writes.length, 1);
      assertCleared(get);
    }
  }
});

test('changed messages, tabs, navigation and unavailable browser context never reach the clipboard', async () => {
  const changes = [
    ({ state }) => { state.fingerprint = 'msg-v1-fedcba9876543210'; },
    ({ state }) => { state.tab = { id: 2, url: 'https://exmail.qq.com/' }; },
    ({ state }) => { state.tab = { id: 1, url: 'https://example.test/' }; },
    ({ state }) => { state.tab = null; },
    ({ context }) => { context.chrome.tabs.query = async () => { throw Error('private diagnostic'); }; },
    ({ context }) => { context.chrome.tabs.sendMessage = async () => { throw Error('private diagnostic'); }; },
  ];
  for (const change of changes) {
    const page = copyPage('popup');
    await page.get('analyze-button').dispatch('click');
    change(page);
    await page.get('copy-draft-button').dispatch('click');
    assert.deepEqual(page.state.writes, []);
    assert.equal(page.get('status').textContent, 'Email changed; analyze again');
    assertCleared(page.get);
  }
});

test('empty drafts and clipboard errors use fixed safe statuses on both pages', async () => {
  for (const surface of ['popup', 'local']) {
    const { get, state, context } = copyPage(surface);
    for (const body of ['', ' \n\t ', null, 123, { text: 'untrusted' }]) {
      state.analysis.reply_draft.body = body;
      await get('analyze-button').dispatch('click');
      assert.equal(get('copy-draft-button').disabled, true);
      await get('copy-draft-button').dispatch('click');
      assert.equal(get('status').textContent, 'No draft to copy');
      assert.deepEqual(state.writes, []);
    }
    state.analysis = fixture();
    await get('analyze-button').dispatch('click');
    for (const clipboard of [undefined, {}, { writeText: async () => { throw Error('private clipboard diagnostic'); } }]) {
      context.navigator.clipboard = clipboard;
      await get('copy-draft-button').dispatch('click');
      assert.equal(get('status').textContent, 'Copy failed');
      assert.equal(get('draft').value, fixture().reply_draft.body);
      assert.equal(get('copy-draft-button').disabled, false);
    }
  }
});

test('a changed visible draft during message revalidation is not copied', async () => {
  const { get, state } = copyPage('popup');
  await get('analyze-button').dispatch('click');
  state.duringRevalidation = async () => { get('draft').value = 'Changed without analysis'; };
  await get('copy-draft-button').dispatch('click');
  assert.deepEqual(state.writes, []);
  assertCleared(get);
});

test('a late copy check cannot clear or copy a newer analysis', async () => {
  const { get, state } = copyPage('popup');
  await get('analyze-button').dispatch('click');
  let started, finish;
  const checking = new Promise(resolve => { started = resolve; });
  state.duringRevalidation = () => { started(); return new Promise(resolve => { finish = resolve; }); };
  const copying = get('copy-draft-button').dispatch('click');
  await checking;
  state.duringRevalidation = async () => {};
  state.analysis = fixture();
  state.analysis.reply_draft.body = 'Newly analyzed draft';
  await get('analyze-button').dispatch('click');
  finish();
  await copying;
  assert.deepEqual(state.writes, []);
  assert.equal(get('draft').value, 'Newly analyzed draft');
  assert.equal(get('status').textContent, '分析完成');
});

test('draft subject and review reasons remain inert and malformed reasons use a safe reminder', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  const url = 'https://example.test/<img src=x onerror=alert(1)>/' + 'LONG无空格'.repeat(50);
  analysis.reply_draft = { subject: url, body: url, review_reasons: [url, {}, null, ''], needs_human_review: true };
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.draftSubject.textContent, url);
  assert.equal(fields.draftBody.value, url);
  assert.equal(fields.draftReviewReasons.textContent, url);
  assert.equal(descendants(fields.draftReviewReasons, 'A').length, 0);
  assert.equal(descendants(fields.draftReviewReasons, 'IMG').length, 0);
  analysis.reply_draft.review_reasons = [{ reason: 'untrusted' }, ''];
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.draftReviewReasons.textContent, '请人工核对草稿内容');
});
