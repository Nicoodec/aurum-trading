
def decide(tech_signal, news_verdict, macro_result, risk_plan):
    """
    Decision final combinando señal tecnica, filtro de noticias y macro.

    tech_signal:  dict de signal_engine (o None)
    news_verdict: dict de news_filter {"verdict": CONFIRM|NEUTRAL|VETO, ...}
    macro_result: dict de macro_filter {"approved": bool, ...}
    risk_plan:    dict de risk_manager

    Returns: {"decision": LONG|SHORT|STAY_OUT, "confidence": int, "reason": str}
    """
    reasons = []

    # Gate 1: señal tecnica obligatoria
    if tech_signal is None:
        return {
            "decision":   "STAY OUT",
            "confidence": 0,
            "reason":     "No technical setup (EMA/RSI/ADX gate)",
        }

    direction   = tech_signal["signal"]
    tech_conf   = tech_signal.get("confidence", 60)
    tech_reason = tech_signal.get("reason", "")
    reasons.append(f"Technical: {tech_signal['sig_type']} {direction} (conf={tech_conf}%)")

    # Gate 2: macro filter
    if not macro_result.get("approved", True):
        macro_reasons = " | ".join(macro_result.get("reasons", []))
        return {
            "decision":   "STAY OUT",
            "confidence": 0,
            "reason":     "Macro VETO: " + macro_reasons,
        }

    for w in macro_result.get("warnings", []):
        reasons.append("Macro warn: " + w)

    size_mult = macro_result.get("size_multiplier", 1.0)

    # Gate 3: risk plan valid
    if not risk_plan.get("valid", False):
        return {
            "decision":   "STAY OUT",
            "confidence": 0,
            "reason":     "Risk invalid: " + str(risk_plan.get("reason", "")),
        }

    # Gate 4: news filter
    news_verd = news_verdict.get("verdict", "NEUTRAL") if news_verdict else "NEUTRAL"
    news_conf = news_verdict.get("confidence", 50)     if news_verdict else 50
    news_rsn  = news_verdict.get("reason", "")         if news_verdict else ""

    if news_verd == "VETO":
        return {
            "decision":   "STAY OUT",
            "confidence": 0,
            "reason":     "News VETO: " + news_rsn,
        }

    reasons.append(f"News: {news_verd} (conf={news_conf}%)")

    # Confidence calculation
    # Technical: 60% weight (primary signal)
    # News: 40% weight (confirmation)
    if news_verd == "CONFIRM":
        news_weight = 0.40
        tech_weight = 0.60
        final_conf  = round(tech_conf * tech_weight + news_conf * news_weight)
    else:  # NEUTRAL — trust technical more
        news_weight = 0.20
        tech_weight = 0.80
        final_conf  = round(tech_conf * tech_weight + 50 * news_weight)

    # Minimum confidence threshold
    if final_conf < 60:
        return {
            "decision":   "STAY OUT",
            "confidence": final_conf,
            "reason":     f"Confidence {final_conf}% below threshold (60%) | " + " | ".join(reasons),
        }

    full_reason = " | ".join(reasons)
    if news_rsn:
        full_reason += " | " + news_rsn

    return {
        "decision":        direction,
        "confidence":      final_conf,
        "reason":          full_reason,
        "size_multiplier": size_mult,
        "tech_signal":     tech_signal,
        "news_verdict":    news_verdict,
        "macro_result":    macro_result,
    }
