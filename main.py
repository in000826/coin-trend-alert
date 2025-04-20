from flask import Flask
import ccxt
import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime
import os

app = Flask(__name__)

BOT_TOKEN     = os.getenv("BOT_TOKEN")
CHAT_ID       = os.getenv("CHAT_ID")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_SECRET  = os.getenv("BYBIT_SECRET")

def fetch_ohlcv(symbol, timeframe='1h', limit=100):
    bybit = ccxt.bybit({
        'apiKey': BYBIT_API_KEY,
        'secret': BYBIT_SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    data = bybit.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','volume'])
    return df

def check_signal(df):
    df['ema9']  = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema55'] = ta.ema(df['close'], length=55)
    macd       = ta.macd(df['close'])
    df['hist'] = macd['MACDh_12_26_9']
    latest = df.iloc[-1]; prev = df.iloc[-2]

    if latest['ema9']>latest['ema21']>latest['ema55'] and prev['hist']<0 and latest['hist']>0:
        return 'long'
    if latest['ema9']<latest['ema21']<latest['ema55'] and prev['hist']>0 and latest['hist']<0:
        return 'short'
    return None

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    res = requests.post(url, data={'chat_id': CHAT_ID, 'text': msg})
    if res.status_code != 200:
        print("텔레그램 전송 실패:", res.text)

def get_top_volume_symbols(limit=20):
    # Bybit 공개 Market API를 직접 호출
    url  = "https://api.bybit.com/v5/market/tickers?category=spot"
    resp = requests.get(url)
    resp.raise_for_status()  # HTTPError 발생 시 예외
    data = resp.json()
    if data.get('retCode') != 0:
        print("티커 조회 오류:", data)
        return []
    tickers = data['result']['list']
    # USDT 페어만 필터링
    usdt = [t for t in tickers if t['symbol'].endswith('USDT')]
    # 24h 거래량 기준 내림차순 정렬
    sorted_usdt = sorted(usdt, key=lambda x: float(x.get('24hVolume',0)), reverse=True)
    return [t['symbol'] for t in sorted_usdt[:limit]]

def run_alert_logic():
    # 고정 감시 리스트
    always_watch = ['XRP/USDT','DOGE/USDT','SOL/USDT','PEPE/USDT','SUI/USDT']
    top_symbols  = get_top_volume_symbols(limit=20)
    symbols      = list({*always_watch, *top_symbols})

    for symbol in symbols:
        try:
            df     = fetch_ohlcv(symbol)
            signal = check_signal(df)
            if signal:
                emoji   = '📈' if signal=='long' else '📉'
                message = f"[{emoji} {signal.upper()} 신호]\n{symbol} @ {datetime.now().strftime('%H:%M')} (Bybit)"
                send_telegram(message)
        except Exception as e:
            print(f"{symbol} 오류:", e)

@app.route("/run")
def run():
    run_alert_logic()
    return "알림 작업 완료", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port)




