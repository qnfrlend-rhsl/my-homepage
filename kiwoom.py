###################################################
###########                            ############
###########                            ############
###########        2025.03.19          ############
###########        불기둥 고니          ############
###########        키 움 증 권          ############
###########                            ############
###################################################

import os
import time
import requests
from dotenv import load_dotenv  
from pykiwoom.kiwoom import Kiwoom  # ✅ 키움증권 API

# ✅ .env 파일에서 환경 변수 로드
load_dotenv()

# ✅ 키움증권 로그인
kiwoom = Kiwoom()
kiwoom.CommConnect(block=True)  # 로그인 요청 (대기)

print("✅ 키움증권 로그인 완료")

# ✅ 환경 변수에서 웹훅 URL 불러오기
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# ✅ 매매 설정
BUY_AMOUNT = 500000  # 매수 금액 (원)
TARGET_PROFIT = 1.01  # 목표 상승률 (1% 상승 시 매도)
ADD_BUY_DROP = 0.96   # 추가 매수 하락률 (4% 하락 시 추가 매수)

# ✅ **거래할 주식 종목코드 리스트**
STOCK_CODES = ["005930"]  # 삼성전자 예시 (종목코드 추가 가능)

def send_message(msg):
    """디스코드 웹훅으로 메시지 전송"""
    if webhook_url:
        requests.post(webhook_url, json={"content": msg})

def get_stock_price(code):
    """현재가 조회"""
    price = kiwoom.GetMasterLastPrice(code)
    return int(price.replace(",", ""))  # 쉼표 제거 후 정수 변환

def buy_stock(code):
    """시장가 매수"""
    qty = BUY_AMOUNT // get_stock_price(code)  # 매수 수량 계산
    kiwoom.SendOrder("시장가매수", "0101", kiwoom.GetLoginInfo("ACCNO")[0], 1, code, qty, 0, "03", "")
    send_message(f"✅ {code} 시장가 매수: {qty}주 🚀")
    time.sleep(5)

def sell_stock(code):
    """시장가 매도"""
    qty = get_stock_balance(code)
    if qty > 0:
        kiwoom.SendOrder("시장가매도", "0101", kiwoom.GetLoginInfo("ACCNO")[0], 2, code, qty, 0, "03", "")
        send_message(f"🎯 {code} 시장가 매도 완료! 🤑")
    return None

def get_stock_balance(code):
    """보유 주식 수량 조회"""
    account = kiwoom.GetLoginInfo("ACCNO")[0]  
    kiwoom.SetInputValue("계좌번호", account)
    kiwoom.SetInputValue("비밀번호", "0000")  
    kiwoom.SetInputValue("상장폐지조회구분", "0")
    kiwoom.SetInputValue("비밀번호입력매체구분", "00")
    kiwoom.CommRqData("계좌평가잔고내역요청", "opw00018", 0, "2000")

    time.sleep(0.5)  # 데이터 요청 후 대기
    data = kiwoom.tr_data  
    for stock in data:
        if stock['종목코드'] == code:
            return int(stock['보유수량'].replace(",", ""))
    return 0

def get_avg_buy_price(code):
    """평균 매수가 조회"""
    account = kiwoom.GetLoginInfo("ACCNO")[0]
    kiwoom.SetInputValue("계좌번호", account)
    kiwoom.SetInputValue("비밀번호", "0000")
    kiwoom.SetInputValue("상장폐지조회구분", "0")
    kiwoom.SetInputValue("비밀번호입력매체구분", "00")
    kiwoom.CommRqData("계좌평가잔고내역요청", "opw00018", 0, "2000")

    time.sleep(0.5)  
    data = kiwoom.tr_data  
    for stock in data:
        if stock['종목코드'] == code:
            return int(stock['평균단가'].replace(",", ""))
    return None

# ✅ 자동 매매 루프
while True:
    try:
        for code in STOCK_CODES:
            current_price = get_stock_price(code)
            avg_buy_price = get_avg_buy_price(code)
            balance = get_stock_balance(code)

            profit_rate = (current_price / avg_buy_price - 1) * 100 if avg_buy_price else 0
            print(f"[{code}] 현재가: {current_price}원 | 평균 매수가: {avg_buy_price}원 | 수익률: {profit_rate:.2f}%")

            # 신규 매수 (보유량 없음)
            if avg_buy_price is None:
                buy_stock(code)
                time.sleep(30)
                continue

            # 목표가 도달 시 매도
            if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                sell_stock(code)
                time.sleep(1)
                continue

            # 추가 매수 (하락 시)
            if current_price <= avg_buy_price * ADD_BUY_DROP:
                buy_stock(code)
                send_message(f"📉 {code} 추가매수: {BUY_AMOUNT}원 (하락 {100 - ADD_BUY_DROP * 100:.1f}%)")
                time.sleep(30)

        time.sleep(10)  # 모든 종목 확인 후 대기

    except Exception as e:
        send_message(f"⚠️ 에러 발생: {str(e)}")
        time.sleep(10)
