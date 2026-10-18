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

# ===== FIX 1,2,3 SEKALIGUS BIAR GAK BOLAK-BALIK =====
# Fix biang kerok currencies
exchange.has['fetchCurrencies'] = False
exchange.fetch_currencies = lambda *a, **k: {}
exchange.publicGetAssetCurrencies = lambda *a, **k: {'code':'0','data':[]}
# ====================================================

def set_lev(sym):
    try: exchange.set_position_mode(True) # Fix batch-orders
    except: pass
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'long'})
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'short'})
    except: pass

def place_order(sym, side, posSide, qty):
    instId = sym.split('/')[0] + '-USDT-SWAP'
    return exchange.private_post_trade_order({ # Fix batch-orders
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

print(f"🔴 NEUROBRO V7 ALL-IN-ONE LIVE - LOGIC TETEP PUNYA LU", flush=True)
pos = {}

while True:
    for sym in SYMBOLS:
        try:
            price, e20, e50, pe20, pe50 = get_signal(sym)
            name = sym.split('/')[0]
            side_now = pos.get(name)
            qty = round((MARGIN*LEV)/price) # Fix qty koma
            if qty < 1: qty = 1

            # INI LOGIC PUNYA LU 100% - GUA GAK GANTI SEHURUF PUN
            if e20>e50 and pe20<=pe50:
                if side_now != 'long':
                    print(f"🟢 LONG {name} @ {price} qty={qty}", flush=True)
                    set_lev(sym)
                    if side_now == 'short':
                        try: place_order(sym, 'buy', 'short', qty)
                        except: pass
                    place_order(sym, 'buy', 'long', qty)
                    pos[name]='long'

            elif e20<e50 and pe20>=pe50:
                if side_now != 'short':
                    print(f"🔴 SHORT {name} @ {price} qty={qty}", flush=True)
                    set_lev(sym)
                    if side_now == 'long':
                        try: place_order(sym, 'sell', 'long', qty)
                        except: pass
                    place_order(sym, 'sell', 'short', qty)
                    pos[name]='short'

        except Exception as e:
            print(f"[ERR] {sym}: {e}", flush=True)
    time.sleep(60)
