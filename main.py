import os, time, ccxt

MARGIN = 2.0
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
    'options': {'defaultType': 'swap'}
})

def set_lev(sym):
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated'})
        exchange.set_margin_mode('isolated', sym)
    except: pass

def get_signal(sym):
    ohlcv = exchange.fetch_ohlcv(sym, '5m', limit=100)
    closes = [c[4] for c in ohlcv]
    def ema(d,p):
        k=2/(p+1); e=d[0]
        for x in d[1:]: e=x*k+e*(1-k)
        return e
    return closes[-1], ema(closes,20), ema(closes,50), ema(closes[:-1],20), ema(closes[:-1],50)

print(f"🔴 NEUROBRO 2 ARAH $5 x{LEV} LIVE", flush=True)
pos = {} # sym -> 'long'/'short'

while True:
    for sym in SYMBOLS:
        try:
            price, e20, e50, pe20, pe50 = get_signal(sym)
            name = sym.split('/')[0]
            side_now = pos.get(name)

            # GOLDEN CROSS -> LONG
            if e20>e50 and pe20<=pe50:
                if side_now != 'long':
                    print(f"🟢 [LONG] {name} @ {price}", flush=True)
                    set_lev(sym)
                    # tutup short dulu kalau ada
                    if side_now == 'short':
                        try: exchange.create_market_buy_order(sym, (MARGIN*LEV)/price, {'tdMode':'isolated','reduceOnly':True})
                        except: pass
                    qty = (MARGIN*LEV)/price
                    exchange.create_market_buy_order(sym, qty, {'tdMode':'isolated'})
                    pos[name]='long'

            # DEATH CROSS -> SHORT
            elif e20<e50 and pe20>=pe50:
                if side_now != 'short':
                    print(f"🔴 [SHORT] {name} @ {price}", flush=True)
                    set_lev(sym)
                    if side_now == 'long':
                        try: exchange.create_market_sell_order(sym, (MARGIN*LEV)/price, {'tdMode':'isolated','reduceOnly':True})
                        except: pass
                    qty = (MARGIN*LEV)/price
                    exchange.create_market_sell_order(sym, qty, {'tdMode':'isolated'})
                    pos[name]='short'
        except Exception as e:
            print(f"[ERR] {sym} {e}", flush=True)
    time.sleep(60)
