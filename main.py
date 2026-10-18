import os, time, ccxt, traceback

MARGIN = 5.0
LEV = 8
SYMBOLS = ["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","ASTER/USDT:USDT","SOL/USDT:USDT"]

exchange = ccxt.okx({
    'apiKey': os.getenv("OKX_API_KEY"),
    'secret': os.getenv("OKX_API_SECRET"),
    'password': os.getenv("OKX_PASSPHRASE"),
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},
})

# Blok currencies
exchange.has['fetchCurrencies'] = False
exchange.fetch_currencies = lambda *a, **k: {}
exchange.publicGetAssetCurrencies = lambda *a, **k: {'code':'0','data':[]}

def safe_order(sym, side, posSide, qty):
    instId = sym.split('/')[0] + '-USDT-SWAP'
    # Ambil lot size asli dari OKX biar gak ditolak
    try:
        markets = exchange.load_markets()
        lot = float(markets[sym]['info'].get('lotSz','1'))
        qty = max(lot, round(qty / lot) * lot)
        if lot >= 1: qty = int(qty) -1  # kasih buffer fee
    except: 
        qty = max(1, int(qty)-1)

    # Coba hedge mode dulu (punya lu)
    params_hedge = {
        'instId': instId, 'tdMode': 'isolated',
        'side': side, 'posSide': posSide,
        'ordType': 'market', 'sz': str(qty)
    }
    # Coba net mode (kalo akun lu one-way)
    params_net = {
        'instId': instId, 'tdMode': 'isolated',
        'side': side, 'ordType': 'market', 'sz': str(qty)
    }

    try:
        print(f"TRY HEDGE {params_hedge}", flush=True)
        return exchange.private_post_trade_order(params_hedge)
    except Exception as e1:
        print(f"GAGAL HEDGE: {e1}", flush=True)
        try:
            print(f"COBA NET MODE {params_net}", flush=True)
            return exchange.private_post_trade_order(params_net)
        except Exception as e2:
            print(f"GAGAL NET JUGA: {e2}", flush=True)
            try:
                print(f"OKX MSG: {exchange.last_json_response}", flush=True)
            except:
                pass
            raise e2

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except: pass
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'long'})
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'short'})
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated'})
    except: pass

def get_signal(sym):
    ohlcv = exchange.fetch_ohlcv(sym, '5m', limit=100)
    closes = [c[4] for c in ohlcv]
    def ema(d,p):
        k=2/(p+1); e=d[0]
        for x in d[1:]: e=x*k+e*(1-k)
        return e
    return closes[-1], ema(closes,20), ema(closes,50), ema(closes[:-1],20), ema(closes[:-1],50)

print(f"🔴 NEUROBRO V9 DIAGNOSA - TAMPILIN MSG OKX", flush=True)
# Cek saldo awal
try:
    bal = exchange.fetch_balance()
    print(f"SALDO TRADING: {bal.get('USDT',{})}", flush=True)
except Exception as e:
    print(f"BALANCE ERR: {e}", flush=True)

pos = {}
while True:
    for sym in SYMBOLS:
        try:
            price, e20, e50, pe20, pe50 = get_signal(sym)
            name = sym.split('/')[0]
            side_now = pos.get(name)
            qty = round((MARGIN*LEV)/price)

            if e20>e50 and pe20<=pe50:
                if side_now != 'long':
                    print(f"🟢 LONG {name} @ {price} qty={qty}", flush=True)
                    set_lev(sym)
                    if side_now == 'short': safe_order(sym, 'buy', 'short', qty)
                    safe_order(sym, 'buy', 'long', qty)
                    pos[name]='long'

            elif e20<e50 and pe20>=pe50:
                if side_now != 'short':
                    print(f"🔴 SHORT {name} @ {price} qty={qty}", flush=True)
                    set_lev(sym)
                    if side_now == 'long': safe_order(sym, 'sell', 'long', qty)
                    safe_order(sym, 'sell', 'short', qty)
                    pos[name]='short'

        except Exception as e:
            print(f"[ERR-FULL] {sym}: {e}", flush=True)
            traceback.print_exc()
            time.sleep(5)
    time.sleep(60)
