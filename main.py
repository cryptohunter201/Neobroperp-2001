import os, time, ccxt, requests

# ============ KONFIG ============
MARGIN  = 5.0
LEV     = 8
MAX_DAILY_LOSS = -20
SYMBOLS = ["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","SOL/USDT:USDT"]

def clean(v): return (v or "").strip().replace("\n","").replace("\r","").strip()

API_KEY      = clean(os.getenv("OKX_API_KEY"))
API_SECRET   = clean(os.getenv("OKX_API_SECRET"))
PASSPHRASE   = clean(os.getenv("OKX_PASSPHRASE"))
FONNTE_TOKEN = clean(os.getenv("FONNTE_TOKEN"))
WA_TARGET    = clean(os.getenv("WA_TARGET") or os.getenv("FONNTE_TARGET"))

# ============ NOTIF ============
def send_wa(pesan):
    if not FONNTE_TOKEN or not WA_TARGET: 
        print(f"[WA SKIP] {pesan}", flush=True); return
    try:
        r = requests.post("https://api.fonnte.com/send",
            headers={"Authorization": FONNTE_TOKEN},
            data={"target": WA_TARGET, "message": pesan, "countryCode": "62"},
            timeout=15)
        print(f"[WA] {r.status_code} {pesan[:50]}", flush=True)
    except Exception as e:
        print(f"[WA FAIL] {e}", flush=True)

# ============ INDIKATOR ============
def ema(d, p):
    k = 2 / (p + 1); e = d[0]
    for x in d[1:]: e = x * k + e * (1 - k)
    return e

def rsi_14(closes, period=14):
    if len(closes) < period+1: return 50
    gains = losses = 0.0
    for i in range(1, period+1):
        chg = closes[-i] - closes[-i-1]
        if chg >= 0: gains += chg
        else: losses -= chg
    if losses == 0: return 100.0
    rs = (gains / period) / (losses / period)
    return 100 - 100 / (1 + rs)

def atr_14(ohlcv, period=14):
    trs = []
    for i in range(1, len(ohlcv)):
        h, l, pc = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-period:]) / period

# ============ EXCHANGE ============
print(f"🔴 NEOBRO V13 NEW LOGIC - KEY LEN {len(API_KEY)}", flush=True)
exchange = ccxt.okx({
    'apiKey': API_KEY, 'secret': API_SECRET, 'password': PASSPHRASE,
    'enableRateLimit': True, 'options': {'defaultType': 'swap'},
})
# BYPASS - ini yang bikin lu error 2 jam tadi
exchange.has['fetchCurrencies'] = False
exchange.fetch_currencies = lambda *a, **k: {}
exchange.publicGetAssetCurrencies = lambda *a, **k: {'code':'0','data':[]}

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except Exception: pass
    for ps in ('long','short'):
        try: exchange.set_leverage(LEV, sym, {'mgnMode':'isolated','posSide':ps})
        except Exception: pass

CT_VAL = {}
def qty_contracts(sym, notional_usd):
    if sym not in CT_VAL:
        try:
            m = exchange.market(sym)
            CT_VAL[sym] = float(m['info'].get('ctVal', 1))
            CT_VAL[sym+"_price"] = float(m['info'].get('ctValCcy', 1)) # fallback
        except: CT_VAL[sym]=1
    # OKX: 1 contract = ctVal * price. ctVal untuk LIT dll = 1
    return max(1, int(notional_usd))

def open_order(sym, side, posSide, qty, atr, price):
    inst = sym.split(':')[0].replace('/','-') + '-USDT-SWAP'
    sl = price - 1.5*atr if side=='buy' else price + 1.5*atr
    tp = price + 2.0*atr if side=='buy' else price - 2.0*atr
    try:
        # 1. entry market
        exchange.create_order(sym, 'market', qty, None, {
            'instId': inst, 'tdMode': 'isolated', 'side': side,
            'posSide': posSide, 'ordType': 'market'})
        print(f"✅ ENTRY {posSide} {sym} {qty} @ {price}", flush=True)
        send_wa(f"{'🟢 LONG' if posSide=='long' else '🔴 SHORT'} {sym.split('/')[0]} @ {price}\nSL {sl:.4f} TP {tp:.4f} ATR {atr:.4f}")

        # 2. SL/TP algo (opsional, kalau gagal entry tetep jalan)
        try:
            exchange.private_post_trade_order_algo({
                'instId': inst, 'tdMode': 'isolated', 'side': 'sell' if side=='buy' else 'buy',
                'posSide': posSide, 'ordType': 'conditional',
                'sz': str(qty), 'tpTriggerPx': str(tp), 'tpOrdPx': '-1',
                'slTriggerPx': str(sl), 'slOrdPx': '-1'
            })
        except Exception as e:
            print(f"[SLTP WARN] {e}", flush=True)

    except Exception as e:
        msg = f"🚨 ORDER FAIL {sym} {posSide}: {e}"
        print(msg, flush=True); send_wa(msg); raise

def get_signal(sym):
    try:
        h1_ = exchange.fetch_ohlcv(sym, '1h', limit=200)
        ch  = [x[4] for x in h1_]
        bias = 'long' if ema(ch,50) > ema(ch,200) else 'short'

        m5_ = exchange.fetch_ohlcv(sym, '5m', limit=100)
        c5  = [x[4] for x in m5_]
        v5  = [x[5] for x in m5_]
        e20, e50 = ema(c5,20), ema(c5,50)
        rsi, atr = rsi_14(c5), atr_14(m5_)
        vol_up   = v5[-1] > v5[-2] * 1.2

        long_ok  = bias=='long' and e20>e50 and 40<rsi<55 and vol_up
        short_ok = bias=='short' and e20<e50 and 45<rsi<60 and vol_up
        sig = 'long' if long_ok else 'short' if short_ok else None
        return sig, atr, bias, rsi, e20, e50
    except Exception as e:
        print(f"[SIGNAL ERR {sym}] {e}", flush=True)
        return None, 0, None, 0, 0, 0

# ============ MAIN ============
daily_pnl, pos = 0.0, {}
try:
    bal = exchange.fetch_balance()
    print(f"SALDO OK: {bal.get('total',{}).get('USDT',0)}", flush=True)
    send_wa(f"🤖 NEOBRO V13 ON\nSaldo Trading: {bal.get('total',{}).get('USDT',0)} USDT")
except Exception as e:
    print(f"BALANCE ERR: {e}", flush=True)
    send_wa(f"🚨 BALANCE ERR: {e}")

while True:
    try:
        for sym in SYMBOLS:
            name = sym.split('/')[0]
            signal, atr, bias, rsi, e20, e50 = get_signal(sym)
            if not signal: continue
            if pos.get(name) == signal: continue

            price = exchange.fetch_ticker(sym)['last']
            qty   = qty_contracts(sym, MARGIN * LEV / price * 100) # approx
            if qty < 1: qty = 1

            print(f"[SCAN] {name} bias:{bias} sig:{signal} rsi:{rsi:.1f} {e20:.4f}/{e50:.4f} atr:{atr:.4f}", flush=True)

            set_lev(sym)
            if signal == 'long':
                if pos.get(name) == 'short':
                    open_order(sym,'buy','short',qty,atr,price)
                open_order(sym,'buy','long',qty,atr,price)
                pos[name]='long'
            elif signal == 'short':
                if pos.get(name) == 'long':
                    open_order(sym,'sell','long',qty,atr,price)
                open_order(sym,'sell','short',qty,atr,price)
                pos[name]='short'

        time.sleep(30)
    except Exception as e:
        print(f"[LOOP ERR] {e}", flush=True)
        time.sleep(10)
