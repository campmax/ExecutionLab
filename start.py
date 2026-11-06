import json
from pathlib import Path
import subprocess
import sys
import webbrowser
from executionlab.live import validate_symbol
from executionlab.stocks import validate_stock

ROOT=Path(__file__).resolve().parent
PREFS=ROOT/'preferences.json'


def validate_preferences(data):
    allowed={'stocks','crypto','interval','feed','clock_account'}
    if not isinstance(data,dict) or set(data)-allowed:raise ValueError('Unknown preferences; only non-secret settings are accepted')
    defaults=dict(stocks=['SPY','QQQ','AAPL','MSFT','NVDA'],crypto=['BTC-USD','ETH-USD'],interval=5,feed='iex',clock_account='paper')
    defaults.update(data)
    for key,validator in [('stocks',validate_stock),('crypto',validate_symbol)]:
        symbols=defaults[key]
        if not isinstance(symbols,list) or not 1<=len(symbols)<=5 or len(set(symbols))!=len(symbols):raise ValueError('Use 1-5 distinct symbols')
        for symbol in symbols:validator(symbol)
    if type(defaults['interval']) not in (int,float) or not 2<=defaults['interval']<=15:raise ValueError('Interval must be 2-15 seconds')
    if defaults['feed'] not in ('iex','sip') or defaults['clock_account'] not in ('paper','live'):raise ValueError('Invalid feed/account')
    return defaults


def load_preferences(path=PREFS):
    return validate_preferences(json.loads(path.read_text()) if path.exists() else {})


def save_preferences(data,path=PREFS):
    value=validate_preferences(data)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def command(choice,preferences):
    stock=choice in ('1','2')
    demo=choice in ('2','4')
    args=[sys.executable,str(ROOT/('stock_monitor.py' if stock else 'monitor.py')),
          '--symbols',*preferences['stocks' if stock else 'crypto'],'--interval',str(.25 if demo else preferences['interval'])]
    if demo:args+=['--demo']
    if stock:args+=['--feed',preferences['feed'],'--clock-account',preferences['clock_account']]
    return args


def main():
    if sys.version_info<(3,10):raise SystemExit('Install Python 3.10 or newer.')
    try:preferences=load_preferences()
    except (ValueError,OSError,TypeError):
        print('Saved preferences could not be read. Using defaults until you save new settings.')
        preferences=validate_preferences({})
    while True:
        print('\nExecutionLab - stocks, crypto and execution research\n'
              '1  Stocks live (Alpaca keys required)\n2  Stocks demo (no keys)\n'
              '3  Crypto live (no keys)\n4  Crypto demo\n5  Change watchlists/settings\n'
              '6  Open backtest report\n7  Open quick-start guide\n0  Exit')
        choice=input('Choose: ').strip()
        if choice=='0':return
        if choice in ('1','2','3','4'):
            print('Starting monitor. Close it with Ctrl+C to return to this menu.')
            try:
                result=subprocess.run(command(choice,preferences),cwd=ROOT)
                if result.returncode:print('Monitor stopped with an error. Check the message above; no data has been substituted.')
            except KeyboardInterrupt:print('\nMonitor stopped.')
        elif choice=='5':
            try:
                updated=dict(preferences)
                for key in ('stocks','crypto'):
                    raw=input(f"{key.title()} watchlist [{', '.join(preferences[key])}]: ").strip().upper()
                    if raw:updated[key]=raw.replace(',',' ').split()
                updated['interval']=float(input(f"Refresh interval [{preferences['interval']} seconds]: ").strip() or preferences['interval'])
                updated['feed']=input(f"Stock feed: iex or sip [{preferences['feed']}]: ").strip().lower() or preferences['feed']
                updated['clock_account']=input(f"Alpaca key account: paper or live [{preferences['clock_account']}]: ").strip().lower() or preferences['clock_account']
                save_preferences(updated);preferences=validate_preferences(updated)
                print('Preferences saved. API keys are never stored here.')
            except (ValueError,OSError,TypeError) as exc:print(f'Settings not saved: {exc}')
        elif choice=='6':webbrowser.open((ROOT/'docs'/'index.html').as_uri())
        elif choice=='7':webbrowser.open((ROOT/'QUICK_START.html').as_uri())
        else:print('Choose a number from 0 to 7.')


if __name__=='__main__':
    try:main()
    except (EOFError,KeyboardInterrupt):print('\nGoodbye.')
