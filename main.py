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
    try:
        requests.post("https://api.fonnte.com/send", headers={"Authorization": FONNTE_TOKEN}, data={"target": WA_TARGET, "message": msg}, timeout=10)
    except: pass

exchange = ccxt.okx({
    'apiKey': API_KEY, 'secret': API_SECRET, 'password': PASSPHRASE,
    'enableRateLimit': True, 'options': {'defaultType': 'swap'}
})

print("=== NEOBRO V8 LENGKAP + WA ===", flush=True)
try:
    bal = exchange.fetch_balance()
    usdt = bal.get('USDT',{}).get('free',0)
    print(f"✅ SALDO OK: {usdt} USDT", flush=True)
    send_wa(f"✅ BOT V8 ON - SALDO {usdt} USDT - 5 KOIN AKTIF")
except Exception as e:
    print(f"❌ BALANCE ERR: {e}", flush=True)
    print(f"DETAIL: {getattr(exchange,'last_json_response',{})}", flush=True)
    time.sleep(15)

def get_ema(closes, p):
    k=2/(p+1); e=sum(closes[:p])/p
    for c in closes[p:]: e=c*k+e*(1-k)
    return e

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except: pass
    try:
        exchange.set_leverage(LEV, sym, {'mgnMode':'isolated','posSide':'long'})
        exchange.set_leverage(LEV, sym, {'mgnMode':'isolated','posSide':'short'})
    except: pass

def safe_order(sym, side, posSide, qty):
    inst = sym.split('/')[0]+"-USDT-SWAP"
    qty = max(1, int(qty)-1)  # buffer fee
    try:
        return exchange.private_post_trade_order({'instId':inst,'tdMode':'isolated','side':side,'posSide':posSide,'ordType':'market','sz':str(qty)})
    except Exception as e:
        # fallback net mode kalo hedge fail
        print(f"FAIL hedge {e}, coba net", flush=True)
        return exchange.private_post_trade_order({'instId':inst,'tdMode':'isolated','side':side,'ordType':'market','sz':str(qty)})

pos={}
while True:
    for sym in SYMBOLS:
        try:
            ohlcv=exchange.fetch_ohlcv(sym,'5m',limit=100)
            closes=[c[4] for c in ohlcv]; price=closes[-1]
            e20=get_ema(closes,20); e50=get_ema(closes,50)
            pe20=get_ema(closes[:-1],20); pe50=get_ema(closes[:-1],50)
            name=sym.split('/')[0]; side_now=pos.get(name)
            qty=round((MARGIN*LEV)/price)
            if qty<1: qty=1

            if e20>e50 and pe20<=pe50 and side_now!='long':
                msg=f"🟢 LONG {name} @{price} QTY {qty}"
                print(msg, flush=True); send_wa(msg)
                set_lev(sym)
                if side_now=='short': safe_order(sym,'buy','short',qty)
                safe_order(sym,'buy','long',qty)
                pos[name]='long'
            elif e20<e50 and pe20>=pe50 and side_now!='short':
                msg=f"🔴 SHORT {name} @{price} QTY {qty}"
                print(msg, flush=True); send_wa(msg)
                set_lev(sym)
                if side_now=='long': safe_order(sym,'sell','long',qty)
                safe_order(sym,'sell','short',qty)
                pos[name]='short'
        except Exception as e:
            print(f"[ERR] {sym}: {e}", flush=True)
    time.sleep(60)
