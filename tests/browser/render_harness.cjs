const fs = require('node:fs');
const vm = require('node:vm');

// A small DOM boundary double: production rendering and page handlers run unchanged.
class Element {
  constructor(tagName = 'div', ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.className = '';
    this.value = '';
    this.listeners = {};
  }
  set textContent(value) { this.children = []; this.text = String(value); }
  get textContent() { return (this.text || '') + this.children.map(x => x.textContent).join(''); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.text = ''; this.children = children; }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  async dispatch(type) { for (const callback of this.listeners[type] || []) await callback({ target: this }); }
}

function harness() {
  const elements = new Map();
  const document = {
    createElement: tag => new Element(tag, document),
    createTextNode: text => { const node = new Element('#text', document); node.textContent = text; return node; },
    querySelector: selector => {
      if (!elements.has(selector)) elements.set(selector, new Element('div', document));
      return elements.get(selector);
    },
  };
  const context = { document, setTimeout, clearTimeout, AbortController };
  context.window = context;
  vm.createContext(context);
  const load = path => vm.runInContext(fs.readFileSync(path, 'utf8'), context, { filename: path });
  load('frontend/browser_extension/shared/render_analysis.js');
  const fields = Object.fromEntries([
    'nextSteps', 'keyFacts', 'mustCheck', 'riskSignals', 'risks', 'actions', 'decisionBrief',
    'conclusion', 'currentRequest', 'draftBody', 'technicalDetails',
    'priority', 'category', 'confidence', 'summary', 'engine', 'fallbackBanner',
    'draftSubject', 'draftReviewStatus', 'draftReviewReasons', 'copyButton',
  ].map(name => [name, document.createElement('div')]));
  return { context, document, fields, load, renderer: context.EmailAssistantRender };
}

function fixture() {
  return {
    priority: 'normal', category: 'order_followup', summary: '核查后回复',
    analysis_engine: { source: 'rule_fallback', label: 'Rule fallback' },
    decision_brief: {
      one_line_conclusion: '核查后回复', requested_outcome: '确认交期', confidence: 'medium',
      next_steps: [
        { step: '核对库存', owner_hint: 'sales', due_hint: '周五前', source: '邮件正文第 2 段' },
        { step: '核对数量', owner_hint: 'untrusted approver', due_hint: '', source: '' },
      ],
      key_facts: [{ label: '订单', value: 'SYN-001', source: '邮件正文' }],
      must_check: ['核实排产'], missing_info: ['缺少发货日'],
    },
    risk_flags: [
      { type: 'delivery_risk', level: 'medium', evidence: '交期未确认', recommendation: '核查排产' },
      { type: 'payment_risk', level: 'low', evidence: '付款待核对', recommendation: '联系财务' },
    ],
    suggested_actions: [{ type: 'reply', description: '核查后回复客户', owner_hint: 'sales', due_hint: '' }],
    reply_draft: { subject: 'Re: SYN-001', body: 'We will verify the schedule.', needs_human_review: true },
  };
}

function descendants(element, tag) {
  return element.children.flatMap(child => [
    ...(child.tagName === tag ? [child] : []), ...descendants(child, tag),
  ]);
}

function loadPage(h, surface) {
  const popup = surface === 'popup';
  const directory = popup ? 'frontend/browser_extension' : 'frontend/local_debug_page';
  const html = fs.readFileSync(`${directory}/${popup ? 'popup' : 'index'}.html`, 'utf8');
  const ids = new Set(Array.from(html.matchAll(/id="([^"]+)"/g), match => `#${match[1]}`));
  const query = h.document.querySelector;
  h.document.querySelector = selector => ids.has(selector) ? query(selector) : null;
  h.context.navigator = { clipboard: { writeText: async () => {} } };
  const get = id => h.document.querySelector(`#${id}`);
  if (!popup) {
    for (const name of ['subject', 'from', 'to', 'sent-at', 'attachments-input', 'body']) get(name).value = '';
    get('body').value = 'Please confirm the schedule.';
  }
  h.load(`${directory}/${popup ? 'popup' : 'app'}.js`);
  return get;
}


module.exports = { harness, fixture, descendants, loadPage };
