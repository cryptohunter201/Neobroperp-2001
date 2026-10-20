import os, time, ccxt, requests
MARGIN=5.0; LEV=8
SYMBOLS=["LIT/USDT:USDT","ONDO/USDT:USDT","SUI/USDT:USDT","SOL/USDT:USDT","ETH/USDT:USDT"]

def clean(v): return (v or "").strip().replace("\n","").replace("\r","")
API_KEY=clean(os.getenv("OKX_API_KEY")); API_SECRET=clean(os.getenv("OKX_API_SECRET")); PASSPHRASE=clean(os.getenv("OKX_PASSPHRASE"))
FONNTE_TOKEN=clean(os.getenv("FONNTE_TOKEN")); WA_TARGET=clean(os.getenv("WA_TARGET") or os.getenv("FONNTE_TARGET"))

def send_wa(p):
    try:
        if FONNTE_TOKEN and WA_TARGET:
            requests.post("https://api.fonnte.com/send", headers={"Authorization":FONNTE_TOKEN}, data={"target":WA_TARGET,"message":p,"countryCode":"62"}, timeout=10)
    except: pass

def ema(d,p):
    k=2/(p+1); e=d[0]
    for x in d[1:]: e=x*k+e*(1-k)
    return e
def rsi_14(c, period=14):
    gains=losses=0.0
    for i in range(1,period+1):
        chg=c[-i]-c[-i-1]
        if chg>=0: gains+=chg
        else: losses-=chg
    return 100.0 if losses==0 else 100-100/(1+(gains/period)/(losses/period))
def atr_14(o,p=14):
    trs=[]
    for i in range(1,len(o)):
        h,l,pc=o[i][2],o[i][3],o[i-1][4]
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    return sum(trs[-p:])/p

exchange=ccxt.okx({'apiKey':API_KEY,'secret':API_SECRET,'password':PASSPHRASE,'enableRateLimit':True,'options':{'defaultType':'swap'}})
exchange.has['fetchCurrencies']=False; exchange.fetch_currencies=lambda *a,**k:{}; exchange.publicGetAssetCurrencies=lambda *a,**k:{'code':'0','data':[]}

def set_lev(sym):
    try: exchange.set_position_mode(True)
    except: pass
    for ps in ('long','short'):
        try: exchange.set_leverage(LEV,sym,{'mgnMode':'isolated','posSide':ps})
        except: pass

def get_signal(sym):
    h1=exchange.fetch_ohlcv(sym,'1h',limit=200); ch=[x[4] for x in h1]; bias='long' if ema(ch,50)>ema(ch,200) else 'short'
    m5=exchange.fetch_ohlcv(sym,'5m',limit=100); c5=[x[4] for x in m5]; v5=[x[5] for x in m5]
    e20,e50=ema(c5,20),ema(c5,50); rsi=rsi_14(c5); atr=atr_14(m5); vol_up=v5[-1]>v5[-2]*1.2
    long_ok=bias=='long' and e20>e50 and 40<rsi<55 and vol_up
    short_ok=bias=='short' and e20<e50 and 45<rsi<60 and vol_up
    return ('long' if long_ok else 'short' if short_ok else None), atr

print("🔴 NEOBRO V13.3 FIX SIDE + ETH", flush=True)
pos={}
while True:
    try:
        bal=exchange.fetch_balance(); usdt=float(bal.get('total',{}).get('USDT',0) or 0)
        print(f"SALDO OK: {usdt}", flush=True)
        if usdt < 1.0:
            print("SALDO <1 - SKIP", flush=True); time.sleep(30); continue

        for sym in SYMBOLS:
            name=sym.split('/')[0]; sig,atr=get_signal(sym)
            if not sig or pos.get(name)==sig: continue
            price=exchange.fetch_ticker(sym)['last']
            # qty kontrak: OKX minimal 1
            qty=max(1,int(MARGIN*LEV/price*10) if price>10 else int(MARGIN*LEV))
            set_lev(sym)
            
            # FIX UTAMA DISINI
            side = 'buy' if sig=='long' else 'sell'
            posSide = sig
            instId = sym.split(':')[0].replace('/','-') + '-USDT-SWAP'
            
            # format ccxt yang bener: symbol, type, side, amount, price, params
            exchange.create_order(sym, 'market', side, qty, None, {
                'instId': instId,
                'tdMode': 'isolated',
                'posSide': posSide,
                'ordType': 'market'
            })
            
            pos[name]=sig
            msg=f"{'🟢 LONG' if sig=='long' else '🔴 SHORT'} {name} @ {price} qty {qty} ATR {atr:.4f}"
            print(msg, flush=True); send_wa(msg)

    except Exception as e:
        print(f"[ERR] {e}", flush=True)
        if '51000' not in str(e) and '51008' not in str(e): # jangan spam WA kalo cuma saldo
            send_wa(f"🚨 FAIL: {str(e)[:200]}")
        time.sleep(5)
    time.sleep(30)
