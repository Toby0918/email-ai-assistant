"""Keyword sets and labels for the local rule analyzer."""

DELIVERY_KEYWORDS = ("delivery", "shipment", "order", "eta", "交期", "发货", "物流", "到货", "订单", "交付")
PAYMENT_KEYWORDS = ("payment", "invoice", "remittance", "overdue", "付款", "发票", "汇款", "逾期", "账期", "对账")
CONTRACT_KEYWORDS = ("contract", "agreement", "terms", "signing", "合同", "协议", "条款", "签署")
QUALITY_COMPLAINT_KEYWORDS = (
    "complaint",
    "quality complaint",
    "quality issue",
    "defective",
    "damaged",
    "defect",
    "rejected",
    "rejection",
    "iqc",
    "root cause",
    "corrective action",
    "rca",
    "out of tolerance",
    "burrs",
    "fail",
    "failed",
    "投诉",
    "质量异常",
    "不良",
    "损坏",
    "缺陷",
)
NEW_PRODUCT_KEYWORDS = (
    "new product",
    "new development",
    "new bottle trap",
    "introduce a new",
    "developing a solution",
    "project scope",
    "cost target",
    "target cost",
    "cost optimisation",
    "cost optimization",
    "feasibility",
    "technical or commercial",
    "performance objectives",
    "sample development",
    "prototype",
    "npi",
    "新产品",
    "新品",
    "开发",
    "项目范围",
    "成本目标",
    "可行性",
    "样品开发",
)
QUOTE_KEYWORDS = ("quote", "quotation", "rfq", "price", "报价", "询价", "价格")
INTERNAL_KEYWORDS = ("internal", "internally", "approval", "approve", "reviewer", "内部", "审批", "复核", "审核")
MARKETING_KEYWORDS = ("marketing", "promotion", "advertisement", "exhibition", "trade show", "brochure", "展会", "推广", "广告")
MEETING_KEYWORDS = ("meeting", "calendar", "invitation", "invite", "zoom", "会议", "邀请", "日程")
BOOKING_KEYWORDS = (
    "booking",
    "tracking number",
    "tracking",
    "original fe",
    "forwarder",
    "logistics",
    "air freight",
    "sea freight",
    "订舱",
    "货代",
    "追踪",
    "物流",
)

PRIORITY_LABELS = {"urgent": "紧急", "high": "高", "normal": "普通", "low": "低"}
RISK_LABELS = {
    "payment_risk": "付款风险",
    "delivery_risk": "交付/物流风险",
    "contract_risk": "合同风险",
    "quality_risk": "质量风险",
    "security_risk": "安全风险",
    "commitment_risk": "承诺风险",
    "prompt_injection_risk": "提示注入风险",
}
