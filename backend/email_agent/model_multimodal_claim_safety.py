"""Fail-closed gate for model global prose when visual evidence is present."""

from __future__ import annotations

import re
import unicodedata

from .model_text_safety import is_safe_model_text

_PROTECTED_TRAIT_RE = re.compile(
    r"\b(?:sex|gender|pregnan(?:cy|t)|sexual\s+orientation|gay|lesbian|"
    r"bisexual|heterosexual|race|ethnicity|religion|jewish|muslim|"
    r"christian|hindu|buddhist|disability|disabled|medical|health\s+condition|"
    r"genetic|age|nationality|citizenship)\b|"
    r"(?:性别|怀孕|妊娠|性取向|同性恋|异性恋|双性恋|种族|民族|宗教|信仰|"
    r"犹太|残疾|残障|医疗|疾病|健康状况|基因|遗传|年龄|国籍|公民身份)",
    re.IGNORECASE,
)
_PERSON_IDENTIFICATION_RE = re.compile(
    r"(?:图中|图片中|照片中|影像中).{0,12}"
    r"(?:人物|人员|当事人|这个人).{0,8}(?:是|为|叫|名为|身份)|"
    r"\b(?:person|individual|subject)\s+(?:in\s+(?:the\s+)?(?:image|photo)\s+)?"
    r"(?:is|was|named|identified\s+as)\b|"
    r"(?:姓名|身份)(?:是|为|已识别)|(?:名叫|叫做|人物识别|人脸识别)|"
    r"(?:是|为|担任|属于)(?:客户|公司|销售|账户|业务|部门)?"
    r"(?:联系人|代表|员工|职员|负责人|经理|助理)|"
    r"\b(?:name\s+(?:is|was)|named|identified\s+as|person\s+identity)\b|"
    r"\b(?:is|was)\s+(?:an?\s+|the\s+)?(?:customer\s+|company\s+|sales\s+|"
    r"account\s+)?(?:contact|representative|employee|staff(?:\s+member)?|"
    r"manager|assistant)\b|"
    r"\b(?:contact|representative|employee|staff(?:\s+member)?|manager|"
    r"assistant)\s+(?:is|was)\b",
    re.IGNORECASE,
)
_TOOL_OR_SHELL_RE = re.compile(
    r"\b(?:powershell|cmd|shell|command|script|tool)\b|"
    r"(?:命令|脚本|工具)",
    re.IGNORECASE,
)


def multimodal_global_claim_is_safe(
    text: str, *, has_critical_signatures: bool
) -> bool:
    """Reject unsafe literal text authority introduced by multimodal routing."""
    if type(text) is not str or has_critical_signatures:
        return False
    normalized = unicodedata.normalize("NFKC", text)
    if any(char.isdigit() for char in normalized):
        return False
    return bool(
        is_safe_model_text(normalized)
        and not _PROTECTED_TRAIT_RE.search(normalized)
        and not _PERSON_IDENTIFICATION_RE.search(normalized)
        and not _TOOL_OR_SHELL_RE.search(normalized)
    )
