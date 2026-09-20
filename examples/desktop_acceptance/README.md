# Synthetic desktop acceptance instructions

All values are synthetic. Paste the entire contents of `email.txt` into the body
field; that file contains only email text. Keep these instructions out of the body.

Enter subject `Delivery date confirmation`, sender `buyer@example.test`, and
recipient `sales@example.test`. Select `Build/desktop-mail-acceptance/synthetic-order.xlsx`
from the project root, then explicitly click Analyze.

Review the quantity 1200 pcs from the attachment, an unconfirmed delivery date,
and a draft without an invented price or delivery commitment. The expected quantity
is deliberately absent from the email body so attachment extraction can be checked
independently. Inspect the model/rule contribution displayed in the status.

The previous combined fixture also contained an Expected review section. The
operator pasted that section into the email body during the second live run,
introducing extra price wording and the expected quantity. An offline comparison
through the actual local service with the XLSX showed the clean body categorized
as order_followup; including the review instructions produced customer_inquiry.
This documents a remaining keyword-classification limitation; it does not establish
robust quotation-intent understanding or pass semantic acceptance.

No restart or key re-entry is needed to replace the body in an already configured
session. Editing it correctly clears the previous analysis and review state.
