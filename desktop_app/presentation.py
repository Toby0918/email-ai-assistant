"""Plain-text rendering keeps untrusted mail and model text inert."""


def advice_text(analysis: dict) -> str:
    brief = analysis.get("decision_brief", {})
    parts = ["处理结论", brief.get("one_line_conclusion", analysis.get("summary", "")),
             "", "当前诉求", brief.get("requested_outcome", ""), "", "下一步"]
    for item in brief.get("next_steps", []):
        parts.append(item.get("step", ""))
    parts.extend(["", "关键事实"])
    for item in brief.get("key_facts", []):
        parts.append(f"{item.get('label', '')}：{item.get('value', '')}")
    parts.extend(["", "必须核查"])
    for item in brief.get("must_check", []):
        parts.append(item if isinstance(item, str) else "；".join(str(v) for v in item.values()))
    parts.extend(["", "风险提示"])
    for item in analysis.get("risk_flags", []):
        parts.append("；".join(str(v) for v in item.values()))
    return "\n".join(str(part) for part in parts)


def details_text(analysis: dict) -> str:
    import json
    selected = {key: analysis.get(key) for key in (
        "analysis_engine", "summary", "priority", "category",
        "conversation_timeline", "attachment_insights", "suggested_actions",
    )}
    return json.dumps(selected, ensure_ascii=False, indent=2)
