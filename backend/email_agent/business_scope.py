"""Bounded, explicit business clauses with quantity and decision scope intact.

Statements are reports from the sender. These rules do not adjudicate a document,
infer state from a form's option list, authorize a change or calculate deadlines.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_NUMBER = r"(?:\d{1,3}(?:,\d{3}){1,3}|\d{1,9})(?:\.\d{1,4})?"
_COUNT = rf"{_NUMBER}\s*(?:pcs|pieces|units|Nos)"
_ID = r"[A-Z0-9][A-Z0-9_-]{3,39}"
_DATE = r"(?:TBA|\d{4}-\d{2}-\d{2})"


@dataclass(frozen=True)
class ScopeRule:
    pattern: str
    label: str
    check: str = ""
    missing: str = ""


_RULES = (
    ScopeRule(rf"Lot\s+(?:Qty|Quantity)\s*[:：]\s*(?P<value>{_COUNT})", "批次数量",
              "批次数量不等于不良数量；样本中的异常不能直接推广到整批。", "不良数量、比例与具体批次仍需核验。"),
    ScopeRule(rf"Cargo\s+gross\s+weight\s*:\s*(?P<value>{_NUMBER}\s*(?:kg|lb|lbs))", "货物毛重",
              "货物毛重与 VGM 的口径不同，不能混用或将差值自动认定为已核实皮重。"),
    ScopeRule(rf"VGM\s*:\s*(?P<value>{_NUMBER}\s*(?:kg|lb|lbs))", "VGM",
              "VGM 是含箱口径的申报重量；不是货物净重或毛重。"),
    ScopeRule(rf"Total\s+inventory(?:\s+across\s+all\s+finishes)?\s*(?:is|:)\s*(?P<value>{_COUNT})", "总库存",
              "总库存不是冻结、不良或已批准退货数量；不能据此认定 RMA 已接受。",
              "各表面处理的冻结数量、拟退数量及授权范围仍需核验。"),
    ScopeRule(r"(?:salt\s+spray|salt\s+spray\s+test)\s+(?:has\s+)?(?P<value>passed|failed|is pending)", "盐雾检验",
              "盐雾结论仅对应该检验项目，不能代替尺寸、功能或整批验收。"),
    ScopeRule(r"Dimensional\s+inspection\s+(?P<value>(?:passed|failed)(?:\s+on\s+(?:\d{1,4}|one|two|three|four|five|six|ten)\s+samples?)?)", "尺寸检验",
              "尺寸检验中的样本结论与整批数量分开；还需对应具体尺寸、图纸和批次。"),
    ScopeRule(r"(?:the\s+)?color\s+is\s+(?P<value>acceptable|approved|borderline)", "颜色评审",
              "颜色认可不等于功能测试通过；还需核对基材、表面处理、LTI 与测试项目。"),
    ScopeRule(rf"PPAP\s+for\s+SKU\s+(?P<value>{_ID})\s+is\s+approved", "PPAP 批准料号",
              "发件人报告的 PPAP 批准不能跨表面处理、料号或图纸版本扩大；需核验对应文件。"),
    ScopeRule(rf"PPAP\s+for\s+SKU\s+(?P<value>{_ID})\s+is\s+pending", "PPAP 待批准料号",
              "待批准料号不能沿用其他料号或表面处理的批准结论。"),
    ScopeRule(rf"ATA\s+transit\s+port\s*:\s*(?P<value>{_DATE})", "中转港实际到达",
              "中转港 ATA 不代表货物已到目的港或收货仓库。"),
    ScopeRule(rf"ETA\s+destination\s+port\s*:\s*(?P<value>{_DATE})", "目的港预计到达",
              "目的港 ETA 是预计时间；TBA 表示尚待明确，不得补出到港日期。"),
    ScopeRule(r"We\s+(?:accept|agree\s+to)\s+(?P<value>(?:the\s+)?original\s+prices\s+with\s+colou?r\s+boxes\s+for\s+this\s+order\s+only)", "适用范围",
              "本订单的接受不能扩大为未来订单或其他客户的永久价格政策；包装放行和费用审批另行核对。"),
)
_ALLOCATION = re.compile(
    rf"We\s+propose\s+to\s+take\s+(?P<count>{_COUNT})\s+from\s+PO\s+(?P<out>{_ID})\s+"
    rf"and\s+replenish\s+(?:them\s+)?later\s+from\s+PO\s+(?P<back>{_ID})", re.I,
)
_CONDITIONAL = re.compile(r"(?:the\s+)?(?:test\s+)?result\s+is\s+(?P<value>conditionally\s+OK|conditional\s+OK|YES[- ]CON)", re.I)


def apply_business_scope(result: dict[str, Any], body: str) -> None:
    if any(item['type'] in {'security_risk', 'prompt_injection_risk'} for item in result['risk_flags']):
        return
    # Cross-clause retractions and quoted/hypothetical declarations require review.
    if re.search(r"\b(?:correction|incorrect|retracted|withdrawn|hypothetical|if|unless|example|template|options)\b|not confirmed|更正|如果|假设|示例|模板", body, re.I):
        return
    body = re.split(r"(?im)^\s*(?:best regards|kind regards|regards|--|此致|祝好)\s*[,!。]?\s*$", body)[0]
    body = re.sub(r"\b(Qty)\.(?=\s|:)", r"\1", body, flags=re.I)
    brief = result['decision_brief']
    verdicts = {match.group(1).lower() for match in re.finditer(
        r"\bresult\s+is\s+([^.;\n]+)", body, re.I)}
    clauses = [clause.strip() for clause in re.split(r"[\n;；。]|\.(?=\s|$)", body[:8000]) if clause.strip()]
    status_only = all(
        _CONDITIONAL.fullmatch(clause)
        or re.fullmatch(rf"PPAP\s+for\s+SKU\s+{_ID}\s+is\s+(?:approved|pending)", clause, re.I)
        or re.fullmatch(r"Please see the updated ISIR|approval is subject to the stated conditions|Hello|Thank you", clause, re.I)
        for clause in clauses
    )
    timeline = result['conversation_timeline']
    other_open_work = any('Please see the updated ISIR' not in str(item.get('item', ''))
                          for item in timeline.get('open_items', []))
    latest_request = str(timeline.get('latest_external_request') or '')
    other_request = bool(latest_request and 'Please see the updated ISIR' not in latest_request)
    replace_generic = bool(status_only and not result['risk_flags'] and not other_open_work and not other_request)
    for clause in re.split(r"[\n;；。]|\.(?=\s|$)", body[:8000]):
        clause = clause.strip()
        for rule in _RULES:
            match = re.fullmatch(rule.pattern, clause, re.I)
            if not match:
                continue
            _fact(brief, rule.label, match['value'])
            _append(brief['must_check'], rule.check)
            _append(brief['missing_info'], rule.missing)
        if match := _ALLOCATION.fullmatch(clause):
            _fact(brief, '借出订单', f"PO {match['out']}; {match['count']}; 仅为提议")
            _fact(brief, '补回订单', f"PO {match['back']}; 计划后续补回")
            _append(brief['must_check'], '跨订单借货当前是提议；需核对借出、补回方向和明确批准，不能认定已经执行。')
        if re.fullmatch(r"Lead\s*time\s*:\s*\d{1,4}", clause, re.I):
            _fact(brief, '未明确单位的交期', clause)
            _append(brief['missing_info'], '交期单位及起算条件未明确；不能自动补成天、周或某个日期。')
        if match := re.fullmatch(r"Lead\s*time\s+is\s+(?P<days>\d{1,4})\s+days\s+after\s+the\s+official\s+instruction", clause, re.I):
            _fact(brief, '交期起算条件', f"{match['days']} days；官方指令后起算")
            _append(brief['must_check'], '条件性工期不能从邮件日期直接换算成交付承诺；先确认正式指令何时发出。')
        if re.fullmatch(r"Please\s+issue\s+the\s+official\s+PO", clause, re.I):
            _append(brief['missing_info'], '正式 PO 是否已签发仍待核验；样品方案接受不等于订单已发出。')
        if re.fullmatch(r"Please\s+arrange\s+telex\s+release", clause, re.I):
            _append(brief['must_check'], '放单请求不等于已放单；需核对承运人确认和本次所选放单凭据。')
        if (match := _CONDITIONAL.fullmatch(clause)) and len(verdicts) <= 1:
            _fact(brief, '条件检验结论', match['value'])
            _scope_advice(result,
                          '发件人报告检验为条件接受；必须先核对接受条件和适用范围，不能视作无条件批准。',
                          'We will review the stated conditions and supporting evidence before any further confirmation.',
                          'conditional_result', replace_generic)
            _append(brief['must_check'], '条件接受需对应具体料号、项目和附带条件；表单列出的可选项不等于实际勾选结果。')
    ppap = [item for item in brief['key_facts'] if item['label'] in {'PPAP 批准料号', 'PPAP 待批准料号'}]
    if ppap:
        _scope_advice(result,
            '发件人报告了特定料号的 PPAP 状态；须逐项核对批准范围和待批准项目，不能扩大为全部批准。',
            'We will review the PPAP status '
            'for each stated item and finish, including any pending or conflicting '
            'status, before further confirmation.', 'ppap_scope', replace_generic)
        approved = {item['value'].upper() for item in ppap if item['label'] == 'PPAP 批准料号'}
        pending = {item['value'].upper() for item in ppap if item['label'] == 'PPAP 待批准料号'}
        if approved & pending:
            _append(brief['must_check'], '同一料号同时出现批准与待批准状态；需核对时间、文件版本和发件人更正，不能认定已完成批准。')
    # Preserve the label when a generic quantity extractor found the same value.
    scoped = {item['value'] for item in brief['key_facts'] if item['label'] in {'批次数量', '总库存', '货物毛重', 'VGM'}}
    brief['key_facts'] = [item for item in brief['key_facts'] if not (item['label'] == '数量' and item['value'] in scoped)]
    if len(brief['key_facts']) > 20:
        brief['key_facts'] = brief['key_facts'][:20]
        _append(brief['missing_info'], '结构化事实条目已达显示上限，剩余内容需人工核验。')


def _fact(brief: dict[str, Any], label: str, value: str) -> None:
    item = {'label': label, 'value': value, 'source': 'latest_message'}
    if item not in brief['key_facts']:
        brief['key_facts'].append(item)


def _append(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _scope_advice(result: dict[str, Any], conclusion: str, paragraph: str,
                  tag: str, replace_generic: bool) -> None:
    brief = result['decision_brief']
    if replace_generic:
        result['summary'] = brief['one_line_conclusion'] = conclusion
        if result['category'] == 'internal':
            result['category'] = 'customer_inquiry'
            result['tags'] = [value for value in result['tags'] if value != 'internal'] + [tag]
        result['reply_draft']['body'] = f'Hello,\n\nThank you for the update. {paragraph}\n\nBest regards'
    else:
        # Scope supplements must never erase a request, escalation or open work.
        if conclusion not in result['summary']:
            result['summary'] += ' ' + conclusion
            brief['one_line_conclusion'] += ' ' + conclusion
        draft = result['reply_draft']['body']
        if paragraph not in draft:
            closing = '\n\nBest regards'
            result['reply_draft']['body'] = (draft.replace(closing, '\n\n' + paragraph + closing, 1)
                                              if closing in draft else draft + '\n\n' + paragraph)
