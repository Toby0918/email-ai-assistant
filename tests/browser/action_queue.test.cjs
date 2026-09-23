const assert = require('node:assert/strict');
const { test } = require('node:test');
const { harness, fixture, descendants, loadPage } = require('./render_harness.cjs');

function assertPageCleared(get) {
  for (const id of ['work-next-steps', 'work-key-facts', 'work-must-check', 'work-risk-signals', 'risks', 'actions', 'priority', 'category', 'confidence']) {
    assert.equal(get(id).textContent, '-', id);
  }
  assert.equal(get('draft').value, '');
}

test('steps form an ordered queue with owner, due hint and original source', () => {
  const { renderer, fields } = harness();
  renderer.renderAnalysis(fields, fixture());
  assert.match(fields.nextSteps.textContent, /来源：邮件正文第 2 段/);
  assert.match(fields.nextSteps.textContent, /销售负责人/);
  assert.match(fields.nextSteps.textContent, /相关负责人/);
  assert.match(fields.nextSteps.textContent, /周五前/);
  assert.match(fields.nextSteps.textContent, /未指定/);
  assert.equal(descendants(fields.nextSteps, 'OL').length, 1);
  assert.equal(descendants(fields.nextSteps, 'LI').length, 2);
});

test('unknown owners and malformed optional fields never become authority or object text', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  let reads = 0;
  analysis.decision_brief.next_steps = ['constructor', '__proto__', 'toString', 'untrusted approver'].map(owner => ({
    step: '核查', owner_hint: owner, due_hint: { value: 'tomorrow' },
    get source() { reads++; return 'untrusted source'; },
  }));
  analysis.decision_brief.key_facts = [{ label: '订单', value: { nested: true } }];
  analysis.decision_brief.must_check = [{ nested: true }];
  renderer.renderAnalysis(fields, analysis);
  assert.equal(reads, 0);
  assert.equal((fields.nextSteps.textContent.match(/相关负责人/g) || []).length, 4);
  for (const field of Object.values(fields)) {
    assert.doesNotMatch(field.textContent, /\[object Object\]|function|untrusted/);
  }
});

test('all validated risk signals retain their order and full evidence remains available', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  analysis.primary_risk = { type: 'security_risk', level: 'high' };
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.riskSignals.textContent, '交付/物流风险（中）付款风险（低）');
  assert.match(fields.risks.textContent, /交期未确认/);
  assert.match(fields.risks.textContent, /付款待核对/);
  assert.match(fields.actions.textContent, /核查后回复客户/);
  assert.match(fields.mustCheck.textContent, /必须核查：核实排产/);
  assert.match(fields.mustCheck.textContent, /缺失信息：缺少发货日/);
  analysis.risk_flags = [];
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.riskSignals.textContent, '暂无已识别风险信号');
  assert.doesNotMatch(fields.risks.textContent, /交期未确认/);
  renderer.clearAnalysis(fields);
  for (const key of ['nextSteps', 'keyFacts', 'mustCheck', 'riskSignals', 'risks', 'actions']) {
    assert.equal(fields[key].textContent, '-');
  }
});

test('editing local email clears previous actions and ignores an in-flight result', async () => {
  const h = harness();
  let resolveResponse;
  h.context.fetch = async () => ({ json: async () => ({ ok: true, analysis: fixture() }) });
  const get = loadPage(h, 'local');
  await get('analyze-button').dispatch('click');
  assert.match(get('work-next-steps').textContent, /核对库存/);
  get('body').value = 'A different email';
  await get('body').dispatch('input');
  assertPageCleared(get);
  h.context.fetch = () => new Promise(resolve => { resolveResponse = resolve; });
  const pending = get('analyze-button').dispatch('click');
  assert.match(get('status').textContent, /60 秒/);
  await get('subject').dispatch('input');
  resolveResponse({ json: async () => ({ ok: true, analysis: fixture() }) });
  await pending;
  assertPageCleared(get);
  assert.equal(get('analyze-button').disabled, false);
});

test('popup clears every action on stale copy, service failure and partial render failure', async () => {
  const h = harness();
  let current = true;
  let result = { ok: true, analysis: fixture() };
  h.context.chrome = { tabs: {
    query: async () => [{ id: 1, url: 'https://exmail.qq.com/' }],
    sendMessage: async (_id, message) => message.type === 'REVALIDATE_CURRENT_EMAIL'
      ? { ok: current, message_fingerprint: 'msg-v1-0123456789abcdef' }
      : { ok: true, tab_id: 1, message_fingerprint: 'msg-v1-0123456789abcdef', payload: { body_text: 'Synthetic body' } },
  } };
  h.context.EmailAssistantApi = { analyzeCurrentEmail: async () => result };
  const get = loadPage(h, 'popup');
  await get('analyze-button').dispatch('click');
  assert.match(get('work-next-steps').textContent, /核对库存/);
  current = false;
  await get('copy-draft-button').dispatch('click');
  assertPageCleared(get);
  current = true;
  await get('analyze-button').dispatch('click');
  result = { ok: false, error: { code: 'LOCAL_HTTP_ERROR' } };
  await get('analyze-button').dispatch('click');
  assertPageCleared(get);
  const broken = fixture();
  Object.defineProperty(broken.reply_draft, 'body', { get() { throw new Error('synthetic render failure'); } });
  result = { ok: true, analysis: broken };
  await get('analyze-button').dispatch('click');
  assertPageCleared(get);
});

test('long mixed-language identifiers and URL-shaped values stay complete and inert', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  const identifier = 'SYN-零件-ABC123'.repeat(60);
  const url = 'https://example.test/<img src=x onerror=alert(1)>?id=' + identifier;
  analysis.decision_brief.key_facts = [{ label: '完整料号', value: identifier, source: '' }];
  analysis.decision_brief.next_steps[0].step = url;
  analysis.decision_brief.next_steps[0].source = url;
  renderer.renderAnalysis(fields, analysis);
  assert.ok(fields.keyFacts.textContent.includes(identifier));
  assert.ok(fields.nextSteps.textContent.includes(url));
  for (const field of Object.values(fields)) {
    assert.equal(descendants(field, 'A').length, 0);
    assert.equal(descendants(field, 'IMG').length, 0);
  }
});

test('missing, inherited or malformed collections reset populated fields safely', () => {
  const { renderer, fields } = harness();
  renderer.renderAnalysis(fields, fixture());
  const analysis = fixture();
  const brief = Object.create({ next_steps: fixture().decision_brief.next_steps });
  Object.defineProperty(brief, 'must_check', { get() { throw Error('must not invoke accessor'); } });
  analysis.decision_brief = brief;
  analysis.risk_flags = [{ type: 'constructor', level: 'high' }, { type: 'payment_risk', level: 'unknown' }, null];
  analysis.suggested_actions = null;
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.nextSteps.textContent, '暂无建议动作');
  assert.equal(fields.keyFacts.textContent, '暂无关键事实');
  assert.equal(fields.mustCheck.textContent, '暂无必须核查项');
  assert.equal(fields.riskSignals.textContent, '暂无已识别风险信号');
  assert.equal(fields.actions.textContent, '-');
  renderer.renderAnalysis(fields, {});
  assert.doesNotMatch(Object.values(fields).map(f => f.textContent).join(''), /\[object Object\]|核对库存/);
});

test('text-only consumers retain numbering, source and safe reset', () => {
  const { renderer } = harness();
  const fields = { nextSteps: { textContent: '' }, riskSignals: { textContent: '' } };
  renderer.renderAnalysis(fields, fixture());
  assert.match(fields.nextSteps.textContent, /第 1 步/);
  assert.match(fields.nextSteps.textContent, /来源：邮件正文第 2 段/);
  renderer.clearAnalysis(fields);
  assert.equal(fields.nextSteps.textContent, '-');
  assert.equal(fields.riskSignals.textContent, '-');
});
