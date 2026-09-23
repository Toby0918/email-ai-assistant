"""Preserve per-test scope and explicit conditional acceptance."""
import re
from .business_projection import affirmative, fact, guarded, project, retracted


def apply_quality_evidence(result, body, subject):
    if guarded(result) or retracted(body):return
    clauses=re.split(r'[\n.!。]+',body)
    conditional=next((s for s in clauses if re.search(r'(?:test\s+)?result is Conditionally OK',s,re.I) and affirmative(s)),None)
    verdicts = {m.group(1).strip().lower() for m in re.finditer(
        r'\bresult\s+is\s+([^.;\n]+)', body, re.I)}
    if len(verdicts) > 1:
        return
    if conditional:
        facts=[fact('条件检验结论','Conditionally OK — 不等于无条件批准')]
        obj=re.search(r'ISIR-(\d{5,15})-(\d{4,15})-(\d{3,15})',subject,re.I)
        if obj:facts.append(fact('邮件所指检验对象',f'material={obj[1]}; change={obj[2]}; supplier={obj[3]}','subject'))
        for insight in result['attachment_insights']:
            for f in insight['key_facts']:
                if f.startswith(('Inspection report:', 'Inspection object:')):
                    facts.append(fact('附件检验对象/结论',f,'attachment:'+insight['filename']))
        project(result,category='customer_inquiry',conclusion='本次所指检验报告为条件接受；仅限对应料号和报告对象，具体附带条件仍须核验。',facts=facts,
            steps=['核对所指料号、变更号、报告编号及附带条件，再决定后续动作。'],
            draft='We have noted the conditional result for the referenced inspection. We will review the conditions against the specific material and report before further confirmation; this is not unconditional approval.',
            checks=['表单列出的 yes/no、approved/rejected 选项不是实际勾选结果。','条件性结论不得扩展到其他料号、试验或整批批准。'],
            missing=['具体附带条件及表单实际勾选/签署尚需人工查看原报告，不能从文本选项推定。'])
        return
    salt=next((s for s in clauses if re.search(r'(?:has\s+)?(?:already\s+)?(?:successfully\s+)?passed Salt Spray testing',s,re.I) and affirmative(s)),None)
    dimension=next((s for s in clauses if re.search(r'only need[^\n]{0,100}Dimensional review[^\n]{0,80}(?:have )?failed',s,re.I)),None)
    if salt and dimension:
        facts=[fact('盐雾检验','passed — 已通过，仅指盐雾项目'),fact('尺寸复核','previous samples failed — 先前样品尺寸复核未通过'),
               fact('所需样品','仅需送尺寸复核样品；不重复追加盐雾样品')]
        date=re.search(r'move up the sample availability date from ([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?)',body,re.I)
        if date:facts.append(fact('样品日期提前请求',date[1]+' — 争取提前，新日期尚未确认'))
        project(result,category='complaint',conclusion='盐雾已通过，先前尺寸复核未通过；当前只需尺寸复核样品，样品提前日期仍待确认。',facts=facts,
            steps=['与质量及生产负责人安排尺寸复核样品，不重复安排盐雾样品。','核对能否提前样品可用日期，再回复可实现的计划。'],
            draft='We have noted that salt spray testing has passed and no additional samples are needed for that test. We will arrange the samples for Dimensional review and check whether their availability can be brought forward before confirming a new date.',
            checks=['盐雾通过不等于尺寸通过或整体 PPAP/整批批准。','不要在生产确认前承诺提前日期。'])
