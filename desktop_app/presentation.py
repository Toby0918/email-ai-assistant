"""Plain-text rendering keeps untrusted mail and model text inert."""


def engine_text(engine: object) -> str:
    if not isinstance(engine, dict):
        return "未确认分析引擎"
    if engine.get("source") == "rule_fallback":
        return "本地规则结果 · 未采用远程 AI 结果"
    label = engine.get("label")
    if not isinstance(label, str):
        return "未确认分析引擎"
    if engine.get("source") == "ai_model" and label in {
        "DeepSeek Flash", "DeepSeek V4 Flash", "DeepSeek V4 Pro",
    }:
        # DesktopRuntime uses the conservative DeepSeek route for these labels.
        return f"{label} 补充分析 · 处理建议和草稿由本地规则生成"
    if engine.get("source") == "ai_model" and label == "OpenAI GPT-5.6 Sol":
        return "OpenAI GPT-5.6 Sol"
    if engine.get("source") == "ai_model" and label in {
        "DeepSeek Flash text fallback", "DeepSeek V4 Flash text fallback", "DeepSeek V4 Pro text fallback",
    }:
        return "DeepSeek 文本回退分析"
    return "未确认分析引擎"


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
