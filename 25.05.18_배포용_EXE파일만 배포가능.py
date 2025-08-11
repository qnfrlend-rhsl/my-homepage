import os
import time
import requests
import pyupbit
import pandas as pd
from datetime import datetime, timedelta
import sys

# 사용 기한 설정
USAGE_START_DATE = datetime(2025, 3, 16)
USAGE_LIMIT_DAYS = 0  # 0이면 무제한

# 웹훅 메시지 전송 함수
def send_message(msg):
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

# 사용기한 체크
def check_usage_limit():
    if USAGE_LIMIT_DAYS == 0:
        return True
    expiration_date = USAGE_START_DATE + timedelta(days=USAGE_LIMIT_DAYS)
    if datetime.today() > expiration_date:
        send_message(f"사용 기한 만료됨! ({expiration_date.strftime('%Y-%m-%d')})")
        return False
    return True

# API 키 입력
access_key = input("Access Key: ").strip()
secret_key = input("Secret Key: ").strip()
webhook_url = input("Webhook URL: ").strip()

if not check_usage_limit():
    print("사용 기한이 만료되었습니다.")
    sys.exit()

# 거래 대상 코인 설정
TICKERS = ["KRW-BTC", "KRW-ETH"]
user_input = input(" 거래할 코인 목록 입력 (예: KRW-BTC, KRW-ETH): ").strip()
if user_input:
    TICKERS = [t.strip() for t in user_input.split(",")]

# 매매 설정값
buy_amount = float(input("매수 금액 (원): "))
target_profit = float(input("목표 수익률 (%): "))
base_add_buy_drop = float(input("기본 하락률 기준 (%): ")) / 100
atr_period_12 = float(input("높은 변동성 추가 매수 기준 (%): ")) / 100
atr_period_05 = float(input("낮은 변동성 추가 매수 기준 (%): ")) / 100

# 로그 경로
atr_log_file = "atr_log.csv"
TIMEFRAME = "15m"
ATR_PERIOD = 33

# Upbit 객체 생성
upbit = pyupbit.Upbit(access_key, secret_key)
avg_buy_price = {}
balance = {}
previous_atr_percent = {}

# 보조 함수들
def send_message(msg):
    """디스코드 웹훅으로 메시지 전송"""
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_ohlcv(ticker):
    df = pyupbit.get_ohlcv(ticker, interval=TIMEFRAME, count=ATR_PERIOD+1)
    if df is None or len(df) < ATR_PERIOD:
        raise ValueError(f"{ticker} 캔들 데이터 부족")
    return df

def calculate_atr(df):
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    return df['TR'].rolling(window=ATR_PERIOD).mean().iloc[-1]

def get_atr_percent(atr, price):
    return (atr / price) * 100 if price > 0 else 0

def adjust_buy_drop_based_on_atr(atr_percent):
    if atr_percent > 12:
        return base_add_buy_drop * 0.94
    elif atr_percent < 5:
        return base_add_buy_drop * 0.98
    return base_add_buy_drop

def log_atr_data(ticker, atr, atr_percent):
    row = pd.DataFrame([[time.strftime("%Y-%m-%d %H:%M:%S"), ticker, atr, atr_percent]],
                       columns=["timestamp", "ticker", "atr", "atr_percent"])
    row.to_csv(atr_log_file, mode='a', header=not os.path.exists(atr_log_file), index=False)

def get_avg_buy_price(ticker):
    for b in upbit.get_balances():
        if b['currency'] == ticker.split('-')[1]:
            return float(b.get('avg_buy_price', 0))
    return 0

def get_coin_balance(ticker):
    for b in upbit.get_balances():
        if b['currency'] == ticker.split('-')[1]:
            return float(b.get('balance', 0))
    return 0

def update_prices(ticker):
    price = pyupbit.get_current_price(ticker)
    avg = get_avg_buy_price(ticker)
    bal = get_coin_balance(ticker)
    avg_buy_price[ticker] = avg
    balance[ticker] = bal
    return price, avg, bal

def buy_coin(ticker):
    upbit.buy_market_order(ticker, buy_amount)
    send_message(f"{ticker} 매수: {buy_amount}원 매수 완료!")
    time.sleep(60)

def sell_coin(ticker):
    bal = get_coin_balance(ticker)
    if bal > 0:
        upbit.sell_market_order(ticker, bal)
        send_message(f"{ticker} 매도 완료!")
        time.sleep(5)

# 자동매매 루프 시작
print("\n🚀 자동매매 시작! 종료하려면 Ctrl+C")

while True:
    try:
        prices = pyupbit.get_current_price(TICKERS)
        for ticker in TICKERS:
            price, avg, bal = update_prices(ticker)
            if price is None or price == 0:
                continue

            df = get_ohlcv(ticker)
            atr = calculate_atr(df)
            atr_percent = get_atr_percent(atr, price)
            adjusted_drop = adjust_buy_drop_based_on_atr(atr_percent)
            profit_rate = (price / avg - 1) * 100 if avg > 0 else 0

            log_atr_data(ticker, atr, atr_percent)

            print(f"[{ticker}] 현재가: {price:.0f}원 | 평균가: {avg:.0f} | 수익률: {profit_rate:.2f}%")

            # ✅ 최초 매수
            if avg == 0:
                buy_coin(ticker)
                avg_buy_price[ticker] = get_avg_buy_price(ticker)
                time.sleep(60)
                continue

            # ✅ 목표 수익률 도달 시 매도
            if price >= avg * (1 + target_profit / 100) and bal > 0:
                sell_coin(ticker)
                time.sleep(5)
                continue

            # ✅ ATR 기반 추가 매수
            if price <= avg * adjusted_drop:
                buy_coin(ticker)
                avg_buy_price[ticker] = get_avg_buy_price(ticker)
                send_message(f"{ticker} 추가매수: {buy_amount}원 (하락 {100 - adjusted_drop * 100:.1f}%)")
                time.sleep(120)

        time.sleep(5)

    except Exception as e:
        send_message(f"⚠️ 에러 발생: {str(e)}")
        print(f"에러 발생: {e}")
        time.sleep(5)
    # 자동 매매 루프 종료 후 입력 대기
    input("\n프로그램이 종료되었습니다. Enter를 눌러 창을 닫으세요.")