import os
import sys
import time
import json
import requests
import pyupbit
import pandas as pd
from dotenv import load_dotenv

# ✅ 환경 변수 먼저 로드
load_dotenv()

# 하드코딩한 허용 계좌번호 (배포 전에 꼭 본인 계좌번호로 바꿔!)
ALLOWED_ACCOUNT_ID = "1234567890"

# 실행 시 사용자 .env에 입력된 계좌번호
CURRENT_ACCOUNT_ID = os.getenv("ACCOUNT_ID")

# 인증 검사
if not CURRENT_ACCOUNT_ID or CURRENT_ACCOUNT_ID != ALLOWED_ACCOUNT_ID:
    print("❌ 인증되지 않은 계좌입니다. 프로그램을 종료합니다.")
    input("아무 키나 누르면 종료됩니다...")
    sys.exit()

access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

if access_key and secret_key:
    upbit = pyupbit.Upbit(access_key, secret_key)
    print("✅ Upbit 객체 생성 완료")
else:
    print("⚠️ API 키가 없습니다. 확인해주세요!")
    sys.exit()

print("✅ 인증 완료! 프로그램을 실행합니다.")

# (여기에 네 나머지 자동매매 코드 계속 이어서 작성)

# ✅ 마지막 매수가 저장 파일
LAST_BUY_FILE = "last_buy_prices.json"

def get_input(prompt, default, type_func=str):
    user_input = input(f"{prompt} (기본값: {default}): ").strip()
    if not user_input:
        return default
    try:
        return type_func(user_input)
    except ValueError:
        print("⚠️ 입력값 형식이 잘못됐어요. 기본값으로 설정합니다.")
        return default

def parse_tickers_input(raw_input):
    return [s.strip().upper() for s in raw_input.split(',') if s.strip()]

def load_last_buy_prices(tickers):
    if os.path.exists(LAST_BUY_FILE):
        with open(LAST_BUY_FILE, "r") as f:
            return json.load(f)
    return {ticker: None for ticker in tickers}

def save_last_buy_prices(last_buy_prices):
    with open(LAST_BUY_FILE, "w") as f:
        json.dump(last_buy_prices, f)

def send_message(msg):
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_ohlcv(ticker, timeframe='5m', atr_period=100):
    ohlcv_data = pyupbit.get_ohlcv(ticker, interval=timeframe, count=atr_period+1)
    if ohlcv_data is None or len(ohlcv_data) < atr_period:
        raise ValueError(f"[{ticker}] 데이터 부족")
    return ohlcv_data

def calculate_atr(df, atr_period=100):
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    atr = df['TR'].rolling(window=atr_period).mean().iloc[-1]
    return atr if not pd.isna(atr) else 0

def get_atr_percent(atr, current_price):
    return (atr / current_price) * 100 if current_price > 0 else 0

def adjust_buy_drop_based_on_atr(atr_percent, base_add_buy_drop):
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

    adjusted_drop = base_add_buy_drop * scale
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

def buy_coin(ticker, buy_amount, last_buy_prices):
    order = upbit.buy_market_order(ticker, buy_amount)
    if order:
        send_message(f"✅ {ticker} 시장가 매수: {buy_amount}원 진입 완료! 🔥가즈아~!!🔥🚀")
        time.sleep(10)  # 너무 길면 줄임

        current_price = pyupbit.get_current_price(ticker)
        if current_price:
            last_buy_prices[ticker] = current_price
            save_last_buy_prices(last_buy_prices)
            print(f"[buy_coin] {ticker} 마지막 매수 가격 저장: {current_price}")
        else:
            print(f"[buy_coin] {ticker} 현재가 조회 실패, 저장 안함")
    else:
        print(f"[buy_coin] {ticker} 매수 실패")

    return order

def sell_coin(ticker, last_buy_prices):
    balance = get_coin_balance(ticker)
    if balance > 0:
        order = upbit.sell_market_order(ticker, balance)
        send_message(f"🎯 {ticker} 📈🤑💖시장가 매도 완료! 💎🏆호박이 넝쿨 째! ✨🎉")
        last_buy_prices[ticker] = None
        save_last_buy_prices(last_buy_prices)
        return order
    return None

def get_profit_info(ticker):
    current_price = pyupbit.get_current_price(ticker)   # 현재가
    avg_price = get_avg_buy_price(ticker)               # 평균 매수가
    balance = get_coin_balance(ticker)                  # 보유 수량

    if avg_price is not None and balance is not None and balance > 0:
        eval_value = current_price * balance
        buy_value = avg_price * balance
        profit = eval_value - buy_value
        profit_rate = (profit / buy_value) * 100
        return profit, profit_rate
    return 0, 0

def main():
    print("🎯 코인 자동매매 프로그램 설정")

    BUY_AMOUNT = get_input("💰 1회 매수 금액 (숫자)", 5000, int)
    TARGET_PROFIT = get_input("🎯 목표 수익률 (예: 1.01 → 1%)", 1.01, float)
    BASE_ADD_BUY_DROP = get_input("📉 추가 매수 기준 (예: 0.98 → 2% 하락시)", 0.98, float)

    tickers_input = input("📦 코인 종목 입력 (예: KRW-BTC, KRW-ETH) (기본값: KRW-ONDO, KRW-XLM): ").strip()
    TICKERS = parse_tickers_input(tickers_input) if tickers_input else ['KRW-ONDO', 'KRW-XLM']

    print("\n🛠️ 설정 완료:")
    print(f"- 매수금액: {BUY_AMOUNT}")
    print(f"- 목표수익률: {TARGET_PROFIT}")
    print(f"- 추가매수 기준: {BASE_ADD_BUY_DROP}")
    print(f"- 종목 리스트: {TICKERS}")

    last_buy_prices = load_last_buy_prices(TICKERS)

    TIMEFRAME = '5m'
    ATR_PERIOD = 100

    while True:
        try:
            balances = upbit.get_balances()
            krw_balance = 0
            for b in balances:
                if b['currency'] == 'KRW':
                    krw_balance = float(b['balance'])
                    break

            atr_data = {}

            for ticker in TICKERS:
                current_price, avg_buy_price, balance = update_prices(ticker)
                ohlcv = get_ohlcv(ticker, TIMEFRAME, ATR_PERIOD)
                atr_value = calculate_atr(ohlcv, ATR_PERIOD)
                atr_percent = get_atr_percent(atr_value, current_price)
                adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent, BASE_ADD_BUY_DROP)

                last_buy_price = last_buy_prices.get(ticker) or avg_buy_price
                threshold_price = last_buy_price * adjusted_buy_drop if last_buy_price else None
                drop_percent = round((1 - adjusted_buy_drop) * 100, 2)

                print(f"[DEBUG] {ticker} 마지막 매수가: {round(last_buy_price, 2) if last_buy_price else 'None'}, 현재가: {round(current_price, 2) if current_price else 'None'}, 조정 비율: {round(adjusted_buy_drop,4) if adjusted_buy_drop else 'None'}")

                # 평가손익 출력
                profit, profit_rate = get_profit_info(ticker)
                print(f"💰 {ticker} 평가손익: {round(profit):,}원 ({profit_rate:.2f}%)")

                # 최초 매수
                if avg_buy_price is None:
                    print(f"[INFO] {ticker} 💰💰최초 매수 진행💰💰")
                    buy_coin(ticker, BUY_AMOUNT, last_buy_prices)
                    time.sleep(10)
                    continue

                # 추가 매수 조건
                print(f"[DEBUG] {ticker} 추가매수 기준가: {round(threshold_price,2) if threshold_price else 'None'}, 현재가: {round(current_price,2) if current_price else 'None'}")
                if last_buy_price and current_price <= threshold_price:
                    print(f"[INFO] {ticker} 추가 매수 조건 충족! 진입 시도")
                    buy_coin(ticker, BUY_AMOUNT, last_buy_prices)
                    send_message(f"📉 {ticker} 💰🌈🍀추가매수 진입! 하락 {drop_percent:.2f}% 기준")
                    time.sleep(10)

                # 목표 수익률 도달 시 매도
                if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                    print(f"[INFO] {ticker} 목표 수익률 도달! 매도 진행")
                    sell_coin(ticker, last_buy_prices)
                    time.sleep(10)

            print("\n💰 [현재 보유 현황]")
            print(f"🧾 원화 잔고: {krw_balance:,.0f}원")

            total_cost = 0
            total_eval = 0

            for ticker in TICKERS:
                coin = ticker.split('-')[1]
                b = next((bal for bal in balances if bal['currency'] == coin and float(bal['balance']) > 0), None)
                if b:
                    balance = float(b['balance'])
                    avg_price = float(b['avg_buy_price'])
                    current_price = pyupbit.get_current_price(ticker)
                    if current_price is None:
                        continue

                    buy_amt = balance * avg_price
                    eval_amt = balance * current_price
                    profit = eval_amt - buy_amt
                    profit_rate = (profit / buy_amt) * 100 if buy_amt > 0 else 0

                    total_cost += buy_amt
                    total_eval += eval_amt

                    print(f"- {ticker} · 매수: {buy_amt:,.0f}원 | 평가: {eval_amt:,.0f}원 | 평가 손익: {'+' if profit > 0 else ''}{profit:,.0f}원 ({profit_rate:+.2f}%)")

            print(f"\n📌 전체 요약 · 총 매수: {total_cost:,.0f}원 | 총 평가: {total_eval:,.0f}원 | 총 손익: {'+' if (total_eval - total_cost) > 0 else ''}{(total_eval - total_cost):,.0f}원\n")

            time.sleep(5)

        except Exception as e:
            send_message(f"⚠️ 에러 발생: {str(e)}")
            time.sleep(5)

if __name__ == "__main__":
    main()
