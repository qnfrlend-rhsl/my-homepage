import os
import time
import requests
import pyupbit
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

if access_key and secret_key:
    upbit = pyupbit.Upbit(access_key, secret_key)
    print("✅ Upbit 객체 생성 완료")
else:
    print("⚠️ API 키가 없습니다. 확인해주세요!")
    exit()

previous_atr_percent = None  
atr_log_file = "atr_log.csv" 

######################################################
###############🔥 설정 변경하는 곳 🔥##################
BUY_AMOUNT = 5000  # 매수 금액
TARGET_PROFIT = 1.01  # 목표 상승률 (1.01% 은 1%라는 뜻, 현재는 0.6% 상승하면 매도)
BASE_ADD_BUY_DROP = 0.94  # 기본 추가 매수 하락률 (5% 하락하면 추가 매수)

# ✅ ATR 설정
TIMEFRAME = '1m'  # '1d' → 일봉, '15m' → 15분봉
ATR_PERIOD = 100  # ATR 계산 기간 

# ✅ 거래할 코인 목록
TICKERS = ['KRW-XLM' , 'KRW-ONDO' ]  # , 를 넣고 거래할 코인을 넣으면 됨. 'KRW-LAYER' , 'KRW-AUCTION'
######################################################

def send_message(msg):
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_ohlcv(ticker, timeframe=TIMEFRAME):
    ohlcv_data = pyupbit.get_ohlcv(ticker, interval=timeframe, count=ATR_PERIOD+1)
    if ohlcv_data is None or len(ohlcv_data) < ATR_PERIOD:
        raise ValueError(f"데이터가 충분하지 않음: {ticker}")
    return ohlcv_data

def calculate_atr(df):
    """ATR 계산"""
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    atr_value = df['TR'].rolling(window=ATR_PERIOD).mean().iloc[-1]
    return atr_value if not pd.isna(atr_value) else 0

def get_atr_percent(atr, current_price):
    if current_price > 0:
        return (atr / current_price) * 100
    return 0

def adjust_buy_drop_based_on_atr(atr_percent):
    if atr_percent > 10:  
        return BASE_ADD_BUY_DROP * 0.90 
    elif atr_percent < 3:  
        return BASE_ADD_BUY_DROP * 0.98 
    return BASE_ADD_BUY_DROP    


def log_atr_data(ticker, atr_value, atr_percent):
    log_data = pd.DataFrame([[time.strftime("%Y-%m-%d %H:%M:%S"), ticker, atr_value, atr_percent]],
                            columns=["timestamp", "ticker", "atr", "atr_percent"])
    
    if os.path.exists(atr_log_file):
        log_data.to_csv(atr_log_file, mode='a', header=False, index=False)
    else:
        log_data.to_csv(atr_log_file, mode='w', header=True, index=False)

def buy_coin(ticker):
    """시장가 매수"""
    order = upbit.buy_market_order(ticker, BUY_AMOUNT)
    send_message(f"✅ {ticker} 시장가 매수: {BUY_AMOUNT}원 🔥못 먹어도 고~가즈아~!!🔥🚀")
    time.sleep(120) 
    return order

def sell_coin(ticker):
    """시장가 매도"""
    balance = get_coin_balance(ticker)
    if balance > 0:
        order = upbit.sell_market_order(ticker, balance)
        send_message(f"🎯 {ticker} 📈🤑💖시장가 매도 완료! 💎🏆호박이 넝쿨 째! ✨🎉")
        return order
    return None

def get_avg_buy_price(ticker):
    """보유 코인의 평균 매수가 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['avg_buy_price'])
    return None

def get_coin_balance(ticker):
    """보유 코인 수량 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['balance'])
    return 0

def update_prices(ticker):
    """현재 가격, 평균 매수가, 보유량 업데이트"""
    current_price = pyupbit.get_current_price(ticker)
    avg_buy_price = get_avg_buy_price(ticker)
    balance = get_coin_balance(ticker)
    return current_price, avg_buy_price, balance  

while True:
    try:
        for ticker in TICKERS:  
            current_price, avg_buy_price, balance = update_prices(ticker)

            ohlcv = get_ohlcv(ticker)
            atr_value = calculate_atr(ohlcv)
            atr_percent = get_atr_percent(atr_value, current_price)
            adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)
            perc_drop = round((1 - adjusted_buy_drop) * 100, 2)
            profit_rate = (current_price / avg_buy_price - 1) * 100 if avg_buy_price else 0

            atr_trend = "🔷동일"
            if previous_atr_percent is not None:
                if atr_percent > previous_atr_percent:
                    atr_trend = "🔺증가"
                elif atr_percent < previous_atr_percent:
                    atr_trend = "🟡 감소"

            log_atr_data(ticker, atr_value, atr_percent)

            previous_atr_percent = atr_percent  

            print(f"[{ticker}] 현재 가격:{current_price}원 | 평균 매수가: {avg_buy_price}원 | ATR: {atr_value:.2f}원({atr_percent:.2f}%) {atr_trend} | 상승률: {profit_rate:.2f}% | 추가 매수 하락률: {adjusted_buy_drop:.2f}%")

            if avg_buy_price is None:
                buy_coin(ticker)
                time.sleep(60)
                continue

            if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                sell_coin(ticker)
                time.sleep(5)
                continue

            if current_price <= avg_buy_price * adjusted_buy_drop:
                buy_coin(ticker)
                send_message(f"📉 {ticker} 🌈🍀추가매수: {BUY_AMOUNT}원 쿵떡,쿵떡^^💰🐞(하락 {100 - adjusted_buy_drop * 100:.1f}%)")
                time.sleep(120)

        time.sleep(5)

    except Exception as e:
        send_message(f"⚠️ 에러 발생: {str(e)}")
        time.sleep(5)
