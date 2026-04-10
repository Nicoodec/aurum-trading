
# Thresholds calibrados para XAU/USD swing trading
DXY_VETO_LONG  = 125.0   # DXY muy alto = dolar muy fuerte = veto LONG oro
DXY_VETO_SHORT = 98.0    # DXY muy bajo = dolar muy debil = veto SHORT oro
DXY_WARN_LONG  = 121.0   # zona de precaucion para LONGs
DXY_WARN_SHORT = 101.0   # zona de precaucion para SHORTs

YIELD_VETO_LONG  = 4.8   # yields muy altos = veto LONG oro
YIELD_VETO_SHORT = 3.2   # yields muy bajos = veto SHORT oro
YIELD_WARN_LONG  = 4.4   # zona de precaucion para LONGs
YIELD_WARN_SHORT = 3.6   # zona de precaucion para SHORTs

# FTMO $25k swing
DAILY_LOSS_LIMIT  = 1250.0
TOTAL_LOSS_LIMIT  = 2500.0
PROFIT_TARGET_P1  = 2500.0   # fase 1: 10%
PROFIT_TARGET_P2  = 1250.0   # fase 2: 5%
BALANCE_INICIAL   = 25000.0
WARN_DAILY_PCT    = 0.60     # aviso cuando consumimos 60% del limite diario
WARN_TOTAL_PCT    = 0.60     # aviso cuando consumimos 60% del limite total

def check(direction, fred_data, account_info=None, daily_pnl=0.0):
    """
    Evalua condiciones macro y FTMO para una direccion propuesta.

    Returns:
        {
            "approved": bool,
            "verdict": "OK" | "WARN" | "VETO",
            "reasons": [str],
            "warnings": [str],
            "size_multiplier": float,   # 1.0 normal, 0.5 reducido, 0.0 veto
            "ftmo": dict,
        }
    """
    dxy = fred_data.get("dxy")
    t10 = fred_data.get("t10y")
    t2  = fred_data.get("t2y")

    reasons  = []
    warnings = []
    size_mult = 1.0
    approved  = True

    # ── FTMO checks ──────────────────────────────────────────
    bal = account_info.get("balance", BALANCE_INICIAL) if account_info else BALANCE_INICIAL
    eq  = account_info.get("equity",  BALANCE_INICIAL) if account_info else BALANCE_INICIAL

    total_dd     = BALANCE_INICIAL - eq
    daily_used   = abs(min(daily_pnl, 0))
    daily_left   = DAILY_LOSS_LIMIT - daily_used
    total_left   = TOTAL_LOSS_LIMIT - total_dd
    current_profit = bal - BALANCE_INICIAL

    ftmo = {
        "balance":        bal,
        "equity":         eq,
        "daily_pnl":      round(daily_pnl, 2),
        "daily_used":     round(daily_used, 2),
        "daily_left":     round(daily_left, 2),
        "total_drawdown": round(total_dd, 2),
        "total_left":     round(total_left, 2),
        "current_profit": round(current_profit, 2),
    }

    # Hard FTMO limits
    if daily_left <= 0:
        approved = False
        reasons.append(f"FTMO DAILY LIMIT HIT: used ${round(daily_used,2)} of ${DAILY_LOSS_LIMIT}")

    if total_left <= 0:
        approved = False
        reasons.append(f"FTMO TOTAL LIMIT HIT: drawdown ${round(total_dd,2)} of ${TOTAL_LOSS_LIMIT}")

    # Soft FTMO warnings
    if daily_left < DAILY_LOSS_LIMIT * (1 - WARN_DAILY_PCT) and approved:
        warnings.append(f"FTMO daily limit {round(daily_used/DAILY_LOSS_LIMIT*100)}% used — reducing size")
        size_mult = min(size_mult, 0.5)

    if total_left < TOTAL_LOSS_LIMIT * (1 - WARN_TOTAL_PCT) and approved:
        warnings.append(f"FTMO total limit {round(total_dd/TOTAL_LOSS_LIMIT*100)}% used — reducing size")
        size_mult = min(size_mult, 0.5)

    # ── DXY macro filter ─────────────────────────────────────
    if dxy:
        if direction == "LONG":
            if dxy >= DXY_VETO_LONG:
                approved = False
                reasons.append(f"MACRO VETO: DXY={round(dxy,1)} >= {DXY_VETO_LONG} — dollar too strong for gold LONG")
            elif dxy >= DXY_WARN_LONG:
                warnings.append(f"MACRO WARN: DXY={round(dxy,1)} elevated — reducing LONG size")
                size_mult = min(size_mult, 0.75)
        elif direction == "SHORT":
            if dxy <= DXY_VETO_SHORT:
                approved = False
                reasons.append(f"MACRO VETO: DXY={round(dxy,1)} <= {DXY_VETO_SHORT} — dollar too weak for gold SHORT")
            elif dxy <= DXY_WARN_SHORT:
                warnings.append(f"MACRO WARN: DXY={round(dxy,1)} low — reducing SHORT size")
                size_mult = min(size_mult, 0.75)

    # ── Yield macro filter ───────────────────────────────────
    if t10:
        if direction == "LONG":
            if t10 >= YIELD_VETO_LONG:
                approved = False
                reasons.append(f"MACRO VETO: 10Y={t10}% >= {YIELD_VETO_LONG}% — yields too high for gold LONG")
            elif t10 >= YIELD_WARN_LONG:
                warnings.append(f"MACRO WARN: 10Y={t10}% elevated — reducing LONG size")
                size_mult = min(size_mult, 0.75)
        elif direction == "SHORT":
            if t10 <= YIELD_VETO_SHORT:
                approved = False
                reasons.append(f"MACRO VETO: 10Y={t10}% <= {YIELD_VETO_SHORT}% — yields too low for gold SHORT")
            elif t10 <= YIELD_WARN_SHORT:
                warnings.append(f"MACRO WARN: 10Y={t10}% low — reducing SHORT size")
                size_mult = min(size_mult, 0.75)

    # ── Yield curve inversion ─────────────────────────────────
    if t10 and t2:
        spread = t10 - t2
        if spread < -0.5 and direction == "LONG":
            warnings.append(f"Yield curve inverted ({round(spread,2)}%) — recession risk, gold may spike then reverse")
        elif spread < -0.5 and direction == "SHORT":
            warnings.append(f"Yield curve inverted ({round(spread,2)}%) — gold may be bid as safe haven")

    verdict = "OK" if approved and not warnings else ("WARN" if approved else "VETO")

    return {
        "approved":        approved,
        "verdict":         verdict,
        "reasons":         reasons,
        "warnings":        warnings,
        "size_multiplier": round(size_mult, 2),
        "ftmo":            ftmo,
    }
