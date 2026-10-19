import os, time, ccxt, requests

MARGIN = 5.0
LEV = 8
SYMBOLS = ["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","ASTER/USDT:USDT","SOL/USDT:USDT"]

API_KEY = (os.getenv("OKX_API_KEY") or "").strip()
API_SECRET = (os.getenv("OKX_API_SECRET") or "").strip()
PASSPHRASE = (os.getenv("OKX_PASSPHRASE") or "").strip()
FONNTE_TOKEN = (os.getenv("FONNTE_TOKEN") or "").strip()
WA_TARGET = (os.getenv("WA_TARGET") or "").strip()

def send_wa(msg):
    if not FONNTE_TOKEN or not WA_TARGET: return
    try: requests.post("https://api.fonnte.com/send", headers={"Authorization": FONNTE_TOKEN}, data={"target": WA_TARGET, "message": msg}, timeout=10)
    except: pass

exchange = ccxt.okx({
    'apiKey': API_KEY, 'secret': API_SECRET, 'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})
exchange.options['fetchCurrencies'] = False
exchange.has['fetchCurrencies'] = False
exchange.fetch_currencies = lambda *a, **k: {}
exchange.fetchCurrencies = lambda *a, **k: {}
exchange.publicGetAssetCurrencies = lambda *a, **k: {'code':'0','data':[]}
exchange.privateGetAssetCurrencies = lambda *a, **k: {'code':'0','data':[]}

print("=== NEOBRO V12 FINAL NO LOGIC CHANGE ===", flush=True)

try:
    bal = exchange.fetch_balance({'type':'swap'})
    usdt = bal.get('USDT',{}).get('free',0) or 0
    print(f"SALDO OK: {usdt}", flush=True)
    send_wa(f"BOT V12 ON SALDO {usdt}")
except Exception as e:
    print(f"BALANCE ERR: {e}", flush=True)

def get_ema(closes, period):
    k = 2/(period+1)
    ema = sum(closes[:period])/period
    for c in closes[period:]:
        ema = c*k + ema*(1-k)
    return ema

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except: pass
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode':'isolated','posSide':'long'})
        exchange.set_leverage(LEV, sym, {'mgnMode':'isolated','posSide':'short'})
    except: pass

pos={}
while True:
    for sym in SYMBOLS:
        try:
            ohlcv=exchange.fetch_ohlcv(sym,'5m',limit=100)
            closes=[c[4] for c in ohlcv]
            price=closes[-1]
            e20=get_ema(closes,20)
            e50=get_ema(closes,50)
            pe20=get_ema(closes[:-1],20)
            pe50=get_ema(closes[:-1],50)
            name=sym.split('/')[0]
            cur=pos.get(name)
            qty=max(1, int(round((MARGIN*LEV)/price))-1)

            if e20>e50 and pe20<=pe50 and cur!='long':
                print(f"LONG {name} {price}", flush=True)
                send_wa(f"LONG {name} {price}")
                set_lev(sym)
                inst=name+"-USDT-SWAP"
                if cur=='short':
                    exchange.private_post_trade_order({'instId':inst,'tdMode':'isolated','side':'buy','posSide':'short','ordType':'market','sz':str(qty)})
                exchange.private_post_trade_order({'instId':inst,'tdMode':'isolated','side':'buy','posSide':'long','ordType':'market','sz':str(qty)})
                pos[name]='long'
            elif e20<e50 and pe20>=pe50 and cur!='short':
                print(f"SHORT {name} {price}", flush=True)
                send_wa(f"SHORT {name} {price}")
                set_lev(sym)
                inst=name+"-USDT-SWAP"
                if cur=='long':
                    exchange.private_post_trade_order({'instId':inst,'tdMode':'isolated','side':'sell','posSide':'long','ordType':'market','sz':str(qty)})
                exchange.private_post_trade_order({'instId':inst,'tdMode':'isolated','side':'sell','posSide':'short','ordType':'market','sz':str(qty)})
                pos[name]='short'
        except Exception as e:
            print(f"[ERR] {sym}: {e}", flush=True)
    time.sleep(60)
