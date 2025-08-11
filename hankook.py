###################################################
###########                            ############
###########                            ############
###########        2025.03.19          ############
###########        불기둥 고니          ############
###########        한국투자증권         ############
###########                            ############
###################################################

import os
import time
import requests
from dotenv import load_dotenv  

# ✅ .env 파일에서 환경 변수 로드
load_dotenv()

# ✅ 한국투자증권 API 키 & 계좌 정보
APP_KEY = os.getenv("KOREA_INVEST_APP_KEY")
APP_SECRET = os.getenv("KOREA_INVEST_APP_SECRET")
ACCOUNT_NO = os.getenv("KOREA_INVEST_ACCOUNT_NO")  # 계좌번호 앞 8자리
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ✅ 매매 설정
BUY_AMOUNT = 500000  # 매수 금액 (원)
TARGET_PROFIT = 1.01  # 목표 상승률 (1% 상승 시 매도)
ADD_BUY_DROP = 0.96   # 추가 매수 하락률 (4% 하락 시 추가 매수)

# ✅ 거래할 주식 종목코드 리스트
STOCK_CODES = ["005930"]  # 삼성전자 예시

# ✅ 한국투자증권 API 기본 URL
BASE_URL = "https://openapi.koreainvestment.com:9443"

# ✅ API 인증 (Access Token 발급)
def get_access_token():
    """Access Token 발급"""
    url = f"{BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    data = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    response = requests.post(url, json=data, headers=headers)
    return response.json()["access_token"]

ACCESS_TOKEN = get_access_token()  # 최초 실행 시 토큰 발급
print("✅ 한국투자증권 API 로그인 완료")

# ✅ 디스코드 메시지 전송 함수
def send_message(msg):
    """디스코드 웹훅 메시지 전송"""
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})

# ✅ 현재가 조회 함수
def get_stock_price(code):
    """주식 현재가 조회"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010100"
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    response = requests.get(url, headers=headers, params=params)
    return int(response.json()["output"]["stck_prpr"])

# ✅ 시장가 매수 함수
def buy_stock(code):
    """시장가 매수"""
    price = get_stock_price(code)
    qty = BUY_AMOUNT // price  # 매수 수량 계산

    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
    headers = {
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "TTTC0802U"  # 시장가 매수 요청 ID
    }
    data = {
        "CANO": ACCOUNT_NO,
        "ACNT_PRDT_CD": "01",
        "PDNO": code,
        "ORD_QTY": str(qty),
        "ORD_UNPR": "0",  # 시장가 주문은 0
        "ORD_DVSN": "01",  # 시장가 주문 코드
        "CMA_EVLU_AMT_ICLD_YN": "N",
        "ORD_CHNL_DVSN": "01"
    }
    requests.post(url, json=data, headers=headers)
    send_message(f"✅ {code} 시장가 매수: {qty}주 🚀")

# ✅ 시장가 매도 함수
def sell_stock(code):
    """시장가 매도"""
    qty = get_stock_balance(code)  # 보유 수량 조회
    if qty > 0:
        url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/order-cash"
        headers = {
            "authorization": f"Bearer {ACCESS_TOKEN}",
            "appkey": APP_KEY,
            "appsecret": APP_SECRET,
            "tr_id": "TTTC0801U"  # 시장가 매도 요청 ID
        }
        data = {
            "CANO": ACCOUNT_NO,
            "ACNT_PRDT_CD": "01",
            "PDNO": code,
            "ORD_QTY": str(qty),
            "ORD_UNPR": "0",  # 시장가 주문
            "ORD_DVSN": "01",
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "ORD_CHNL_DVSN": "01"
        }
        requests.post(url, json=data, headers=headers)
        send_message(f"🎯 {code} 시장가 매도 완료! 🤑")

# ✅ 보유 주식 수량 조회 함수
def get_stock_balance(code):
    """보유 주식 수량 조회"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "VTTC8434R"
    }
    params = {"CANO": ACCOUNT_NO, "ACNT_PRDT_CD": "01"}
    response = requests.get(url, headers=headers, params=params)
    
    for stock in response.json()["output1"]:
        if stock["pdno"] == code:
            return int(stock["hldg_qty"])  # 보유 수량 반환
    return 0

# ✅ 평균 매수가 조회 함수
def get_avg_buy_price(code):
    """평균 매수가 조회"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "authorization": f"Bearer {ACCESS_TOKEN}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "VTTC8434R"
    }
    params = {"CANO": ACCOUNT_NO, "ACNT_PRDT_CD": "01"}
    response = requests.get(url, headers=headers, params=params)
    
    for stock in response.json()["output1"]:
        if stock["pdno"] == code:
            return int(stock["pchs_avg_pric"])  # 평균 매수가 반환
    return None

# ✅ 토큰 자동 갱신 함수
def refresh_access_token():
    """토큰 갱신 함수 (24시간마다 실행)"""
    global ACCESS_TOKEN  # 전역 변수로 저장
    ACCESS_TOKEN = get_access_token()  # 새 토큰 발급
    print("🔄 Access Token 갱신 완료!")

# ✅ 자동 매매 루프
start_time = time.time()  # 시작 시간 저장
while True:
    try:
        for code in STOCK_CODES:
            current_price = get_stock_price(code)
            avg_buy_price = get_avg_buy_price(code)
            balance = get_stock_balance(code)

            profit_rate = (current_price / avg_buy_price - 1) * 100 if avg_buy_price else 0
            print(f"[{code}] 현재가: {current_price}원 | 평균 매수가: {avg_buy_price}원 | 수익률: {profit_rate:.2f}%")

            if avg_buy_price is None:
                buy_stock(code)
                time.sleep(30)
                continue

            if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                sell_stock(code)
                time.sleep(1)
                continue

            if current_price <= avg_buy_price * ADD_BUY_DROP:
                buy_stock(code)
                send_message(f"📉 {code} 추가매수: {BUY_AMOUNT}원")
                time.sleep(30)

        # ✅ 24시간(86400초) 지나면 토큰 갱신
        if time.time() - start_time >= 86400:
            refresh_access_token()
            start_time = time.time()  # 시간 초기화

        time.sleep(10)

    except Exception as e:
        send_message(f"⚠️ 에러 발생: {str(e)}")
        time.sleep(10)
