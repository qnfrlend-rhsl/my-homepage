import os
import time
import requests
import pyupbit
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

# ✅ 사용 기한 설정 (배포 시 수정)
USAGE_START_DATE = datetime(2025, 3, 16)  # 최초 실행 날짜
USAGE_LIMIT_DAYS = 0  # 사용 가능 기간 (0: 무제한, 180: 6개월, 365: 1년)

# ✅ 사용 기한 체크 함수
def check_usage_limit():
    if USAGE_LIMIT_DAYS == 0:
        return True  # 무제한 사용 가능

    expiration_date = USAGE_START_DATE + timedelta(days=USAGE_LIMIT_DAYS)
    today = datetime.today()

    if today > expiration_date:
        print(f"⛔ 사용 기한 만료! ({expiration_date.strftime('%Y-%m-%d')})")
        send_message(f"⛔ 사용 기한 만료! ({expiration_date.strftime('%Y-%m-%d')})", webhook_url)
        return False

    return True

# ✅ .env 파일에서 환경 변수 로드
load_dotenv()
# 로그 설정
logging.basicConfig(filename='bot.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')


# ✅ Upbit API 키 불러오기
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# 자동매매 관련 설정 값들
BUY_AMOUNT = float(os.getenv("BUY_AMOUNT", 5000))  # 기본값 5000
TARGET_PROFIT = float(os.getenv("TARGET_PROFIT", 1.01))  # 기본값 1.01
BASE_ADD_BUY_DROP = float(os.getenv("BASE_ADD_BUY_DROP", 0.95))  # 기본값 0.95
BASE_ADD_BUY_DROP_HIGH = float(os.getenv("BASE_ADD_BUY_DROP_HIGH", 0.90))  # 기본값 0.90
BASE_ADD_BUY_DROP_LOW = float(os.getenv("BASE_ADD_BUY_DROP_LOW", 0.97))  # 기본값 0.97
tickers_raw = os.getenv("TICKERS", "")  # .env에서 TICKERS 값을 가져옴
TICKERS = [ticker.strip() for ticker in tickers_raw.split(",") if ticker.strip()]  # 공백을 제거하고 리스트로 만들기

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

# ✅ 설정
BUY_AMOUNT = 5000  # 매수 금액
TARGET_PROFIT = 1.01  # 목표 상승률 (1.01% 은 1%라는 뜻, 현재는 0.6% 상승하면 매도)
# ✅ ATR 평상시 설정
BASE_ADD_BUY_DROP = 0.95 # 0.95%는 05%하락을 말함. 현재 ATR 5~12사이일 때 추가 매수
# ✅ ATR 급등락 설정                
BASE_ADD_BUY_DROP = 0.90  # 현재 ATR 12이상 설정됨. 변동성 급등락 때 (0.90는 10% 하락 추가 매수시 매수.)
BASE_ADD_BUY_DROP = 0.97  # 현재 ATR 05이하 설정됨. 변동성 급등락 때 (0.97는 03% 하락 추가 매수시 매수.)

# ✅ ATR 설정(캐들 갯수를 어디로 설정하느냐에 따라 변동성이 달라짐.)
TIMEFRAME = '60m'  # '1d' → 일봉, '15m' → 15분봉, '1m' → 1분봉
ATR_PERIOD = 33  # ATR 계산 기간 (캔들 갯수를 뜻함. 업비트에서는 최대 캔들 200개까지 조회 가능)

# ✅ 거래할 코인 목록
TICKERS = ['KRW-ONDO' , 'KRW-XLM']  # , 를 넣고 거래할 코인을 넣으면 됨. 'KRW-CTC' , 'KRW-XRP' 'KRW-WAVES'
                                    # 'KRW-HIVE' , 'KRW-LAYER' , 'KRW-ONDO' , 'KRW-XLM' , 'KRW-VIRTUAL'
# ✅ 1분 타임프레임으로 매매 체크 (새로 추가된 부분)
short_timeframe = '1m'

# 전역 변수로 관리할 `avg_buy_price`와 `balance`
avg_buy_price = {}  # 각 코인별 평균 매수가 저장
balance = {}  # 각 코인별 보유 수량

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
    if 12 < atr_percent < 30:
        return BASE_ADD_BUY_DROP * BASE_ADD_BUY_DROP_HIGH
    elif 1 < atr_percent < 4.99:
        return BASE_ADD_BUY_DROP * BASE_ADD_BUY_DROP_LOW
    return BASE_ADD_BUY_DROP

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
    global avg_buy_price  # 전역 변수 사용
    order = upbit.buy_market_order(ticker, BUY_AMOUNT)
    send_message(f"✅ {ticker} 시장가 매수: {BUY_AMOUNT}원 🔥못 먹어도 고~가즈아~!!🔥🚀")
    time.sleep(5)  # 매수 후 잠시 대기시간
    avg_buy_price[ticker] = get_avg_buy_price(ticker)  # 매수 후 평균 매수 가격 갱신
    return order

def sell_coin(ticker):
    """시장가 매도"""
    global balance  # 전역 변수 사용
    balance[ticker] = get_coin_balance(ticker)  # 보유 수량 갱신
    if balance[ticker] > 0:
        order = upbit.sell_market_order(ticker, balance[ticker])
        send_message(f"🎯 {ticker} 📈🤑💖시장가 매도 완료! 💎🏆호박이 넝쿨 째! ✨🎉")
        return order
    return None

def get_avg_buy_price(ticker):
    balances = upbit.get_balances()
    print("DEBUG: balances =", balances)
    for b in balances:
        if isinstance(b, dict) and 'currency' in b:
            if b['currency'] == ticker.split('-')[1]:
                return float(b['avg_buy_price'])
    return 0

def get_coin_balance(ticker):
    """보유 코인 수량 조회"""
    balances = upbit.get_balances()
    print("balances 타입:", type(balances))  # 꼭 추가
    print("balances 내용:", balances)
    if isinstance(balances, str):
        import json
        try:
            balances = json.loads(balances)
        except Exception as e:
            print("JSON 변환 실패:", e)
            return 0
    for b in balances:
        if isinstance(b, dict) and 'currency' in b:
            if b['currency'] == ticker.split('-')[1]:
                return float(b['balance'])
    return 0


def update_prices(ticker):
    """현재 가격, 평균 매수가, 보유량 업데이트"""
    current_price = pyupbit.get_current_price(ticker)
    avg_buy_price[ticker] = get_avg_buy_price(ticker)
    balance[ticker] = get_coin_balance(ticker)
    return current_price, avg_buy_price[ticker], balance[ticker]

# ✅ 자동 매매 루프
while True:
    try:
        for ticker in TICKERS:  
            current_price, avg_buy_price[ticker], balance[ticker] = update_prices(ticker)

            # ✅ ATR 계산 및 변동성 분석
            ohlcv = get_ohlcv(ticker, timeframe=short_timeframe)  # short_timeframe을 사용
            atr_value = calculate_atr(ohlcv)
            atr_percent = get_atr_percent(atr_value, current_price)
            adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)
            perc_drop = round((1 - adjusted_buy_drop) * 100, 2)
            profit_rate = (current_price / avg_buy_price[ticker] - 1) * 100 if avg_buy_price[ticker] else 0

            # ✅ ATR 변동 비교 (이전 값과 비교)
            atr_trend = "🔷동일"
            if previous_atr_percent is not None:
                if atr_percent > previous_atr_percent:
                    atr_trend = "🔺증가"
                elif atr_percent < previous_atr_percent:
                    atr_trend = "🟡 감소"

            # ✅ ATR 로그 저장
            log_atr_data(ticker, atr_value, atr_percent)

            # ✅ ATR 값 업데이트
            previous_atr_percent = atr_percent  

            print(f"[{ticker}] 현재 가격: {current_price:.2f}원 | "
                f"평균 매수가: {avg_buy_price[ticker]:.2f}원 | "
                f"ATR: {atr_value:.2f}원({atr_percent:.2f}%) "
                f"{atr_trend} | 상승률: {profit_rate:.2f}% | "
                f"추가 매수 하락률: {adjusted_buy_drop:.2f}%")

            # ✅ 최초 매수
            if avg_buy_price[ticker] == 0:  # avg_buy_price가 0이면 매수하지 않은 것으로 간주
                buy_coin(ticker)
                time.sleep(60)  # 매수 후 잠시 대기시간
                continue

            # ✅ 목표가 도달 시 매도
            if current_price >= avg_buy_price[ticker] * TARGET_PROFIT and balance[ticker] > 0:
                sell_coin(ticker)
                time.sleep(5)  # 매도 후 잠시 대기시간
                continue

            # ✅ 변동성 기반 추가 매수
            if current_price <= avg_buy_price[ticker] * adjusted_buy_drop:
                buy_coin(ticker)
                    # 매수 후 평균 매수 가격 갱신
                avg_buy_price[ticker] = get_avg_buy_price(ticker)
                    # ATR을 기반으로 하락률 재계산
                adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)

                send_message(f"📉 {ticker} 🌈🍀추가매수: {BUY_AMOUNT}원 쿵떡,쿵떡^^💰🐞(하락 {100 - adjusted_buy_drop * 100:.1f}%)")
                time.sleep(120)  # 매수 후 잠시 대기시간

        time.sleep(5)# 모든 코인 확인 후 잠시 대기

    except Exception as e:
            logging.exception("🔥 프로그램 초기화 중 오류 발생!")
    # 아래는 사용자에게도 표시되도록
    import sys
    print(f"에러 발생: {e}")
    sys.exit(1)
    send_message(f"⚠️ 에러 발생: {str(e)}")
    time.sleep(120)#에러시 잠시 대기시간