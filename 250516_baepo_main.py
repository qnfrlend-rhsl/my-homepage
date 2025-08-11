import os
import time
import json
from tkinter import Y
import pyupbit
import configparser
from datetime import datetime, timedelta
import logging
import requests
import sys
upbit = None  # 업비트 객체 (초기값 None)

#  사용 기한 설정 (배포 시 수정)
USAGE_START_DATE = datetime(2025, 5, 15)  # 최초 실행 날짜
USAGE_LIMIT_DAYS = 0  # 사용 가능 기간 (0: 무제한, 180: 6개월, 365: 1년)

#  사용 기한 체크 함수
def check_usage_limit():
    if USAGE_LIMIT_DAYS == 0:
        return True  # 무제한 사용 가능

    expiration_date = USAGE_START_DATE + timedelta(days=USAGE_LIMIT_DAYS)
    today = datetime.today()

    if today > expiration_date:
        print(f"사용 기한 만료! ({expiration_date.strftime('%Y-%m-%d')})")
        send_discord_message(f"사용 기한 만료! ({expiration_date.strftime('%Y-%m-%d')})")
        return False

    return True

#  로깅 설정
logging.basicConfig(filename='baepo_main.log', level=logging.INFO)
logging.info("프로그램 시작")

#  설정 파일 로드 함수
def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists("config.ini"):
        print(" config.ini 파일이 없습니다! 프로그램을 종료합니다.")
        exit()
    
    with open("config.ini", "r", encoding="utf-8") as f:
        config.read_file(f)
    return config

#  설정 변경 함수 (`config.ini`에 즉시 저장 + 변경된 값 반영)
def modify_global_config():
    global CONFIG  # 전역 변수 업데이트를 위해 추가
    CONFIG = load_config()

    while True:
        print("\n현재 설정 값:")
        for section in CONFIG.sections():
            for key, value in CONFIG[section].items():
                print(f"{key}: {value}")

        change = input("\n설정을 변경하시겠습니까? (y/n): ").strip().lower()
        if change != 'y':
            break

        try:
            setting_section = input("\n수정할 섹션을 입력하세요 (예: TRADE_SETTINGS): ").strip()
            setting_key = input("수정할 설정 키를 입력하세요 (예: BUY_AMOUNT): ").strip()

            if setting_section in CONFIG and setting_key in CONFIG[setting_section]:
                new_value = input(f"새로운 값 입력 ({setting_key}): ").strip()
                CONFIG[setting_section][setting_key] = new_value

                #  변경된 설정 즉시 저장
                with open("config.ini", "w") as configfile:
                    CONFIG.write(configfile)

                #  변경된 설정 다시 로드하여 반영
                CONFIG = load_config()
                
                print("\n 설정이 변경되었습니다! (config.ini 저장 완료)")
                
                #  변경된 값 확인
                print(f"\n 변경된 값 확인: {setting_key} → {new_value}")

            else:
                print("\n 입력한 섹션 또는 키가 존재하지 않습니다.")

        except Exception as e:  
            logging.error(f"설정 변경 중 오류 발생: {e}")
            print(f"\n 오류 발생: {e}, 다시 시도해주세요.")


# 전역 변수 선언 (기본값 설정)
CONFIG = None  
ACCESS_KEY = None
SECRET_KEY = None
WEBHOOK_URL = None
BUY_AMOUNT = None
TARGET_PROFIT = None
ADD_BUY_DROP = None
TICKERS = None
TIMEFRAME = '1d'  # '1d' → 일봉, '15m' → 15분봉
ATR_PERIOD = 30  # ATR 계산 기간
BASE_ADD_BUY_DROP = 0.95  # 기본 추가 매수 하락률 (5% 하락하면 추가 매수)
adjusted_buy_drop = BASE_ADD_BUY_DROP  # ATR 변동성 적용한 추가 매수 하락률


# ATR 변동성에 따른 추가 매수 조정 비율
ATR_THRESHOLD_HIGH = 12  
ATR_THRESHOLD_MID = 5  
ATR_ADJUST_HIGH = 0.90  
ATR_ADJUST_MID = 0.98  


# 디스코드 알림 보내는 함수
def send_discord_message(message):
    if WEBHOOK_URL:
        payload = {"content": message}
        try:
            requests.post(WEBHOOK_URL, json=payload)
        except Exception as e:
            print(f"디스코드 알림 실패: {e}")


# 설정 출력 및 수정 함수
def modify_global_config():
    global ACCESS_KEY, SECRET_KEY, WEBHOOK_URL, BUY_AMOUNT, TARGET_PROFIT, ADD_BUY_DROP, TICKERS
    global TIMEFRAME, ATR_PERIOD, BASE_ADD_BUY_DROP, ATR_THRESHOLD_HIGH, ATR_THRESHOLD_MID, ATR_ADJUST_HIGH, ATR_ADJUST_MID

    while True:
        print("\n현재 설정 값:")
        print(f" 1) ACCESS_KEY: {ACCESS_KEY}")
        print(f" 2) SECRET_KEY: {SECRET_KEY}")
        print(f" 3) WEBHOOK_URL: {WEBHOOK_URL}")
        print(f" 4) 매수 금액 (BUY_AMOUNT): {BUY_AMOUNT}")
        print(f" 5) 목표 수익률 (TARGET_PROFIT): {TARGET_PROFIT}")
        print(f" 6) 추가 매수 하락률 (ADD_BUY_DROP): {ADD_BUY_DROP}")
        print(f" 7) TICKERS: {TICKERS}")
        print(f" 8) TIMEFRAME: {TIMEFRAME}")
        print(f" 9) ATR_PERIOD: {ATR_PERIOD}")
        print(f"10) BASE_ADD_BUY_DROP: {BASE_ADD_BUY_DROP}")
        print(f"11) ATR_THRESHOLD_HIGH: {ATR_THRESHOLD_HIGH}")
        print(f"12) ATR_THRESHOLD_MID: {ATR_THRESHOLD_MID}")
        print(f"13) ATR_ADJUST_HIGH: {ATR_ADJUST_HIGH}")
        print(f"14) ATR_ADJUST_MID: {ATR_ADJUST_MID}")

        change = input("\n설정을 변경하시겠습니까? (y/n): ").strip().lower()
        if change != 'y':
            break

        try:
            setting_number = input("\n수정할 설정 번호를 입력하세요 (Enter: 취소): ").strip()
            if setting_number == "":
                break

            setting_value = input("새로운 값을 입력하세요: ").strip()

            if setting_number == "4":
                BUY_AMOUNT = int(setting_value)
            elif setting_number == "5":
                TARGET_PROFIT = float(setting_value)
            elif setting_number == "6":
                ADD_BUY_DROP = float(setting_value)
            elif setting_number == "7":
                TICKERS = setting_value.split(",")
            elif setting_number == "8":
                TIMEFRAME = setting_value
            elif setting_number == "9":
                ATR_PERIOD = int(setting_value)
            elif setting_number == "10":
                BASE_ADD_BUY_DROP = float(setting_value)
            elif setting_number == "11":
                ATR_THRESHOLD_HIGH = float(setting_value)
            elif setting_number == "12":
                ATR_THRESHOLD_MID = float(setting_value)
            elif setting_number == "13":
                ATR_ADJUST_HIGH = float(setting_value)
            elif setting_number == "14":
                ATR_ADJUST_MID = float(setting_value)

            print("설정이 변경되었습니다!")

        except ValueError:
            print("잘못된 입력입니다. 다시 시도해주세요.")

# OHLCV 데이터 가져오는 함수 (추가)
def get_ohlcv(ticker, timeframe=TIMEFRAME):
    """
    특정 코인의 OHLCV 데이터를 가져온다.
    :param ticker: 조회할 코인 (예: "KRW-BTC")
    :param timeframe: 조회할 캔들 주기 ('1d' → 일봉)
    :return: DataFrame (시가, 고가, 저가, 종가, 거래량)
    """
    return pyupbit.get_ohlcv(ticker, interval=timeframe, count=ATR_PERIOD+1)

# ATR 계산 함수 (추가)
def calculate_atr(df):
    """
    ATR (Average True Range) 값을 계산하는 함수.
    :param df: OHLCV 데이터 (DataFrame)
    :return: ATR 값
    """
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    return df['TR'].rolling(window=ATR_PERIOD).mean().iloc[-1]

# ATR 변동성 비율 계산 함수 (추가)
def get_atr_percent(atr, current_price):
    if atr is None or current_price is None or current_price <= 0:
        return 5  # 기본값 5%
    return (atr / current_price) * 100

# ATR 변동성에 따른 추가 매수 비율 조정 (추가)
def adjust_buy_drop_based_on_atr(atr_percent):
    global adjusted_buy_drop  # 전역 변수 사용
    if atr_percent > ATR_THRESHOLD_HIGH:
        adjusted_buy_drop = BASE_ADD_BUY_DROP * ATR_ADJUST_HIGH  
    elif atr_percent > ATR_THRESHOLD_MID:
        adjusted_buy_drop = BASE_ADD_BUY_DROP * ATR_ADJUST_MID  
    else:
        adjusted_buy_drop = BASE_ADD_BUY_DROP  
    return adjusted_buy_drop

# 매수 함수
def buy_coin(upbit, ticker, amount):
    order = upbit.buy_market_order(ticker, amount)
    print(f"{ticker} 시장가 매수: {BUY_AMOUNT}원")
    time.sleep(60)
    return order

# 매도 함수
def sell_coin(upbit, ticker):
    balance = get_coin_balance(upbit, ticker)
    if balance > 0:
        order = upbit.sell_market_order(ticker, balance)
        print(f"{ticker} 시장가 매도 완료!")
        return order
    return None

# 보유 코인 평균 매수가 조회
def get_avg_buy_price(upbit, ticker):
    base_currency = ticker.split('-')[1]
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == base_currency:
            return float(b['avg_buy_price'])
    return None

# 보유 코인 수량 조회
def get_coin_balance(upbit, ticker):
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker.split('-')[1]:
            return float(b['balance'])
    return 0

# 현재가 조회 함수 추가
def get_current_price(ticker):
    """
    주어진 티커의 현재가를 반환합니다.
    :param ticker: 조회할 코인 (예: "KRW-BTC")
    :return: 현재가 (float)
    """
    try:
        return pyupbit.get_current_price(ticker)
    except Exception as e:
        print(f"현재가 조회 실패: {e}")
        return None

# 실시간 가격 업데이트
def update_prices(ticker):
    try:
        current_price = get_current_price(ticker)
        avg_buy_price = get_avg_buy_price(upbit, ticker)
        balance = get_coin_balance(upbit, ticker)

        # 값이 `None`이면 기본값 설정
        return current_price or 0, avg_buy_price or 0, balance or 0

    except Exception as e:
        print(f" 가격 정보 업데이트 중 오류 발생: {e}")
        return 0, 0, 0  # 오류 발생 시 기본값 반환

# 자동 매매 실행
def start_trading():
    print(" 자동 매매 프로그램이 실행되었습니다.")
    print(f"TICKERS 설정 확인: {TICKERS}")  #  TICKERS 값 확인

    while True:  #  반복문을 함수 내부로 이동!
        print(" 자동 매매 로직 진행 중...")  #  실행 확인 메시지 추가
        try:
            for ticker in TICKERS:
                print(f"🚀 처리 중: {ticker}")  #  현재 매매 대상 출력

                #  변수 초기화 (None 방지)
                current_price, avg_buy_price, balance = update_prices(ticker)

                if current_price is None:
                    current_price = 0
                if avg_buy_price is None:
                    avg_buy_price = 0
                if balance is None:
                    balance = 0

                #  가격 및 ATR 변동성 계산
                ohlcv = get_ohlcv(ticker)
                if ohlcv is None:
                    print(f" {ticker}의 OHLCV 데이터를 가져오지 못했습니다.")
                    continue

                atr_value = calculate_atr(ohlcv)
                atr_percent = get_atr_percent(atr_value, current_price)
                adjusted_buy_drop = adjust_buy_drop_based_on_atr(atr_percent)

                print(f"[{ticker}] 현재 가격: {current_price}원 | 평균 매수가: {avg_buy_price}원 | ATR 변동성: {atr_percent:.2f}% | 추가 매수 하락률: {adjusted_buy_drop:.2f}%")

                #  목표가 도달하면 매도
                if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                    sell_coin(upbit, ticker)
                    print(f" {ticker} 매도 완료!")
                    continue

                #  추가 매수
                if current_price <= avg_buy_price * adjusted_buy_drop:
                    buy_coin(upbit, ticker, BUY_AMOUNT)
                    message = f"[{ticker}] 추가 매수: {BUY_AMOUNT}원 (하락 {100 - adjusted_buy_drop * 100:.1f}%)"
                    print(message)
                    time.sleep(120)

                time.sleep(5)  #  대기 시간 설정

        except Exception as e:
            print(f" 오류 발생: {e}")  #  오류 출력 후 프로그램 종료 방지
            time.sleep(5)

#  실행 여부 확인 함수
def confirm_execution():
    start = input("\n자동 매매를 시작할까요? (y/n): ").strip().lower()
    return start == 'y'

#  프로그램 실행
if __name__ == "__main__":
    print("\n자동 매매 프로그램 시작")

    CONFIG = load_config()
    if CONFIG is None:
        print(" 설정 파일(config.ini)을 불러오지 못했습니다. 프로그램을 종료합니다.")
        sys.exit()

    if confirm_execution():
        print("\n 프로그램 실행 중...\n")
        start_trading()  #  자동 매매 로직 실행!
    else:
        print("\n 프로그램을 종료합니다.")
