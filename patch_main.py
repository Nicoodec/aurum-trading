import os

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

addition = '''
    # Multi-timeframe analysis
    from agents.mtf_analyst import analyze as mtf_analyze
    mtf = mtf_analyze(price)
    print('      MTF confluence:', mtf.get('confluence'), '| Aligned:', mtf.get('aligned_timeframes'), '/3')
    cycle_data['mtf'] = mtf

    # Auto-close check
    from agents.auto_close import run_auto_close
    closed = run_auto_close(news)
    if closed:
        print('[auto_close] Closed', len(closed), 'positions')

    # Telegram alert
    try:
        from utils.telegram_alerts import alert_decision
        alert_decision(cycle_data)
    except Exception as e:
        print('[telegram] alert error:', e)
'''

# Insertar antes del return final
content = content.replace(
    "    sync('AURUM: ' + decision + ' @ ' + str(price.get('price')))",
    addition + "    sync('AURUM: ' + decision + ' @ ' + str(price.get('price')))"
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('main.py updated with MTF + auto-close + telegram')
