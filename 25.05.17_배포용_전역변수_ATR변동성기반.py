import os
import time
import requests
import pyupbit
import pandas as pd
import sys  # 프로그램 종료를 위한 sys 모듈 추가
from dotenv import load_dotenv
from datetime import datetime, timedelta


# 사용 기한 설정 (배포 시 수정)
USAGE_START_DATE = datetime(2025, 3, 16)  # 최초 실행 날짜
USAGE_LIMIT_DAYS = 0  # 사용 가능 기간 (0: 무제한, 180: 6개월, 365: 1년)

# 사용 기한 체크 함수
def check_usage_limit():
    if USAGE_LIMIT_DAYS == 0:
        return True  # 무제한 사용 가능

    expiration_date = USAGE_START_DATE + timedelta(days=USAGE_LIMIT_DAYS)
    today = datetime.today()

    if today > expiration_date:
        print(f" 사용 기한 만료! ({expiration_date.strftime('%Y-%m-%d')})")
        send_message(f" 사용 기한 만료! ({expiration_date.strftime('%Y-%m-%d')})", webhook_url)
        return False

    return True

# 설정 파일 로드 함수

# API 키 입력 부분 (config.ini 체크 후 실행)
if "access_key" not in locals():
    access_key = input(" Access Key를 입력하세요: ").strip()
if "secret_key" not in locals():
    secret_key = input(" Secret Key를 입력하세요: ").strip()
if "webhook_url" not in locals():
    webhook_url = input(" Webhook URL을 입력하세요: ").strip()

print("\n 설정 확인:")
print(f"Access Key: {access_key}")
print(f"Secret Key: {secret_key}")
print(f"Webhook URL: {webhook_url}")

# Upbit 객체 생성
upbit = pyupbit.Upbit(access_key, secret_key)
print(" Upbit 객체 생성 완료!")

# 전역 변수 (ATR 변동성 로그 저장)
previous_atr_percent = None
atr_log_file = "atr_log.csv"  # ATR 로그 파일


# 예시: 환경 변수 또는 기본값에서 TICKERS를 불러오는 코드로 대체
TICKERS = ["KRW-BTC", "KRW-ETH"]  # 기본값 예시, 필요시 수정

# ✅ 사용자 입력이 있으면 덮어쓰기!
user_tickers = input("🟢 거래할 코인 목록을 입력하세요 (쉼표로 구분): ").strip()
if user_tickers:
    TICKERS = [ticker.strip() for ticker in user_tickers.split(",")]

print(f"\n✅ 최종 거래할 코인 목록: {TICKERS}")


#  매매 설정값 입력 추가
buy_amount = float(input(" 매수 금액을 입력하세요 (원): "))
target_profit = float(input(" 목표 상승률을 입력하세요 (%): "))

#  ATR 설정값 입력 추가
base_add_buy_drop = float(input(" ATR 적용 추가 매수 기준을 입력하세요 (%): ")) / 100
atr_period_12 = float(input(" ATR 적용 변동성이 높을 때 추가 매수 기준을 입력하세요 (%): ")) / 100 # ATR 90 기준
atr_period_05 = float(input(" ATR 적용 변동성이 낮을 때 추가 매수 기준을 입력하세요 (%): ")) / 100 # ATR 98 기준


#  **매매 설정값 출력**
print("\n 매매 설정값 확인")
print(f" 매수 금액: {buy_amount} 원")
print(f" 목표 상승률: {target_profit}%")
print(f" 추가 매수 기준 (ATR 적용): {base_add_buy_drop * 100:.2f}% 하락 시 추가 매수")
print(f" ATR 12 기준 추가 매수: {atr_period_12 * 100:.2f}% 하락")
print(f" ATR 05 기준 추가 매수: {atr_period_05 * 100:.2f}% 하락")

#  **최종 설정 확인**
print("\n 설정 완료! 자동 매매가 시작됩니다.")


# ATR 설정
TIMEFRAME = '1d'  # '1d' → 일봉, '15m' → 15분봉, '1m' → 1분봉
ATR_PERIOD = 33  # ATR 계산 기간 (캔들 갯수를 뜻함.)

# 1분 타임프레임으로 매매 체크 (새로 추가된 부분)
short_timeframe = '1m'

# 전역 변수로 관리할 `avg_buy_price`와 `balance`
avg_buy_price = {}  # 각 코인별 평균 매수가 저장
balance = {}  # 각 코인별 보유 수량
last_fetch_time = {}
ohlcv_cache = {}
get_ohlcv_safe = {}
######################################################

def send_message(msg):
    """디스코드 웹훅으로 메시지 전송"""
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_ohlcv_safe(ticker, timeframe=TIMEFRAME):
    now = time.time()
    if ticker in last_fetch_time and now - last_fetch_time[ticker] < 60:
        return ohlcv_cache[ticker]
    df = pyupbit.get_ohlcv(ticker, interval=timeframe, count=ATR_PERIOD+1)
    last_fetch_time[ticker] = now
    ohlcv_cache[ticker] = df
    return df

def get_ohlcv(ticker, timeframe='1d', count=34):
    """캔들 데이터 가져오기"""
    for _ in range(3):  # 3회 재시도
        try:
            df = pyupbit.get_ohlcv(ticker, interval=timeframe, count=count)
            if df is not None and len(df) >= count:
                return df
        except Exception as e:
            print(f"{ticker} OHLCV 가져오기 실패: {e}")
            time.sleep(2)
    return None

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
    """ATR 변동성에 따라 추가 매수 간격 조절"""
    if atr_percent > 12:  
        return base_add_buy_drop * 0.94   # 변동성 급등락 때 (0.9는 10% 하락 추가 매수)
    elif atr_percent < 5:  
        return base_add_buy_drop * 0.98   # 변동성 작을 때 (0.98는 2% 하락 추가 매수)
    return base_add_buy_drop    

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
    order = upbit.buy_market_order(ticker, buy_amount)
    send_message(f"{ticker} 시장가 매수: {buy_amount}원 못 먹어도 고~가즈아~!!")
    time.sleep(60)  # 매수 후 잠시 대기시간
    avg_buy_price[ticker] = get_avg_buy_price(ticker)  # 매수 후 평균 매수 가격 갱신
    return order

def sell_coin(ticker):
    """시장가 매도"""
    global balance  # 전역 변수 사용
    balance[ticker] = get_coin_balance(ticker)  # 보유 수량 갱신
    if balance[ticker] > 0:
        order = upbit.sell_market_order(ticker, balance[ticker])
        send_message(f"{ticker} 시장가 매도 완료! 호박이 넝쿨 째! ")
        return order
    return None

def get_avg_buy_price(ticker):
    """보유 코인의 평균 매수가 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['avg_buy_price'])
    return 0  # 매수하지 않은 경우 0으로 반환

def get_coin_balance(ticker):
    """보유 코인 수량 조회"""
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['balance'])
    return 0

def update_prices(ticker):
    """현재 가격, 평균 매수가, 보유량 업데이트"""
    current_price = get_safe_price(ticker)
    avg_buy_price[ticker] = get_avg_buy_price(ticker)
    balance[ticker] = get_coin_balance(ticker)
    return current_price, avg_buy_price[ticker], balance[ticker]


#  잔고 조회 함수 (오류 발생 시 자동 재시도 추가)
def request_balance(upbit):
    try:
        balance = upbit.get_balances()  # API 요청 실행
        return balance
    except Exception as e:
        print(f" 오류 발생: {e}")
        time.sleep(60)  # 5초 후 재시도
        return request_balance(upbit)  # 재시도

#  잔고 확인 실행
balance = request_balance(upbit)
if not balance:
    print(" 잔고가 없습니다!")
else:
    print("\n 보유 코인 목록:")
    for coin in balance:
        print(f"- {coin['currency']} (잔고: {coin['balance']})")

def get_safe_price(ticker):
    for _ in range(3):  # 최대 3번 재시도
        try:
            return pyupbit.get_current_price(ticker)
        except Exception:
            time.sleep(5)
    return None


#  자동 매매 루프
while True:
    try:
        print("코드가 실행되었습니다!")

        for ticker in TICKERS:
            current_price = get_safe_price(ticker)  # get_safe_price로 가격 가져오기
            avg_buy_price[ticker] = get_avg_buy_price(ticker)
            balance[ticker] = get_coin_balance(ticker)

            if current_price is None:
                send_message(f"{ticker} 현재가 조회 실패. 스킵함.")
                continue  # 가격 조회 실패하면 이 코인은 건너뛰기

            # ATR 계산 및 변동성 분석
            ohlcv = get_ohlcv(ticker, timeframe=short_timeframe)  # short_timeframe을 사용
            atr_value = calculate_atr(ohlcv)
            atr_percent = get_atr_percent(atr_value, current_price)
            adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)
            perc_drop = round((1 - adjusted_buy_drop) * 100, 2)
            profit_rate = (current_price / avg_buy_price[ticker] - 1) * 100 if avg_buy_price[ticker] else 0

            # ATR 변동 비교 (이전 값과 비교)
            atr_trend = "동일"
            if previous_atr_percent is not None:
                if atr_percent > previous_atr_percent:
                    atr_trend = "증가"
                elif atr_percent < previous_atr_percent:
                    atr_trend = "감소"

            # ATR 로그 저장
            log_atr_data(ticker, atr_value, atr_percent)

            # ATR 값 업데이트
            previous_atr_percent = atr_percent  

            print(f"[{ticker}] 현재 가격: {current_price:.2f}원 | "
                  f"평균 매수가: {avg_buy_price[ticker]:.2f}원 | "
                  f"ATR: {atr_value:.2f}원({atr_percent:.2f}%) "
                  f"{atr_trend} | 상승률: {profit_rate:.2f}% | "
                  f"추가 매수 하락률: {adjusted_buy_drop:.2f}%")

            # 최초 매수
            if avg_buy_price[ticker] == 0:  # avg_buy_price가 0이면 매수하지 않은 것으로 간주
                buy_coin(ticker)
                time.sleep(60)  # 매수 후 잠시 대기시간
                continue

            # 목표가 도달 시 매도
            if current_price >= avg_buy_price[ticker] * (1 + target_profit / 100) and balance[ticker] > 0:
                sell_coin(ticker)
                time.sleep(5)  # 매도 후 잠시 대기시간
                continue

            # 변동성 기반 추가 매수
            if current_price <= avg_buy_price[ticker] * adjusted_buy_drop:
                buy_coin(ticker)
                # 매수 후 평균 매수 가격 갱신
                avg_buy_price[ticker] = get_avg_buy_price(ticker)
                # ATR을 기반으로 하락률 재계산
                adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)

                send_message(f"{ticker} 추가매수: {buy_amount}원 쿵떡,쿵떡^^(하락 {100 - adjusted_buy_drop * 100:.1f}%)")
                time.sleep(120)  # 매수 후 잠시 대기시간

        time.sleep(5)  # 모든 코인 확인 후 잠시 대기

    except Exception as e:
        send_message(f"에러 발생: {str(e)}")
        print(f"오류 발생: {str(e)}")  # 오류 메시지를 콘솔에 출력
        time.sleep(5)  # 에러 발생 시 잠시 대기시간

    # 자동 매매 루프 종료 후 입력 대기
    input("\n프로그램이 종료되었습니다. Enter를 눌러 창을 닫으세요.")

