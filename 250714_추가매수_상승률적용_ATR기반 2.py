import os
import time
import json
import requests
import pyupbit
import pandas as pd
from dotenv import load_dotenv

# ✅ 환경 변수 로드
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

# ✅ 설정
BUY_AMOUNT = 5000
TARGET_PROFIT = 1.01
BASE_ADD_BUY_DROP = 0.98

TIMEFRAME = '1m'
ATR_PERIOD = 100

TICKERS = ['KRW-ONDO', 'KRW-XLM'] # 'KRW-XLM' 'KRW-SUI' 'KRW-ADA' 'KRW-BLAST' 'KRW-ONDO'

# ✅ 마지막 매수가 저장 파일
LAST_BUY_FILE = "last_buy_prices.json"

# ✅ 마지막 매수가 로드 & 저장 함수
def load_last_buy_prices():
    if os.path.exists(LAST_BUY_FILE):
        with open(LAST_BUY_FILE, "r") as f:
            return json.load(f)
    return {ticker: None for ticker in TICKERS}

def save_last_buy_prices():
    with open(LAST_BUY_FILE, "w") as f:
        json.dump(last_buy_prices, f)

# ✅ 전역 last_buy_prices
last_buy_prices = load_last_buy_prices()

def send_message(msg):
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_ohlcv(ticker, timeframe=TIMEFRAME):
    ohlcv_data = pyupbit.get_ohlcv(ticker, interval=timeframe, count=ATR_PERIOD+1)
    if ohlcv_data is None or len(ohlcv_data) < ATR_PERIOD:
        raise ValueError(f"[{ticker}] 데이터 부족")
    return ohlcv_data

def calculate_atr(df):
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    atr = df['TR'].rolling(window=ATR_PERIOD).mean().iloc[-1]
    return atr if not pd.isna(atr) else 0

def get_atr_percent(atr, current_price):
    return (atr / current_price) * 100 if current_price > 0 else 0

def adjust_buy_drop_based_on_atr(atr_percent):
    """ATR 변동성에 따라 추가 매수 간격 선형 조절"""
    min_atr = 3
    max_atr = 12
    min_scale = 0.98
    max_scale = 0.90

    if atr_percent <= min_atr:
        scale = min_scale
    elif atr_percent >= max_atr:
        scale = max_scale
    else:
        scale = min_scale - ((atr_percent - min_atr) / (max_atr - min_atr)) * (min_scale - max_scale)

    adjusted_drop = BASE_ADD_BUY_DROP * scale
    drop_percent = round((1 - adjusted_drop) * 100, 2)
    print(f"📊 ATR 변동성: {atr_percent:.2f}% | 스케일: {scale:.4f} | 추가 매수 기준가: {adjusted_drop:.4f}(하락률: {drop_percent}%)")
    return adjusted_drop

def get_avg_buy_price(ticker):
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['avg_buy_price'])
    return None

def get_coin_balance(ticker):
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['balance'])
    return 0

def update_prices(ticker):
    current_price = pyupbit.get_current_price(ticker)
    avg_buy_price = get_avg_buy_price(ticker)
    balance = get_coin_balance(ticker)
    return current_price, avg_buy_price, balance

def buy_coin(ticker):
    """시장가 매수 + 마지막 매수 가격 기록"""
    order = upbit.buy_market_order(ticker, BUY_AMOUNT)
    if order:
        send_message(f"✅ {ticker} 시장가 매수: {BUY_AMOUNT}원 진입 완료! 🔥가즈아~!!🔥🚀")
        time.sleep(10)  # 너무 길면 줄임

        current_price = pyupbit.get_current_price(ticker)
        if current_price:
            last_buy_prices[ticker] = current_price
            save_last_buy_prices()
            print(f"[buy_coin] {ticker} 마지막 매수 가격 저장: {current_price}")
        else:
            print(f"[buy_coin] {ticker} 현재가 조회 실패, 저장 안함")
    else:
        print(f"[buy_coin] {ticker} 매수 실패")

    return order

def sell_coin(ticker):
    balance = get_coin_balance(ticker)
    if balance > 0:
        order = upbit.sell_market_order(ticker, balance)
        send_message(f"🎯 {ticker} 📈🤑💖시장가 매도 완료! 💎🏆호박이 넝쿨 째! ✨🎉")
        last_buy_prices[ticker] = None
        save_last_buy_prices()
        return order
    return None

# ✅ 이전 ATR 저장 변수
previous_atr_percent = None
atr_log_file = "atr_log.csv"

def log_atr_data(ticker, atr_value, atr_percent):
    log_data = pd.DataFrame([[time.strftime("%Y-%m-%d %H:%M:%S"), ticker, atr_value, atr_percent]],
                            columns=["timestamp", "ticker", "atr", "atr_percent"])
    if os.path.exists(atr_log_file):
        log_data.to_csv(atr_log_file, mode='a', header=False, index=False)
    else:
        log_data.to_csv(atr_log_file, mode='w', header=True, index=False)

def get_profit_info(ticker):
    current_price = pyupbit.get_current_price(ticker)   # 현재가
    avg_price = get_avg_buy_price(ticker)               # 평균 매수가
    balance = get_coin_balance(ticker)                  # 보유 수량

    if avg_price is not None and balance is not None and balance > 0: # 코인 보유 중 계산
        eval_value = current_price * balance            # 평가금액
        buy_value = avg_price * balance                 # 매수원금
        profit = eval_value - buy_value                 # 평가손익
        profit_rate = (profit / buy_value) * 100        # 수익률 (%)
        return profit, profit_rate
    return 0, 0                                         # 코인 없거나 매수 안 했을 때

while True:
    try:
        for ticker in TICKERS:
            current_price, avg_buy_price, balance = update_prices(ticker)
            ohlcv = get_ohlcv(ticker)
            atr_value = calculate_atr(ohlcv)
            atr_percent = get_atr_percent(atr_value, current_price)
            adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)

            last_buy_price = last_buy_prices.get(ticker) or avg_buy_price
            lbp = round(last_buy_price, 2) if last_buy_price is not None else 'None'
            cp = round(current_price, 2) if current_price is not None else 'None'
            abd = round(adjusted_buy_drop, 2) if adjusted_buy_drop is not None else 'None'
            print(f"[DEBUG] {ticker} 마지막 매수가: {lbp}, 현재가: {cp}, 조정 비율: {abd}%")

            # ✅ 평가손익 출력
            profit, profit_rate = get_profit_info(ticker)
            print(f"💰 {ticker} 평가손익: {round(profit):,}원 ({profit_rate:.2f}%)")

            # 최초 매수
            if avg_buy_price is None:
                print(f"[INFO] {ticker} 💰💰최초 매수 진행💰💰")
                buy_coin(ticker)
                time.sleep(10)
                continue

            # 추가 매수 조건
            threshold_price = last_buy_price * adjusted_buy_drop
            print(f"[DEBUG] {ticker} 추가매수 기준가: {round(threshold_price,2)}, 현재가: {round(current_price,2)}")
            if last_buy_price and current_price <= threshold_price:
                print(f"[INFO] {ticker} 추가 매수 조건 충족! 진입 시도")
                buy_coin(ticker)
                send_message(f"📉 {ticker} 💰🌈🍀추가매수 진입! 하락 {100 - adjusted_buy_drop * 100:.2f}% 기준")
                time.sleep(10)

            # 목표 수익률 도달 시 매도
            if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                sell_coin(ticker)
                time.sleep(10)

        time.sleep(5)

    except Exception as e:
        send_message(f"⚠️ 에러 발생: {str(e)}")
        time.sleep(5)
