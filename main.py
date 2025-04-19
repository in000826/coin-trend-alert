from flask import Flask
import ccxt
import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime
import os

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def fetch_ohlcv(symbol, timeframe='1h', limit=100):
    binance = ccxt.binance()
    data = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def check_signal(df):
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema55'] = ta.ema(df['close'], length=55)
    macd = ta.macd(df['close'])
    df['hist'] = macd['MACDh_12_26_9']
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    if (latest['ema9'] > latest['ema21'] > latest['ema55'] and
        prev['hist'] < 0 and latest['hist'] > 0):
        return 'long'
    elif (latest['ema9'] < latest['ema21'] < latest['ema55'] and
          prev['hist'] > 0 and latest['hist'] < 0):
        return 'short'
    return None

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': msg})

def get_top_volume_symbols(limit=20):
    binance = ccxt.binance()
    markets = binance.load_markets()
    tickers = binance.fetch_tickers()
    usdt_pairs = {
        symbol: ticker
        for symbol, ticker in tickers.items()
        if symbol.endswith('/USDT') and symbol in markets
    }
    sorted_pairs = sorted(usdt_pairs.items(), key=lambda x: x[1]['baseVolume'], reverse=True)
    return [symbol for symbol, _ in sorted_pairs[:limit]]

def run_alert_logic():
    always_watch = ['XRP/USDT', 'DOGE/USDT']
    top_symbols = get_top_volume_symbols(limit=20)
    symbols = list(set(always_watch + top_symbols))

    for symbol in symbols:
        try:
            df = fetch_ohlcv(symbol)
            signal = check_signal(df)
            if signal:
                emoji = '📈' if signal == 'long' else '📉'
                message = f"[{emoji} {signal.upper()} 신호]\n{symbol} @ {datetime.now().strftime('%H:%M')}"
                send_telegram(message)
        except Exception as e:
            print(f"오류: {symbol} - {e}")

@app.route("/run")
def run():
    run_alert_logic()
    return "알림 작업 완료", 200

if __name__ == "__main__":
    app.run()
