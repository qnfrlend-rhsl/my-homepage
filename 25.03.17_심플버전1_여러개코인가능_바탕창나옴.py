###################################################
###########                            ############
###########                            ############
###########        2025.03.12          ############
###########        불기둥 고니          ############
###########                            ############
###########                            ############
###################################################

import os
import time
import requests
import pyupbit
import threading
import tkinter as tk
from tkinter import ttk  # ttk 임포트 추가

from dotenv import load_dotenv  # .env 파일에서 API 키를 불러오기 위해 추가

#  .env 파일에서 환경 변수 로드
load_dotenv()

#  Upbit API 키 불러오기
access_key = os.getenv("UPBIT_ACCESS_KEY")
secret_key = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

#  Upbit 객체 생성
if access_key and secret_key:
    upbit = pyupbit.Upbit(access_key, secret_key)
    print(" Upbit 객체 생성 완료")
else:
    print(" API 키가 없습니다. 확인해주세요!")
    exit()

#  기본 설정
TICKERS = ['KRW-LAYER']  # 거래할 코인 리스트 'KRW-XLM' 'KRW-XRP' 'KRW-BTC' 


#  매매 설정 기본값
BUY_AMOUNT = 5010      # 매수 금액
TARGET_PROFIT = 1.01   # 목표 상승률 (1% 상승하면 매도)
ADD_BUY_DROP = 0.97   # 추가 매수 하락률 (3% 하락하면 추가 매수)

############################################################
############################################################

# Tkinter GUI 클래스
class TradingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("자동 매매 프로그램")
        self.root.geometry("400x300")

        # 상태 표시 레이블
        self.status_label = tk.Label(root, text="현재 상태: 대기 중", font=("Arial", 14))
        self.status_label.pack(pady=20)

        # 설정값 입력 프레임
        self.settings_frame = tk.Frame(root)
        self.settings_frame.pack(pady=10)

        # 매수 금액 설정
        self.buy_amount_label = tk.Label(self.settings_frame, text="매수 금액:")
        self.buy_amount_label.grid(row=0, column=0, padx=10)
        self.buy_amount_entry = tk.Entry(self.settings_frame)
        self.buy_amount_entry.grid(row=0, column=1, padx=10)
        self.buy_amount_entry.insert(0, str(BUY_AMOUNT))  # 기본값

        # 목표 수익률 설정
        self.target_profit_label = tk.Label(self.settings_frame, text="목표 수익률(%):")
        self.target_profit_label.grid(row=1, column=0, padx=10)
        self.target_profit_entry = tk.Entry(self.settings_frame)
        self.target_profit_entry.grid(row=1, column=1, padx=10)
        self.target_profit_entry.insert(0, str(TARGET_PROFIT * 100))  # 기본값

        # 추가 매수 기준 설정
        self.add_buy_drop_label = tk.Label(self.settings_frame, text="추가 매수 하락률(%):")
        self.add_buy_drop_label.grid(row=2, column=0, padx=10)
        self.add_buy_drop_entry = tk.Entry(self.settings_frame)
        self.add_buy_drop_entry.grid(row=2, column=1, padx=10)
        self.add_buy_drop_entry.insert(0, str((1 - ADD_BUY_DROP) * 100))  # 기본값

        # 실행 버튼
        self.start_button = tk.Button(root, text="자동 매매 시작", command=self.start_trading)
        self.start_button.pack(pady=20)

        # 종료 버튼
        self.stop_button = tk.Button(root, text="프로그램 종료", command=self.stop_trading)
        self.stop_button.pack(pady=5)

        # 매매 상태 플래그
        self.is_running = False

    def update_status(self, message):
        """상태 메시지 갱신"""
        self.status_label.config(text=message)

    def start_trading(self):
        """자동 매매 시작"""
        # GUI 입력값으로 설정을 업데이트
        global BUY_AMOUNT, TARGET_PROFIT, ADD_BUY_DROP

        BUY_AMOUNT = int(self.buy_amount_entry.get())
        TARGET_PROFIT = float(self.target_profit_entry.get()) / 100
        ADD_BUY_DROP = float(self.add_buy_drop_entry.get()) / 100

        # 실시간 상태 업데이트
        self.update_status("자동 매매 실행 중...")
        self.is_running = True
        self.thread = threading.Thread(target=self.run_trading_loop)
        self.thread.start()

    def run_trading_loop(self):
        """자동 매매 루프"""
        while self.is_running:
            try:
                for ticker in TICKERS:  #  여러 코인을 반복하면서 거래!
                    current_price, avg_buy_price, balance = self.update_prices(ticker)  # 한 번에 값을 가져옴!
                    profit_rate = (current_price / avg_buy_price - 1) * 100 if avg_buy_price else 0
                    print(f"[{ticker}] 현재 가격: {current_price}원 | 평균 매수가: {avg_buy_price}원 | 상승률: {profit_rate:.2f}%")

                    # 상태 업데이트
                    self.update_status(f"[{ticker}] 현재 가격: {current_price:.2f}원 | 상승률: {profit_rate:.2f}%")

                    # 최초 매수 (보유 코인 없음)
                    if avg_buy_price is None:
                        self.buy_coin(ticker)
                        time.sleep(1)
                        continue

                    # 목표가 도달 시 매도
                    if current_price >= avg_buy_price * TARGET_PROFIT and balance > 0:
                        self.sell_coin(ticker)
                        time.sleep(1)
                        continue

                    # 추가 매수 (하락 시)
                    if current_price <= avg_buy_price * ADD_BUY_DROP:
                        self.buy_coin(ticker)
                        self.send_message(f" {ticker} 추가매수: {BUY_AMOUNT}원 (하락 {100 - ADD_BUY_DROP * 100:.1f}%)")
                        time.sleep(1)

                time.sleep(10)  # 모든 코인 확인 후 잠시 대기

            except Exception as e:
                self.send_message(f" 에러 발생: {str(e)}")
                self.update_status(f"에러 발생: {str(e)}")
                time.sleep(10)

############################################################
############################################################


    def update_prices(self, ticker):
        """현재 가격, 평균 매수가, 보유량 업데이트"""
        current_price = pyupbit.get_current_price(ticker)
        avg_buy_price = self.get_avg_buy_price(ticker)
        balance = self.get_coin_balance(ticker)
        return current_price, avg_buy_price, balance

    def buy_coin(self, ticker):
        """시장가 매수"""
        order = upbit.buy_market_order(ticker, BUY_AMOUNT)
        self.send_message(f" {ticker} 시장가 매수: {BUY_AMOUNT}원 못 먹어도 고~가즈아~!!")
        time.sleep(5)
        return order

    def sell_coin(self, ticker):
        """시장가 매도"""
        balance = self.get_coin_balance(ticker)
        if balance > 0:
            order = upbit.sell_market_order(ticker, balance)
            self.send_message(f" {ticker} 시장가 매도 완료! 호박이 넝쿨 째!")
            return order
        return None

    def get_avg_buy_price(self, ticker):
        """보유 코인의 평균 매수가 조회"""
        balances = upbit.get_balances()
        for b in balances:
            if b['currency'] == ticker.split('-')[1]:
                return float(b['avg_buy_price'])
        return None

    def get_coin_balance(self, ticker):
        """보유 코인 수량 조회"""
        balances = upbit.get_balances()
        for b in balances:
            if b['currency'] == ticker.split('-')[1]:
                return float(b['balance'])
        return 0

    def send_message(self, msg):
        """디스코드 웹훅으로 메시지 전송"""
        if webhook_url:
            requests.post(webhook_url, json={"content": msg})

    def stop_trading(self):
        """자동 매매 종료"""
        self.is_running = False
        self.update_status("프로그램 종료됨")


# Tkinter 앱 실행
if __name__ == "__main__":
    root = tk.Tk()
    app = TradingApp(root)
    root.mainloop()
