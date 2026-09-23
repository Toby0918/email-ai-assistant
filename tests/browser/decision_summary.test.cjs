const assert = require('node:assert/strict');
const { test } = require('node:test');
const { harness, fixture, descendants, loadPage } = require('./render_harness.cjs');

test('summary presents priority, category and Decision Brief confidence together with the conclusion', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  analysis.priority = 'high';
  analysis.confidence = 'low'; // Top-level confidence is not the Decision Brief contract.
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.priority.textContent, '高');
  assert.equal(fields.category.textContent, '订单/交付跟进');
  assert.equal(fields.confidence.textContent, '中');
  assert.equal(fields.conclusion.textContent, '核查后回复');
  assert.equal(fields.currentRequest.textContent, '确认交期');
  renderer.clearAnalysis(fields);
  for (const name of ['priority', 'category', 'confidence']) assert.equal(fields[name].textContent, '-');
});

test('unrecognized or malformed decision labels never display raw provider values or object text', () => {
  const { renderer, fields } = harness();
  for (const value of ['provider-private-label', 'constructor', '__proto__', 'toString', '', 42, null, [], {}]) {
    const analysis = fixture();
    analysis.priority = value;
    analysis.category = value;
    analysis.decision_brief.confidence = value;
    renderer.renderAnalysis(fields, analysis);
    assert.equal(fields.priority.textContent, '未确认');
    assert.equal(fields.category.textContent, '未确认');
    assert.equal(fields.confidence.textContent, '未确认');
    assert.doesNotMatch(fields.technicalDetails.textContent + fields.decisionBrief.textContent,
      /provider-private-label|function|\[object Object\]|__proto__|toString/);
  }
});

test('summary consumes only own data properties without invoking accessors or coercion', () => {
  const { renderer, fields } = harness();
  const prohibited = () => { throw Error('untrusted accessor or coercion was invoked'); };
  const analysis = fixture();
  for (const key of ['priority', 'category', 'summary', 'analysis_engine', 'decision_brief']) {
    Object.defineProperty(analysis, key, { get: prohibited });
  }
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.priority.textContent, '未确认');
  assert.equal(fields.category.textContent, '未确认');
  assert.equal(fields.confidence.textContent, '未确认');
  assert.equal(fields.conclusion.textContent, '暂无分析结论');
  assert.equal(fields.currentRequest.textContent, '暂无明确请求');
  assert.equal(fields.engine.textContent, '未确认分析引擎');
  const inherited = Object.create(fixture());
  renderer.renderAnalysis(fields, inherited);
  assert.equal(fields.priority.textContent, '未确认');
  assert.equal(fields.conclusion.textContent, '暂无分析结论');
  const nested = fixture();
  for (const key of ['one_line_conclusion', 'requested_outcome', 'confidence']) {
    Object.defineProperty(nested.decision_brief, key, { get: prohibited });
  }
  nested.summary = { toString: prohibited };
  nested.analysis_engine = { source: 'ai_model', label: 'private-provider', context_scope: 'constructor' };
  renderer.renderAnalysis(fields, nested);
  assert.equal(fields.conclusion.textContent, '暂无分析结论');
  assert.equal(fields.currentRequest.textContent, '暂无明确请求');
  assert.doesNotMatch(fields.technicalDetails.textContent, /function|private-provider|constructor/);
});

test('both pages expose the same decision labels after Analyze and clear them on failure', async () => {
  for (const surface of ['local', 'popup']) {
    const h = harness();
    let result = { ok: true, analysis: fixture() };
    let requests = 0;
    const response = () => { requests++; return result; };
    h.context.fetch = async () => ({ json: async () => response() });
    h.context.EmailAssistantApi = { analyzeCurrentEmail: async () => response() };
    h.context.chrome = { tabs: {
      query: async () => [{ id: 1, url: 'https://exmail.qq.com/' }],
      sendMessage: async () => ({ ok: true, tab_id: 1, message_fingerprint: 'msg-v1-0123456789abcdef', payload: { body_text: 'Synthetic email' } }),
    } };
    const get = loadPage(h, surface);
    assert.equal(requests, 0);
    await get('analyze-button').dispatch('click');
    assert.equal(get('priority').textContent, '普通', surface);
    assert.equal(get('category').textContent, '订单/交付跟进', surface);
    assert.equal(get('confidence').textContent, '中', surface);
    result = { ok: false, error: { code: 'LOCAL_HTTP_ERROR' } };
    await get('analyze-button').dispatch('click');
    for (const id of ['priority', 'category', 'confidence']) assert.equal(get(id).textContent, '-');
    assert.equal(get('analyze-button').disabled, false);
  }
});

test('engine messages stay fixed for model, DeepSeek fallback, rule fallback and unknown engines', () => {
  const { renderer, fields } = harness();
  const cases = [
    [{ source: 'ai_model', label: 'OpenAI GPT-5.6 Sol' }, 'OpenAI GPT-5.6 Sol', ''],
    ...['DeepSeek Flash text fallback', 'DeepSeek V4 Flash text fallback', 'DeepSeek V4 Pro text fallback'].map(label => [
      { source: 'ai_model', label }, 'DeepSeek text fallback', 'OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。',
    ]),
    [{ source: 'rule_fallback', label: 'Rule fallback' }, 'Rule fallback', '远程模型结果未采用，本次使用安全规则结果。'],
    [{ source: 'ai_model', label: 'untrusted label', fallback_reason: 'untrusted diagnostic' }, '未确认分析引擎', '分析引擎信息未确认，请人工核查本次结果。'],
    [null, '未确认分析引擎', '分析引擎信息未确认，请人工核查本次结果。'],
  ];
  for (const [engine, label, reason] of cases) {
    const analysis = fixture();
    analysis.analysis_engine = engine;
    renderer.renderAnalysis(fields, analysis);
    assert.equal(fields.engine.textContent, label);
    assert.equal(fields.fallbackBanner.textContent, reason);
    assert.equal(fields.fallbackBanner.hidden, !reason);
    assert.doesNotMatch(fields.technicalDetails.textContent, /untrusted/);
  }
  renderer.clearAnalysis(fields);
  assert.equal(fields.fallbackBanner.textContent, '');
  assert.equal(fields.fallbackBanner.hidden, true);
});

test('both pages retain the 60-second pending message and clear previous decision values', async () => {
  for (const surface of ['local', 'popup']) {
    const h = harness();
    let ready, finish;
    const started = new Promise(resolve => { ready = resolve; });
    const response = () => { ready(); return new Promise(resolve => { finish = resolve; }); };
    h.context.fetch = async () => ({ json: () => response() });
    h.context.EmailAssistantApi = { analyzeCurrentEmail: () => response() };
    h.context.chrome = { tabs: {
      query: async () => [{ id: 1, url: 'https://exmail.qq.com/' }],
      sendMessage: async () => ({ ok: true, tab_id: 1, message_fingerprint: 'msg-v1-0123456789abcdef', payload: { body_text: 'Synthetic email' } }),
    } };
    const get = loadPage(h, surface);
    const pending = get('analyze-button').dispatch('click');
    await started;
    assert.equal(get('status').textContent, '正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。');
    assert.equal(get('analyze-button').disabled, true);
    for (const id of ['priority', 'category', 'confidence']) assert.equal(get(id).textContent, '-');
    finish({ ok: true, analysis: fixture() });
    await pending;
    assert.equal(get('analyze-button').disabled, false);
    assert.equal(get('confidence').textContent, '中');
  }
});

test('missing summary values use safe placeholders and URL-shaped conclusions remain inert', () => {
  const { renderer, fields } = harness();
  const analysis = fixture();
  analysis.decision_brief = null;
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.conclusion.textContent, '核查后回复');
  assert.equal(fields.currentRequest.textContent, '暂无明确请求');
  assert.equal(fields.confidence.textContent, '未确认');
  analysis.summary = 123;
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.conclusion.textContent, '暂无分析结论');
  const text = 'https://example.test/<img src=x onerror=alert(1)>/订单'.repeat(20);
  analysis.decision_brief = { one_line_conclusion: text, requested_outcome: text };
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.conclusion.textContent, text);
  assert.equal(fields.currentRequest.textContent, text);
  assert.equal(descendants(fields.conclusion, 'A').length, 0);
  assert.equal(descendants(fields.currentRequest, 'IMG').length, 0);
});
