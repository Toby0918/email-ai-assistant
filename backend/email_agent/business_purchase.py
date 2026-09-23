"""Reconcile explicit purchase rows with the submitted revision context."""
import re
from .document_business_facts import ROW
from .business_projection import affirmative, fact, guarded, project, retracted


def apply_purchase_evidence(result, body, subject, visible_history=''):
    if guarded(result) or retracted(body) or not re.search(r'\b(?:PO|purchase order)\b',body+' '+subject,re.I):return
    rows=[];facts=[]
    for insight in result['attachment_insights']:
        if insight['status']!='parsed':continue
        for value in insight['key_facts']:
            m=ROW.fullmatch(value)
            if m:
                rows.append(m)
                facts.append(fact('采购单费用行' if m['kind']=='expense' else '采购单产品行',value,'attachment:'+insight['filename']))
    if not rows:return
    expense=all(m['kind']=='expense' for m in rows)
    if expense:
        pending=re.search(r'error in PO issue process for ([A-Z0-9-]{2,20})\b',body,re.I)
        if pending:facts.append(fact('待开立采购单',pending[1]+' — 开单出错，仍待修复及释放'))
        project(result,category='order_followup',conclusion='附件是开产费用采购单；EA 表示费用行计量，不能当成产品或样品数量。另行待开单事项须分开跟进。',facts=facts,
            steps=['核对开产费用、币种与费用行数量，按本次修订版本处理。','跟进仍未释放的采购单，不将费用单视为 PPAP 批准。'],
            draft='We have noted the production-line start-up expense PO and will check its amount and latest revision. Please send the separate pending PO once the issuance issue is resolved. The expense line does not establish product quantity or PPAP approval.',
            checks=['费用行的 EA 不等于产品/样品数量。','BRT 等表面处理的费用单不代表该产品已通过 PPAP。'])
        return
    revised=bool(re.search(r'\brevised\s+PO\b|latest version',body,re.I))
    finish=[]
    if revised:
        for line in visible_history.splitlines():
            m=re.search(r'(?:cargo(?:s|es)?|goods|production)\s+(?:will\s+)?finish\s+on\s+(\d{1,2}/\d{1,2}(?:/\d{4})?)',line,re.I)
            if m and affirmative(line) and m[1] not in finish:finish.append(m[1])
    for date in finish[:3]:facts.append(fact('可见历史预计完工',date+' — 原文未写年份时保持待核实','visible_history'))
    conflict=bool(finish and any('/'.join(m['date'].split('/')[:2]) != date for m in rows for date in finish))
    conclusion='修订采购单已给出单价、数量与净额；正文预计完工与采购单交期不一致，需核对年份、日期角色和可实现交期。' if conflict else '核对修订采购单的单价、数量、净额及交期；附件日期不是我方已确认承诺。'
    steps=['核对附件同一产品行的币种、unit price、数量和净额。', '澄清完工日期与采购单交期差异，在生产确认前不承诺。' if conflict else '核对生产安排后再确认可实现的交期。']
    project(result,category='order_followup',conclusion=conclusion,facts=facts,steps=steps,
        draft='We will check the revised unit price, quantity and net amount against the purchase order. '+
              ('The quoted completion date differs from the PO delivery date; please help reconcile those dates before we confirm a delivery commitment.' if conflict else 'We will confirm production readiness before accepting the delivery date.'),
        checks=['单价不等于净额或含税总额；数量必须对应同一产品行。','历史完工计划仅作核对证据，不能当成当前已确认交期。'])
