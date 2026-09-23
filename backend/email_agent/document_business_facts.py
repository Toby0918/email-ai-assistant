"""Finite typed document facts. No arbitrary document prose is exported."""
import re
from decimal import Decimal, InvalidOperation

ID = r'[A-Z0-9][A-Z0-9_/-]{2,39}'
NUM = r'\d[\d,]{0,12}(?:\.\d{1,4})?'
DATE = r'\d{1,2}/\d{1,2}/\d{4}'
CURRENCY = r'(?:CNY|RMB|USD|EUR|GBP)'
ROW = re.compile(rf'PO row: part=(?P<part>{ID}); delivery=(?P<date>{DATE}); quantity=(?P<qty>{NUM}) (?P<unit>EA|PC|PCS|SET); unit_price=(?P<currency>{CURRENCY}) (?P<price>{NUM}); net=(?P=currency) (?P<net>{NUM}); kind=(?P<kind>goods|expense)', re.I)
REPORT = re.compile(rf'Inspection report: id={ID}; status=Conditionally OK', re.I)
OBJECT = re.compile(r'Inspection object: material=\d{5,15}; supplier=\d{3,15}; change=[0-9/]{4,50}')
SHIP = re.compile(r'Shipping: vessel=[A-Z0-9][A-Z0-9 /-]{2,70}; ETD=\d{4}-\d{2}-\d{2}', re.I)


def valid_document_fact(value):
    return bool(ROW.fullmatch(value) or REPORT.fullmatch(value) or OBJECT.fullmatch(value) or SHIP.fullmatch(value))


def document_facts(text):
    text = text[:32_000]
    facts = []
    # Require a recognizable header, explicit currency, and arithmetically
    # consistent row. A random unlabeled number line is not a purchase row.
    currency = re.search(r'TOTAL NET AMT\s+('+CURRENCY+r')\b', text, re.I)
    if currency and re.search(r'QUANTITY\s+U/M\s+PRICE PER UNIT\s+NET AMT', text, re.I):
        pattern = rf'^\s*\d+\s+[A-Z0-9]+\s+(?P<description>[^\n]{{3,140}}?)\s+(?P<date>{DATE})\s+(?P<qty>{NUM})\s+(?P<unit>EA|PC|PCS|SET)\s+(?P<price>{NUM})\s+(?P<net>{NUM})\s*$'
        for m in re.finditer(pattern, text, re.I|re.M):
            desc=m['description'].strip(); expense=re.fullmatch(r'Expense to start production line\s+('+ID+')',desc,re.I)
            part=expense[1] if expense else desc.split()[0]
            if not re.fullmatch(ID,part,re.I) or (not expense and not any(c.isdigit() for c in part)):
                continue
            try:
                q,price,net=(Decimal(m[k].replace(',','')) for k in ('qty','price','net'))
                if q<=0 or price<0 or abs(q*price-net)>Decimal('0.01'):continue
            except InvalidOperation:continue
            c=currency[1].upper();kind='expense' if expense else 'goods'
            facts.append(f"PO row: part={part}; delivery={m['date']}; quantity={m['qty']} {m['unit']}; unit_price={c} {m['price']}; net={c} {m['net']}; kind={kind}")
    # This is an explicit report heading, not one of a form's options.
    for m in re.finditer(rf'(?m)^\s*({ID})\s+Conditionally OK\s*$',text,re.I):
        if 'Inspection Report' in text:
            facts.append(f'Inspection report: id={m[1]}; status=Conditionally OK')
    if re.search(r'Product name\s+Supplier no\.\s+Material no\.\s+Change no\.',text):
        m=re.search(r'(?m)^[A-Z][A-Z ()-]{2,60}\s+(\d{3,15})\s+(\d{5,15})\s+([0-9/]{4,50})\s*$',text)
        if m:facts.append(f'Inspection object: material={m[2]}; supplier={m[1]}; change={m[3]}')
    vessel=re.search(r'船名/航次[：:]\s*([A-Z0-9][A-Z0-9 /-]{2,70})',text)
    etd=re.search(r'预计开航[：:]\s*(\d{4}-\d{2}-\d{2})',text)
    if vessel and etd:facts.append(f'Shipping: vessel={vessel[1].strip()}; ETD={etd[1]}')
    return [f for f in facts if valid_document_fact(f)][:5]
