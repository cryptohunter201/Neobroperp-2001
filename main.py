import os, time, ccxt, requests
MARGIN = 5.0
LEV = 8
SYMBOLS = ["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","ASTER/USDT:USDT","SOL/USDT:USDT"]

# STRIP biar gak ada spasi nyangkut kayak di foto 18:34 tadi
API_KEY = (os.getenv("OKX_API_KEY") or "").strip()
API_SECRET = (os.getenv("OKX_API_SECRET") or "").strip()
PASSPHRASE = (os.getenv("OKX_PASSPHRASE") or "").strip()
def send_wa_alert(pesan):
    try:
        requests.post("https://api.fonnte.com/send",
            headers={"Authorization": (os.getenv("FONNTE_TOKEN") or "").strip()},
            data={"target": (os.getenv("FONNTE_TARGET") or "").strip(), "message": pesan, "countryCode": "62"},
            timeout=10)
    except: pass
exchange = ccxt.okx({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'password': PASSPHRASE,
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},
})

# BLOKIR 2 biang kerok yg bikin error dari pagi
exchange.has['fetchCurrencies'] = False
exchange.fetch_currencies = lambda *a, **k: {}
exchange.publicGetAssetCurrencies = lambda *a, **k: {'code':'0','data':[]}

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except: pass
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'long'})
        exchange.set_leverage(LEV, sym, {'mgnMode': 'isolated', 'posSide': 'short'})
    except: pass

def safe_order(sym, side, posSide, qty):
    instId = sym.split('/')[0] + '-USDT-SWAP'
    qty = max(1, int(qty)-1) # buffer fee biar $5 gak mepet
    for mode in ['hedge','net']:
        try:
            p = {'instId': instId, 'tdMode': 'isolated', 'side': side, 'ordType': 'market', 'sz': str(qty)}
            if mode == 'hedge': p['posSide'] = posSide
            print(f"TRY {mode} {p}", flush=True)
            return exchange.private_post_trade_order(p)
        except Exception as e:
            print(f"FAIL {mode}: {e} | {getattr(exchange,'last_json_response',{})}", flush=True)
            if mode == 'net': raise

def get_signal(sym):
    ohlcv = exchange.fetch_ohlcv(sym, '5m', limit=100)
    closes = [c[4] for c in ohlcv]
    def ema(d,p):
        k=2/(p+1); e=d[0]
        for x in d[1:]: e=x*k+e*(1-k)
        return e
    return closes[-1], ema(closes,20), ema(closes,50), ema(closes[:-1],20), ema(closes[:-1],50)

print("🔴 NEUROBRO FINAL - SEMUA FIX GABUNG", flush=True)
try:
    bal = exchange.fetch_balance()
    print(f"SALDO OK: {bal.get('USDT',{})}", flush=True)
except Exception as e:
    print(f"BALANCE ERR: {e}", flush=True)
    print(f"OKX DETAIL: {getattr(exchange,'last_json_response','no response')}", flush=True)
    print(">>> CEK IP WHITELIST OKX, GANTI JADI 0.0.0.0/0 <<<", flush=True)

pos = {}
while True:
    for sym in SYMBOLS:
        try:
            price, e20, e50, pe20, pe50 = get_signal(sym)
            name = sym.split('/')[0]
            side_now = pos.get(name)
            qty = round((MARGIN*LEV)/price)

            if e20>e50 and pe20<=pe50 and side_now!='long':
                print(f"🟢 LONG {name} @ {price}", flush=True)
                set_lev(sym)
                if side_now=='short': safe_order(sym, 'buy', 'short', qty)
                safe_order(sym, 'buy', 'long', qty)
                pos[name]='long'

            elif e20<e50 and pe20>=pe50 and side_now!='short':
                print(f"🔴 SHORT {name} @ {price}", flush=True)
                set_lev(sym)
                if side_now=='long': safe_order(sym, 'sell', 'long', qty)
                safe_order(sym, 'sell', 'short', qty)
                pos[name]='short'

        except Exception as e:
    print(f"[ERR] {sym}: {e}", flush=True)
    send_wa_alert(f"🚨 FAIL {sym}: {e}")
    time.sleep(60)
