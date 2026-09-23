"""Project explicit business evidence into consistent review-only suggestions."""
import re


def guarded(result):
    return any(r['type'] in {'security_risk', 'prompt_injection_risk'} for r in result['risk_flags'])


def retracted(text):
    return bool(re.search(r'\b(?:correction|retracted|reversed|hypothetical|example)\b|更正|撤回|假设', text, re.I))


def fact(label, value, source='latest_message'):
    return {'label': label, 'value': value, 'source': source}


def project(result, *, category, conclusion, facts, steps, draft, checks=(), missing=(), due='',
            superseded_requests=()):
    """Call only for a recognized event; retain attachment limitations and risks."""
    if guarded(result):
        return
    brief = result['decision_brief']
    timeline = result['conversation_timeline']
    def superseded(item):
        text = ' '.join(item['item'].lower().split())
        return any(' '.join(clause.lower().split()) in text for clause in superseded_requests)
    old_items = timeline['open_items']
    retained = [item for item in old_items if not superseded(item)]
    if len(retained) != len(old_items):
        timeline['open_items'] = retained
        timeline['latest_external_request'] = '；'.join(item['item'] for item in retained)
        timeline['current_status'] = 'unresolved' if retained else 'unknown'
        timeline['status_reason'] = '仅移除有明确后续替代证据的请求；其他事项仍需核对。'
        timeline['confidence'] = 'low'
    request_facts = [fact('待处理请求', item['item'], item['source']) for item in retained]
    escalation = [a for a in result['suggested_actions'] if a['type'] == 'escalate']
    result['category'] = category
    result['summary'] = brief['one_line_conclusion'] = conclusion
    result['tags'] = [category, *[r['type'] for r in result['risk_flags']]]
    brief['key_facts'] = (facts[:15] + request_facts[:5])[:20]
    brief['requested_outcome'] = ('；'.join(item['item'] for item in retained)
                                  if retained else '未识别到明确待处理请求；请核对以下建议。')
    owner = {'payment': 'finance_owner', 'complaint': 'quality_owner',
             'order_followup': 'logistics_owner'}.get(category, 'account_owner')
    request_steps = [{'step': item['item'], 'owner_hint': item['owner_hint'],
                      'due_hint': item['due_hint'], 'source': item['source']} for item in retained]
    suggestions = [{'step': s, 'owner_hint': owner, 'due_hint': due,
                    'source': 'assistant_suggestion'} for s in steps[:4]]
    brief['next_steps'] = (request_steps + suggestions)[:4]
    result['suggested_actions'] = (escalation + [{'type': 'confirm', 'description': s,
                                   'owner_hint': owner, 'due_hint': due} for s in steps[:4]])[:4]
    brief['must_check'] = list(dict.fromkeys([*checks,
        *[s for s in brief['must_check'] if retained or escalation or '附件' in s]]))
    brief['missing_info'] = list(dict.fromkeys([*missing,
        *[s for s in brief['missing_info'] if (retained or escalation or '附件' in s)
          and not (due and '截止时间' in s)]]))
    brief['reply_recommendation'] = {'should_reply': True,
        'reply_type': 'escalate_first' if escalation else 'ask_clarification',
        'reason': '先升级给负责人核查风险，再审核回复。' if escalation else '针对明确业务事项核对或澄清；草稿仍须人工审核。'}
    brief['confidence'] = 'medium'
    if retained:
        draft += ' We will also review the remaining requests before confirming any action.'
    if escalation:
        draft += ' We will refer the quality concerns and any requested RCA to the responsible team for review.'
    result['reply_draft']['body'] = 'Hello,\n\nThank you for the update.\n' + draft + '\n\nBest regards'
    result['reply_draft']['needs_human_review'] = True


def affirmative(text):
    """Do not promote conditional, negated, corrected or questioned assertions."""
    return not re.search(r'\b(?:if|unless|not|never|correction|retracted|hypothetical|example)\b|[?？]|更正|尚未|如果', text, re.I)
