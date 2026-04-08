import json, os
from datetime import datetime, timedelta
from portfolio import load_positions, close_position, get_stats
from config import STATE_DIR

def sync_mt5_positions():
    """Detecta posiciones cerradas por SL/TP en MT5 y actualiza portfolio local."""
    results = []
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return results

        local_positions = load_positions()
        open_local = [p for p in local_positions if p["status"] == "OPEN" and p.get("ticket")]

        if not open_local:
            mt5.shutdown()
            return results

        # Obtener posiciones activas en MT5
        mt5_open = mt5.positions_get(symbol="XAUUSD")
        mt5_tickets = {p.ticket for p in (mt5_open or [])}

        for pos in open_local:
            ticket = pos["ticket"]
            if ticket not in mt5_tickets:
                # Posicion ya no existe en MT5 -- fue cerrada por SL/TP
                print("[sync] Position " + str(ticket) + " closed in MT5 -- syncing")

                # Buscar en historial de deals
                deals = mt5.history_deals_get(
                    datetime.now() - timedelta(hours=72),
                    datetime.now()
                )
                close_deal = None
                if deals:
                    for d in deals:
                        if d.position_id == ticket and d.entry == 1:  # 1 = close
                            close_deal = d
                            break

                if close_deal:
                    exit_price = close_deal.price
                    pnl        = close_deal.profit
                    result     = "WIN" if pnl > 0 else "LOSS"
                    close_position(pos["id"], exit_price, pnl)
                    print("[sync] ticket=" + str(ticket) + " closed at " + str(exit_price) + " PnL=$" + str(round(pnl,2)) + " " + result)

                    # Telegram alert
                    try:
                        from utils.telegram_alerts import alert_closed
                        alert_closed(pos, exit_price)
                    except: pass

                    results.append({
                        "ticket":      ticket,
                        "exit_price":  exit_price,
                        "pnl":         pnl,
                        "result":      result,
                    })
                else:
                    # No deal found -- mark as closed at last known price
                    print("[sync] ticket=" + str(ticket) + " closed but no deal found -- marking closed")
                    close_position(pos["id"], pos.get("entry", 0), 0)

        # Update current equity from MT5
        info = mt5.account_info()
        if info:
            equity_file = os.path.join(STATE_DIR, "mt5_account.json")
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(equity_file, "w", encoding="utf-8") as f:
                json.dump({
                    "balance":      info.balance,
                    "equity":       info.equity,
                    "profit":       info.profit,
                    "margin":       info.margin,
                    "free_margin":  info.margin_free,
                    "currency":     info.currency,
                    "leverage":     info.leverage,
                    "updated_at":   datetime.now().isoformat(),
                }, f, indent=2)

        mt5.shutdown()

    except Exception as e:
        print("[sync] error:", e)

    return results

def get_mt5_account():
    """Lee el ultimo estado de cuenta guardado."""
    equity_file = os.path.join(STATE_DIR, "mt5_account.json")
    if os.path.exists(equity_file):
        with open(equity_file, encoding="utf-8") as f:
            return json.load(f)
    return {}
