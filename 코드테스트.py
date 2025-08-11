import os
import time
import requests
import pyupbit
import pandas as pd
from dotenv import load_dotenv

# ✅ .env 파일에서 환경 변수 로드
load_dotenv()

# ✅ Upbit API 키 불러오기
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# ✅ Upbit 객체 생성
if access_key and secret_key:
    upbit = pyupbit.Upbit(access_key, secret_key)
    print("✅ Upbit 객체 생성 완료")
else:
    print("⚠️ API 키가 없습니다. 확인해주세요!")
    exit()

# ✅ 전역 변수 (ATR 변동성 로그 저장)
previous_atr_percent = None  
atr_log_file = "atr_log.csv"  # ATR 로그 파일

######################################################
###############🔥 설정 변경하는 곳 🔥##################
BUY_AMOUNT = 5000  # 매수 금액
TARGET_PROFIT = 1.01  # 목표 상승률 (1.01% 은 1%라는 뜻, 현재는 0.6% 상승하면 매도)
BASE_ADD_BUY_DROP = 0.95  # 기본 추가 매수 하락률 (5% 하락하면 추가 매수)

# ✅ 거래할 코인 목록
TICKERS = [ 'KRW-XLM', 'KRW-ONDO' ]  # , 를 넣고 거래할 코인을 넣으면 됨. 'KRW-XLM' ,'KRW-LAYER' , 'KRW-AUCTION'
last_buy_prices = {ticker: None for ticker in TICKERS}

# ✅ ATR 설정
TIMEFRAME = '1m'  # '1d' → 일봉, '15m' → 15분봉
ATR_PERIOD = 100  # ATR 계산 기간 
######################################################

def send_message(msg):
    """디스코드 웹훅으로 메시지 전송"""
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_ohlcv(ticker, timeframe=TIMEFRAME):
    """캔들 데이터 가져오기 (업데이트 된 함수 사용)"""
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
    
    # ATR이 nan일 경우 0으로 처리
    atr_value = df['TR'].rolling(window=ATR_PERIOD).mean().iloc[-1]
    return atr_value if not pd.isna(atr_value) else 0

def get_atr_percent(atr, current_price):
    """ATR 값을 퍼센트(%)로 변환"""
    if current_price > 0:
        return (atr / current_price) * 100
    return 0

def adjust_buy_drop_based_on_atr(atr_percent):
    """ATR 변동성에 따라 추가 매수 간격 선형 조절"""
    min_atr = 3
    max_atr = 5
    min_scale = 0.95  # 변동성 낮을 때 (추가 매수 빠르게)
    max_scale = 0.96  # 변동성 높을 때 (추가 매수 천천히)

    if atr_percent <= min_atr:
        scale = min_scale
    elif atr_percent >= max_atr:
        scale = max_scale
    else:
        # 선형 보간: atr_percent에 따라 비율 계산
        scale = min_scale - ((atr_percent - min_atr) / (max_atr - min_atr)) * (min_scale - max_scale)

    adjusted_drop = BASE_ADD_BUY_DROP * scale

    # ✅ 디버깅용 로그 출력
    print(f"📊 ATR 변동성: {atr_percent:.2f}% | 추가매수 스케일: {scale:.4f} | 하락 기준가: {adjusted_drop:.4f}")

    return adjusted_drop


def log_atr_data(ticker, atr_value, atr_percent):
    """ATR 데이터를 로그 파일에 저장"""
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
    time.sleep(120) # 매수 후 잠시 대기시간
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

# ✅ 자동 매매 루프
while True:
    try:
        for ticker in TICKERS:  
            current_price, avg_buy_price, balance = update_prices(ticker)

            # ✅ ATR 계산 및 변동성 분석
            ohlcv = get_ohlcv(ticker)
            atr_value = calculate_atr(ohlcv)
            atr_percent = get_atr_percent(atr_value, current_price)
            adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)
            perc_drop = round((1 - adjusted_buy_drop) * 100, 2)
            profit_rate = (current_price / avg_buy_price - 1) * 100 if avg_buy_price else 0

            # ✅ ATR 변동 비교
            atr_trend = "🔷동일"
            if previous_atr_percent is not None:
                if atr_percent > previous_atr_percent:
                    atr_trend = "🔺증가"
                elif atr_percent < previous_atr_percent:
                    atr_trend = "🟡 감소"

            # ✅ 로그 저장 및 업데이트
            log_atr_data(ticker, atr_value, atr_percent)
            previous_atr_percent = atr_percent  

            print(f"[{ticker}] 현재 가격:{current_price}원 | 평균 매수가: {avg_buy_price}원 | ATR: {atr_value:.2f}원({atr_percent:.2f}%) {atr_trend} | 상승률: {profit_rate:.2f}% | 추가 매수 하락률: {adjusted_buy_drop:.2f}%")

            # ✅ 최초 매수
            if avg_buy_price is None:
                buy_coin(ticker)
                last_buy_prices[ticker] = current_price  # 🔥 마지막 매수가 기록
                time.sleep(10)
                continue

            # ✅ 목표가 도달 시 매도
            if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                sell_coin(ticker)
                last_buy_prices[ticker] = None  # 🔥 매도하면 마지막 매수가 초기화
                time.sleep(10)
                continue

            # ✅ 변동성 기반 추가 매수 (🔥 last_buy_price 기준으로 변경)
            last_buy_price = last_buy_prices.get(ticker)
            if last_buy_price and current_price <= last_buy_price * adjusted_buy_drop:
                buy_coin(ticker)
                last_buy_prices[ticker] = current_price  # 🔥 새로운 기준으로 갱신
                send_message(f"📉 {ticker} 🌈🍀추가매수: {BUY_AMOUNT}원 쿵떡,쿵떡^^💰🐞(하락 {100 - adjusted_buy_drop * 100:.1f}%)")
                time.sleep(30)

        time.sleep(5)

    except Exception as e:
        send_message(f"⚠️ 에러 발생: {str(e)}")
        time.sleep(5)
