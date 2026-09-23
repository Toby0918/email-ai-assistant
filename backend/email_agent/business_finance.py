"""Explicit receipt and GRN blocking evidence; no inferred bank settlement."""
import re
from .business_projection import affirmative, fact, guarded, project, retracted

_ID = r'[A-Z]{2,8}\d{4,20}'
_RECEIPT = re.compile(r'\b(?:we\s+(?:(?:have\s+)?already\s+|have\s+)?received)\s+(?:the\s+)?'
    r'(?P<amount>(?:USD|EUR|CNY|RMB|\$|€|¥)\s*\d[\d,]*(?:\.\d+)?)\s+payment'
    r'(?:\s+on\s+(?P<date>\d{1,2}/\d{1,2}(?:/\d{2,4})?))?', re.I)
_PAID_INVOICE = re.compile(r'\b(?:we\s+(?:(?:have\s+)?already\s+|have\s+)?received)\s+(?:the\s+)?'
    rf'(?:remittance|payment)\s+for\s+(?P<invoice>{_ID})\b', re.I)


def apply_payment_evidence(result, body, visible_history=''):
    if guarded(result) or retracted(body) or not re.search(r'\b(?:payment|invoice|remittance|GRN|MRBR)\b', body, re.I):
        return
    facts, steps = [], []
    for clause in re.split(r'[\n;。]+', body):
        match = _RECEIPT.search(clause)
        if (match and affirmative(clause[:match.end()])
                and not re.search(r'\b(?:if|unless|provided|subject to|pending|not confirmed)\b',
                                  clause[match.end():], re.I)):
            value = match['amount'] + (f" on {match['date']}" if match['date'] else '')
            facts.append(fact('发件人报告已收款', value))
    blocked = []
    for paragraph in re.split(r'\n\s*\n', body):
        if (re.search(r'\bGRN\b', paragraph, re.I)
                and re.search(r'\bMRBR\b', paragraph, re.I)
                and not re.search(r'\b(?:no longer|(?:is|was|has been)\s+(?:unblocked|resolved))\b'
                                  r'|\bGRN\s+(?:is|was|has been)\s+(?:completed?|created)\b', paragraph, re.I)):
            # Bind a supported pending statement to its invoice, rather than
            # assigning a block to every identifier in the paragraph.
            identifiers = []
            for clause in re.split(r'(?<=[.!?])\s+|[\n;]', paragraph):
                if not affirmative(clause):
                    continue
                identifiers += re.findall(
                    rf'\b({_ID})(?:\s+of vendor [A-Za-z &,-]{{1,100}})?\s+is\s+'
                    r'(?:(?:currently|still)\s+)?blocked\b', clause, re.I)
                identifiers += re.findall(
                    rf'\b(?:please|we request you to(?: kindly)?)\s+create\s+(?:the\s+)?GRN\s+(?:against|for)\s+'
                    rf'(?:invoice\s+(?:no\.?\s*)?)?({_ID})\b', clause, re.I)
            for identifier in identifiers:
                if identifier not in blocked:
                    blocked.append(identifier)
                    facts.append(fact('待 GRN / MRBR 解锁', identifier + ' — 尚待 GRN，不能认定已付款'))
    if blocked:
        # Only corroborating receipt facts from visible quoted history; never
        # replay old requests as current work or overwrite a current block.
        for source, text in [('latest_message', body), ('visible_history', visible_history)]:
            for clause in text.splitlines():
                match = _PAID_INVOICE.search(clause)
                if match and affirmative(clause) and match['invoice'] not in blocked:
                    value = fact('发件人报告已收款发票', match['invoice'], source)
                    if not any(f['value'] == value['value'] for f in facts):
                        facts.append(value)
        steps = ['分别跟进 ' + '、'.join(blocked) + ' 的 GRN 创建与 MRBR 解锁；核对付款释放结果。']
        has_receipt = any('已收' in f['label'] for f in facts)
        draft = 'Please confirm the GRN creation and MRBR release status for ' + ', '.join(blocked) + '. '
        draft += ('We will reconcile the separately reported receipt against the remaining invoices before confirming payment status.'
                  if has_receipt else 'We will check the invoice records before confirming payment status.')
        conclusion = '按发票分别核对：部分款项报告已收；其余发票仍待 GRN / MRBR 解锁。' if has_receipt else '当前发票仍待 GRN / MRBR 解锁，解锁后是否已付款仍需核验。'
    elif facts:
        steps = ['核对已收到的款项，并索取付款明细及对应发票以完成匹配。']
        draft = 'Please provide the remittance details and corresponding invoices so we can reconcile the reported receipt. We will confirm the allocation after checking those records.'
        conclusion = '发件人报告已收到款项；当前待付款明细和对应发票匹配，不是未收款催付。'
    else:
        return
    result['risk_flags'] = [r for r in result['risk_flags'] if r['type'] != 'delivery_risk']
    project(result, category='payment', conclusion=conclusion, facts=facts, steps=steps, draft=draft,
            checks=['邮件中的已收款报告仍须与银行及发票记录核对；逐发票区分已收到、待匹配和待解锁。'])
