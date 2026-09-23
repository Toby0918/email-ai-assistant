"""Explicit shipping fields and chronological allocation decisions."""
import re
from .business_projection import fact, guarded, project, retracted

_ID = r'[A-Z0-9][A-Z0-9-]{3,39}'


def apply_shipping_evidence(result, body):
    if guarded(result) or retracted(body):return
    facts=[]; due=''
    cutoff=re.search(r'截单时间(?:更新至|[：:])\s*(\d{1,2}/\d{1,2}(?:上午|下午)?\d{1,2}点)',body)
    etd=re.search(r'(?im)^\s*ETD(?:时间)?[：:]\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2})\s*$',body)
    vessel=re.search(r'(?m)^\s*(?:航名/航次|船名/航次)[：:]\s*([A-Z0-9][A-Z0-9 /-]{2,70})\s*$',body)
    bl=re.search(r'(?m)^\s*提单号[：:]\s*('+_ID+r')',body)
    if cutoff:facts.append(fact('截单 SI 截止',cutoff[1]+'（原文未写时区）'));due=cutoff[1]
    if etd:facts.append(fact('预计离港 ETD',etd[1]+'（计划，非实际离港）'))
    if vessel:facts.append(fact('当前船名/航次',vessel[1].strip()))
    if bl:facts.append(fact('提单号',bl[1]))
    if cutoff or (etd and vessel):
        for insight in result['attachment_insights']:
            for value in insight['key_facts']:
                if value.startswith('Shipping:'):facts.append(fact('附件船期',value,'attachment:'+insight['filename']))
        project(result,category='order_followup',conclusion='船务更新：分别核对截单 SI、计划 ETD 和最新船名/航次；尚不能认定已发运。',
            facts=facts, steps=['按更新的 SI 截止时间核查补料准备；确认当地时区。','核对最新船名、航次、提单号与附件，确认计划 ETD。'],
            draft='We will check the SI submission against the updated cutoff and confirm its time zone. We will also reconcile the updated vessel/voyage and bill of lading with the attachment. The ETD remains a planned departure, not confirmation of sailing.',
            checks=['SI 截止与 ETD 是不同事件；计划不等于已离港。','未写明时区时请向货代核实。'],due=due)
        return
    # Only compare statements explicitly ordered by the operator's ISO markers.
    blocks=re.split(r'(?m)^\[\d{4}-\d{2}-\d{2}T[^\]\n]+\]\s*$',body)
    if len(blocks)<3:return
    sea=list(re.finditer(r'We will ship (\d+) units later by sea\.',body,re.I))
    if not sea:return
    last=sea[-1];count=last[1]
    earlier=body[:last.start()]
    part=re.search(rf'\b{count}\s+units\s+of\s+({_ID})\b',earlier,re.I)
    if not part:return
    # A newer air decision would make this sea resolution stale.
    if re.search(r'\b(?:will|instead|changed)\b[^.\n]{0,80}\bair\b',body[last.end():],re.I):return
    facts=[fact('最新运输决定',f'{part[1]} — {count} units — 海运（sea）；替代早先空运讨论')]
    allocation=re.search(rf'(?P<part>{_ID})\s*[–-]\s*Go ahead[^\n]{{0,100}}?from (?P<origin>[A-Za-z ]{{3,50}}) to take (?P<qty>\d+) units(?: units)? from\s+their PO (?P<out>{_ID}) and replenish it to them later from (?P<target>[A-Z ]{{0,20}})PO\s+(?P<back>{_ID}) by (?P<date>\d{{1,2}}(?:st|nd|rd|th)? [A-Za-z]{{3,9}})',body,re.I)
    if allocation:
        a=allocation
        facts.append(fact('借调与补货',f"{a['part']} — 借调 {a['qty']} units；来源 {a['origin']} PO {a['out']}；补回来源 {a['target']}PO {a['back']}，原文日期 {a['date']}"))
    cancelled=re.search(r'no need to take it separately from ([A-Za-z ]{3,50})[.!]',body[last.end():],re.I)
    if cancelled:facts.append(fact('取消另行借调',f'{count} units — 不再从 {cancelled[1].strip()} 另行借调'))
    query=re.search(r'shipping date of (\d{1,2}/\d{1,2})[^\n]*[?？]',body[last.end():],re.I)
    if query:facts.append(fact('发运日期待确认',query[1]+' — 问句，未获得确认'))
    superseded = [m.group(0).strip() for m in re.finditer(
        rf'[^.\n]*\b{count}\s+units\s+of\s+{re.escape(part[1])}\b[^.\n]*\bby air\b[^.\n]*', earlier, re.I)]
    if cancelled:
        superseded.append(cancelled[0].rstrip('.!'))
    project(result,category='order_followup',conclusion='最新决定为海运；另一个料号的借调与补货单独跟进，不能合并数量或沿用已被替代的空运讨论。',facts=facts,
        steps=['按料号分别核对借调来源、补回订单和期限。','按最新海运决定核对生产安排，确认邮件问及的发运日期；不自行承诺。'],
        draft='We have noted the later sea-shipment decision. We will keep the separate item transfer and replenishment orders distinct, and check production readiness before confirming the proposed shipping date.',
        checks=['数量只适用于对应料号与借调/补回角色，不应相加为一个订单数量。','日期问句尚未形成已确认承诺。'],
        superseded_requests=superseded)
