const assert = require('node:assert/strict');
const { test } = require('node:test');
const { harness, fixture, descendants, loadPage } = require('./render_harness.cjs');

test('only parsed attachments show content facts and every status states its limits', () => {
  const {renderer, fields} = harness();
  const analysis = fixture();
  analysis.attachment_insights = ['parsed', 'metadata_only', 'unavailable', 'failed', 'constructor'].map(status => ({
    filename: `${status}.pdf`, type: 'pdf', status,
    summary: 'CONTENT_SUMMARY', key_facts: ['Quantity 1200 pcs'], limitations: [],
  }));
  renderer.renderAnalysis(fields, analysis);
  const text = fields.attachmentInsights.textContent;
  for (const label of ['已解析', '仅元数据', '不可用', '解析失败', '状态未知']) assert.ok(text.includes(label));
  assert.equal((text.match(/CONTENT_SUMMARY/g)||[]).length, 1);
  assert.equal((text.match(/Quantity 1200 pcs/g)||[]).length, 1);
  assert.match(text, /不代表业务含义正确/);
  assert.doesNotMatch(text, /无已知解析限制|function/);
  renderer.clearAnalysis(fields);
  assert.equal(fields.attachmentInsights.textContent, '暂无附件洞察');
});

const fingerprint = 'msg-v1-0123456789abcdef';
const extraction = () => ({ok: true, message_fingerprint: fingerprint, payload: {body_text: 'Synthetic current email'}});
const deferred = () => { let resolve; const promise = new Promise(r => {resolve = r;}); return {promise, resolve}; };
const settle = () => new Promise(resolve => setImmediate(resolve));
function popupHarness() {
  const h = harness();
  const state = { extract: async () => extraction(), analyze: async () => ({ok:true, analysis:fixture()}), current:true };
  h.context.chrome = {tabs: {
    query: async () => [{id:1,url:'https://exmail.qq.com/'}],
    sendMessage: async (_id, message) => message.type === 'REVALIDATE_CURRENT_EMAIL'
      ? {ok:state.current,message_fingerprint:fingerprint} : state.extract(),
  }};
  h.context.EmailAssistantApi = {analyzeCurrentEmail: payload => state.analyze(payload)};
  const get = loadPage(h,'popup');
  return {...h,get,state};
}

test('reading, selected attachment reading and 60-second analysis disable controls until success', async () => {
  const {context,get,state} = popupHarness();
  const reading = deferred(), files = deferred(), result = deferred();
  state.extract = () => reading.promise;
  state.analyze = () => result.promise;
  context.EmailAssistantManualAttachmentFiles = {readSelectedFiles: () => files.promise};
  get('manual-attachment-files').files = [{name:'synthetic.pdf'}];
  const pending = get('analyze-button').dispatch('click');
  assert.equal(get('status').textContent, 'Reading current email');
  assert.equal(get('analyze-button').disabled,true);
  assert.equal(get('manual-attachment-files').disabled,true);
  reading.resolve(extraction()); await settle();
  assert.equal(get('status').textContent,'正在读取所选附件。');
  files.resolve({attachment_files:[],resource_limitations:[]}); await settle();
  assert.match(get('status').textContent,/60 秒/);
  result.resolve({ok:true,analysis:fixture()}); await pending;
  assert.equal(get('status').textContent,'分析完成');
  assert.equal(get('analyze-button').disabled,false);
  assert.equal(get('manual-attachment-files').disabled,false);
});

test('evidence projects own fields and hides private references and diagnostic credentials', () => {
  const {renderer, fields} = harness();
  const analysis = fixture();
  const secrets = ['C:\\private\\order.pdf', 'https://private.test/?token=SYN_SECRET',
    '/home/private/order.pdf', '\\\\server\\private', 'Cookie: SYN_SECRET',
    'Authorization: Bearer SYN_SECRET', 'api_key=SYN_SECRET', 'provider traceback SYN_SECRET'];
  analysis.attachment_insights = secrets.map(secret => ({filename: secret, type: secret,
    status: 'parsed', summary: secret, key_facts: [secret], limitations: [secret], unknown: 'UNKNOWN_SECRET'}));
  analysis.attachments = secrets.map(secret => ({filename: secret, type: secret, size: secret}));
  analysis.risk_flags = secrets.map(secret => ({type: 'security_risk', level: 'high', evidence: secret, recommendation: secret}));
  let reads = 0;
  analysis.attachment_insights.push(Object.create({filename: 'INHERITED_SECRET', status: 'parsed'}));
  analysis.attachment_insights.push({get summary(){reads++; return 'GETTER_SECRET';}, status: 'parsed'});
  renderer.renderAnalysis(fields, analysis);
  for (const name of ['attachmentInsights', 'attachments', 'risks']) {
    const field = fields[name];
    assert.doesNotMatch(field.textContent, /private|SECRET|provider traceback|function|\[object Object\]/);
    assert.equal(descendants(field, 'A').length, 0);
  }
  assert.equal(reads, 0);
  assert.match(fields.attachmentInsights.textContent, /已隐藏/);
  Object.defineProperty(analysis, 'attachment_insights', {get(){throw Error('must not read getter');}});
  renderer.renderAnalysis(fields, analysis);
  assert.equal(fields.attachmentInsights.textContent, '暂无附件洞察');
});

test('extraction failures never display content-script diagnostics and recover busy controls', async () => {
  const {get,state} = popupHarness();
  state.extract = async () => ({ok:false,error:'Cookie: SYN_SECRET https://private.test'});
  await get('analyze-button').dispatch('click');
  assert.equal(get('status').textContent,'Open a Tencent Exmail message or select email body text from that opened message first');
  assert.equal(get('analyze-button').disabled,false);
  assert.equal(get('manual-attachment-files').disabled,false);
  assert.equal(get('draft').value,'');
});

test('older analysis completion cannot clear a newer attachment selection or re-enable busy controls', async () => {
  const {get,state} = popupHarness();
  const first = deferred(), second = deferred();
  let requests = 0;
  state.analyze = () => ++requests === 1 ? first.promise : second.promise;
  const old = get('analyze-button').dispatch('click'); await settle();
  const current = get('analyze-button').dispatch('click'); await settle();
  get('manual-attachment-files').value = 'synthetic-new-selection';
  first.resolve({ok:true,analysis:fixture()}); await old;
  assert.equal(get('manual-attachment-files').value,'synthetic-new-selection');
  assert.equal(get('analyze-button').disabled,true);
  assert.equal(get('draft').value,'');
  second.resolve({ok:true,analysis:fixture()}); await current;
  assert.equal(get('manual-attachment-files').value,'');
  assert.equal(get('analyze-button').disabled,false);
});

test('conversation evidence ignores accessors, inherited and unknown fields and stays inert', () => {
  const {renderer,fields} = harness();
  const analysis = fixture();
  analysis.conversation_timeline = Object.assign(Object.create({previous_context:'INHERITED_SECRET'}), {
    current_status:'constructor', status_reason:'Cookie: SYN_SECRET', confidence:'__proto__',
    latest_external_request:'<img src=x> Synthetic request', unknown:'UNKNOWN_SECRET',
    open_items:[{item:'Follow up',source:'constructor',due_hint:'https://private.test',owner_hint:'constructor'}],
  });
  Object.defineProperty(analysis.conversation_timeline,'latest_internal_commitment',{get(){throw Error('getter');}});
  renderer.renderAnalysis(fields,analysis);
  assert.doesNotMatch(fields.conversationTimeline.textContent,/SECRET|private|function|\[object Object\]/);
  assert.match(fields.conversationTimeline.textContent,/Follow up/);
  assert.equal(descendants(fields.conversationTimeline,'IMG').length,0);
});

test('safe API errors recover both pages without retaining evidence or raw diagnostics', async () => {
  for (const surface of ['local','popup']) {
    const h = surface === 'popup' ? popupHarness() : harness();
    let response = {ok:true,analysis:fixture()};
    h.context.fetch = async () => ({json:async()=>response});
    if (h.state) h.state.analyze = async () => response;
    const get = h.get || loadPage(h,'local');
    for (const [code,message] of [
      ['LOCAL_ANALYSIS_TIMEOUT','本地分析服务超时，请重试。'],
      ['INVALID_LOCAL_RESPONSE','本地分析服务返回无效结果，请重试。'],
      ['LOCAL_HTTP_ERROR','本地分析服务请求失败，请重试。'],
      ['constructor','分析未完成，请重试。'],
    ]) {
      response = {ok:true,analysis:fixture()}; await get('analyze-button').dispatch('click');
      response = {ok:false,error:{code,message:'SYN_SECRET'}};
      await get('analyze-button').dispatch('click');
      assert.equal(get('status').textContent,message);
      assert.equal(get('draft').value,'');
      assert.equal(get('attachment-insights').textContent,'暂无附件洞察');
      assert.equal(get('analyze-button').disabled,false);
      assert.equal(get('copy-draft-button').disabled,true);
    }
  }
});

test('message changing during analysis rejects the full late result', async () => {
  const {get,state} = popupHarness();
  const result = deferred(); state.analyze = () => result.promise;
  const pending = get('analyze-button').dispatch('click'); await settle();
  state.current=false;
  result.resolve({ok:true,analysis:fixture()}); await pending;
  assert.equal(get('status').textContent,'Email changed; analyze again');
  assert.equal(get('draft').value,'');
  assert.equal(get('work-next-steps').textContent,'-');
  assert.equal(get('analyze-button').disabled,false);
});

test('local deadline rejects a late response and restores controls', async () => {
  const h = harness(), result = deferred();
  let expire;
  h.context.setTimeout = (callback,ms) => {assert.equal(ms,60000);expire=callback;return 1;};
  h.context.clearTimeout = () => {};
  h.context.fetch = () => result.promise;
  const get=loadPage(h,'local');
  const pending=get('analyze-button').dispatch('click');
  expire(); await pending;
  assert.equal(get('status').textContent,'本地分析服务超时，请重试。');
  result.resolve({json:async()=>({ok:true,analysis:fixture()})}); await settle();
  assert.equal(get('draft').value,'');
  assert.equal(get('analyze-button').disabled,false);
});
