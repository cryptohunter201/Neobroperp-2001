import os, time, ccxt

MARGIN = 5.0
LEV = 8
SYMBOLS = ["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","ASTER/USDT:USDT","SOL/USDT:USDT"]

API_KEY = os.getenv("OKX_API_KEY")
API_SECRET = os.getenv("OKX_API_SECRET")
PASSPHRASE = os.getenv("OKX_PASSPHRASE")

exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},
})

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except: pass
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'long'})
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'short'})
    except: pass

def place_order(sym, side, posSide, qty):
    instId = sym.replace('/','-').replace(':USDT','-USDT-SWAP').replace('USDT-USDT','USDT')
    # LIT/USDT:USDT -> LIT-USDT-SWAP
    if 'LIT-' in instId: instId = 'LIT-USDT-SWAP'
    else: instId = sym.split('/')[0] + '-USDT-SWAP'
    return exchange.private_post_trade_order({
        'instId': instId,
        'tdMode': 'isolated',
        'side': side,
        'posSide': posSide,
        'ordType': 'market',
        'sz': str(int(qty))
    })

def get_signal(sym):
    ohlcv = exchange.fetch_ohlcv(sym, '5m', limit=100)
    closes = [c[4] for c in ohlcv]
    def ema(d,p):
        k=2/(p+1); e=d[0]
        for x in d[1:]: e=x*k+e*(1-k)
        return e
    return closes[-1], ema(closes,20), ema(closes,50), ema(closes[:-1],20), ema(closes[:-1],50)

print(f"🔴 NEUROBRO 2 ARAH $5 x{LEV} LIVE OKX V4-FIX", flush=True)
pos = {}

while True:
    for sym in SYMBOLS:
        try:
            price, e20, e50, pe20, pe50 = get_signal(sym)
            name = sym.split('/')[0]
            side_now = pos.get(name)
            qty = round((MARGIN*LEV)/price)
            if qty < 1: qty = 1

            if e20>e50 and pe20<=pe50:
                if side_now != 'long':
                    print(f"🟢 LONG {name} @ {price} qty={qty}", flush=True)
                    set_lev(sym)
                    if side_now == 'short':
                        try: place_order(sym, 'buy', 'short', qty)
                        except Exception as e2: print(f"close err {e2}", flush=True)
                    place_order(sym, 'buy', 'long', qty)
                    pos[name]='long'

            elif e20<e50 and pe20>=pe50:
                if side_now != 'short':
                    print(f"🔴 SHORT {name} @ {price} qty={qty}", flush=True)
                    set_lev(sym)
                    if side_now == 'long':
                        try: place_order(sym, 'sell', 'long', qty)
                        except Exception as e2: print(f"close err {e2}", flush=True)
                    place_order(sym, 'sell', 'short', qty)
                    pos[name]='short'
        except Exception as e:
            print(f"[ERR] {sym}: {e}", flush=True)
            try:
                import json
                print(f"DETAIL: {json.dumps(exchange.last_json)[:500]}", flush=True)
            except: pass
    time.sleep(60)
