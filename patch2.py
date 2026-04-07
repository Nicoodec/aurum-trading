import os

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = """def generate_dashboard(latest):
    from utils.state_manager import load_history
    history = load_history()
    stats = get_stats()
    data = {'latest': latest, 'history': history[-50:], 'stats': stats}
    os.makedirs('dashboard', exist_ok=True)
    os.makedirs('docs', exist_ok=True)
    for path in ['dashboard/state.json', 'docs/state.json']:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)"""

new = """def generate_dashboard(latest):
    from utils.state_manager import load_history
    from gen_dashboard import generate as gen_html
    history = load_history()
    stats = get_stats()
    gen_html(latest=latest, history=history, stats=stats)"""

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content.replace(old, new))
print('main.py dashboard fix OK')
