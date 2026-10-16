import os, time, ccxt

# CONFIG REAL
MARGIN = 5.0
LEV = 8
SYMBOLS = ["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","ASTER/USDT:USDT","SOL/USDT:USDT"]

API_KEY = os.getenv("OKX_API_KEY")
API_SECRET = os.getenv("OKX_API_SECRET")
PASSPHRASE = os.getenv("OKX_PASSPHRASE")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "false" # true = ga beneran order, cuma log

exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'} # futures USDT
})

def set_leverage(sym):
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated'})
    except: pass

def get_ema(sym):
    try:
        candles = exchange.fetch_ohlcv(sym, '5m', limit=100)
        closes = [c[4] for c in candles]
        def ema(d,p):
            k=2/(p+1); e=d[0]
            for x in d[1:]: e=x*k+e*(1-k)
            return e
        return closes[-1], ema(closes,20), ema(closes,50), ema(closes[:-1],20), ema(closes[:-1],50)
    except Exception as e:
        print(f"[ERR] {sym} {e}", flush=True)
        return None

print(f"[OK] REAL BOT MARGIN ${MARGIN} x{LEV} DRY_RUN={DRY_RUN}", flush=True)

pos = {}

while True:
    for sym in SYMBOLS:
        data = get_ema(sym)
        if not data: continue
        price, e20, e50, pe20, pe50 = data
        name = sym.split('/')[0]

        # BUY SIGNAL
        if e20>e50 and pe20<=pe50 and name not in pos:
            print(f"[BUY REAL] {name} @ {price} ${MARGIN} x{LEV}", flush=True)
            if not DRY_RUN:
                set_leverage(sym)
                amount = (MARGIN * LEV) / price # kontrak
                exchange.create_market_buy_order(sym, amount, {'tdMode':'isolated'})
            pos[name]=price

        # SELL SIGNAL
        elif e20<e50 and pe20>=pe50 and name in pos:
            entry=pos.pop(name)
            pnl_pct = (price-entry)/entry*100*LEV
            pnl_usd = MARGIN * pnl_pct / 100
            print(f"[SELL REAL] {name} {entry}->{price} PNL {pnl_pct:.2f}% = ${pnl_usd:.2f}", flush=True)
            if not DRY_RUN:
                # close all
                try:
                    exchange.create_market_sell_order(sym, (MARGIN*LEV)/price, {'tdMode':'isolated','reduceOnly':True})
                except:
                    # kalau error, pakai close_position
                    exchange.close_position(sym)

    time.sleep(60)
