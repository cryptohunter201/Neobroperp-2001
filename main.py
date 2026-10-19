import os, time, ccxt, requests, traceback, hmac, base64, hashlib, json
from datetime import datetime, timezone

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

# === FUNGSI CEK SALDO LANGSUNG KE OKX (ANTI CCXT ERROR) ===
def get_okx_balance_direct():
    try:
        method = "GET"
        request_path = "/api/v5/account/balance"
        body = ""
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        # OKX butuh format 2025-10-19T07:00:00.000Z
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        message = timestamp + method + request_path + body
        mac = hmac.new(API_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
        sign = base64.b64encode(mac.digest()).decode('utf-8')
        
        headers = {
            "OK-ACCESS-KEY": API_KEY,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": PASSPHRASE,
            "Content-Type": "application/json"
        }
        print(f"DEBUG KEY:{API_KEY[:5]}... PASS LEN:{len(PASSPHRASE)}", flush=True)
        r = requests.get(f"https://www.okx.com{request_path}", headers=headers, timeout=10)
        print(f"OKX RAW: {r.status_code} {r.text[:300]}", flush=True)
        data = r.json()
        if data.get('code') == '0':
            eq = data['data'][0].get('totalEq','0')
            return float(eq), data
        else:
            return None, data
    except Exception as e:
        traceback.print_exc()
        return None, str(e)

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

print("=== NEOBRO V12.2 BYPASS ===", flush=True)

bal_val, raw = get_okx_balance_direct()
if bal_val is not None:
    print(f"SALDO OK: {bal_val}", flush=True)
    send_wa(f"BOT V12.2 ON SALDO {bal_val}")
else:
    print(f"BALANCE ERR DETAIL: {raw}", flush=True)
    print("LANJUT TRADING...", flush=True)

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
