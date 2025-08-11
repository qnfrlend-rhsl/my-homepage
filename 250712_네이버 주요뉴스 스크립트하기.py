import time
import os
import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime

# ====================== 설정 ======================
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
TRACK_KEYWORDS = ["특징주", "정부", "금리", "환율", "공매도", "물가"]
SENT_LINKS_FILE = "sent_links.txt"

NEWS_SITES = {
    "네이버": "https://finance.naver.com/news/mainnews.naver",
    "이투데이": "https://rss.etoday.co.kr/eto/etoday_news_all.xml",
    "한국경제": "https://www.hankyung.com/feed/all-news",
    "매일경제": "https://www.mk.co.kr/rss/40300001/",
    "연합뉴스": "https://www.yna.co.kr/rss/news.xml",
    "서울경제": "https://www.sedaily.com/rss/news",
    "팍스넷": "https://www.paxnet.co.kr/news/all?newsSetId=4667&objId=N4667&wlog_rpax=GNB_newsist",

    # 추가 가능
}

# ====================== 로깅 설정 ======================
logging.basicConfig(filename='news_monitor.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ====================== 전송 이력 로딩 ======================
def load_sent_links():
    try:
        with open(SENT_LINKS_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_sent_link(link):
    with open(SENT_LINKS_FILE, "a") as f:
        f.write(link + "\n")

sent_news_links = load_sent_links()

# ====================== 크롤링 함수 ======================
def get_news_naver():
    url = NEWS_SITES["네이버"]
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    news_items = soup.select(".mainNewsList > li")
    results = []
    for item in news_items:
        tag = item.select_one("a")
        if tag and tag.has_attr("href"):
            title = tag.get_text(strip=True)
            link = "https://finance.naver.com" + tag["href"]
            results.append((title, link))
    return results

def get_news_paxnet():
    url = NEWS_SITES["팍스넷"]
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    news_items = soup.select(".news_list ul li a")
    results = []
    for tag in news_items:
        title = tag.get_text(strip=True)
        link = tag["href"]
        if not link.startswith("http"):
            link = "https://www.paxnet.co.kr" + link
        results.append((title, link))
    return results

def safe_crawl(func, name):
    try:
        return func()
    except Exception as e:
        logging.error(f"[{name}] 크롤링 실패: {e}")
        return []

def get_all_news():
    news = []
    news.extend(safe_crawl(get_news_naver, "네이버"))
    news.extend(safe_crawl(get_news_paxnet, "팍스넷"))
    return news

# ====================== 필터 & 포맷 ======================
def filter_news_by_keywords(news_list, keywords):
    filtered = []
    for title, link in news_list:
        for kw in keywords:
            if kw in title:
                filtered.append((kw, title, link))
                break
    return filtered

def format_news_message(title, link):
    today = datetime.now().strftime("%Y.%m.%d")
    return f"📅 날짜: {today}\n📰 주요 뉴스: {title}\n🔗 {link}"

def format_keyword_news_message(keyword, title, link):
    today = datetime.now().strftime("%Y.%m.%d")
    template = {
        "특징주": ("🔥", "- 오늘의 특징주 관련 기사입니다.\n- 변동성 주의", "주가 단기 급등/급락 가능성"),
        "정부": ("🏛️", "- 정부 정책 또는 발표 관련 기사입니다.\n- 정책 수혜주 주목", "정책 관련 종목에 영향 예상"),
        "금리": ("💰", "- 금리 변동 관련 뉴스입니다.\n- 금융시장 영향 주목", "대출, 투자에 영향 가능성"),
        "환율": ("💱", "- 환율 변동 관련 기사입니다.\n- 수출입 기업 영향 주목", "수출입 실적 변동 가능성"),
        "공매도": ("📉", "- 공매도 관련 뉴스입니다.\n- 시장 변동성 주의", "단기 주가 변동 가능성"),
        "물가": ("📈", "- 물가 상승 및 경제 상황 뉴스입니다.\n- 소비자 물가 지수 주목", "소비심리 및 금리 영향 가능성")
    }
    emoji, core, impact = template.get(keyword, ("📌", "- 중요 뉴스입니다.", "시장 전반에 영향 가능성"))
    return (
        f"📅 날짜: {today}\n"
        f"{emoji} `{keyword}` 관련 뉴스: {title}\n"
        f"📊 핵심 내용:\n{core}\n"
        f"📈 영향 예상: {impact}\n"
        f"🔗 {link}"
    )

# ====================== 디스코드 전송 ======================
def send_to_discord(message):
    data = {"content": message}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if resp.status_code != 204:
            logging.error(f"❌ 디스코드 전송 실패: {resp.status_code} {resp.text}")
            return False
        return True
    except Exception as e:
        logging.error(f"❌ 디스코드 요청 예외: {e}")
        return False

# ====================== 메인 루프 ======================
def monitor_news(interval=60):
    print("🔍 뉴스 모니터링 시작 (CTRL+C로 종료)")
    while True:
        try:
            news_list = get_all_news()
            for title, link in news_list:
                if link not in sent_news_links:
                    msg = format_news_message(title, link)
                    if send_to_discord(msg):
                        print(f"📤 기본 뉴스 전송: {title}")
                        sent_news_links.add(link)
                        save_sent_link(link)

            keyword_news = filter_news_by_keywords(news_list, TRACK_KEYWORDS)
            for keyword, title, link in keyword_news:
                if link not in sent_news_links:
                    msg = format_keyword_news_message(keyword, title, link)
                    if send_to_discord(msg):
                        print(f"📌 키워드[{keyword}] 뉴스 전송: {title}")
                        sent_news_links.add(link)
                        save_sent_link(link)

            time.sleep(interval)
        except Exception as e:
            logging.error(f"루프 중 에러: {e}")
            time.sleep(interval)

# ====================== 실행 ======================
if __name__ == "__main__":
    try:
        monitor_news(interval=30)
    except KeyboardInterrupt:
        print("\n🛑 모니터링 종료됨")
