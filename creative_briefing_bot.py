"""
주간 크리에이티브 인사이트 브리핑 봇
매주 월요일 오전 9시 Slack으로 발송
"""

import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime, timedelta
import os

# 환경변수에서 키 읽기 (GitHub Actions Secrets에 저장)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


# ---------- 크롤링 ----------

def crawl_snipit_insight():
    """스니핏 인사이트 블로그 크롤링"""
    try:
        res = requests.get("https://snipit.im/insight/snipit-beauty-ad-trend-report-q1-2026", timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return text[:3000]
    except Exception as e:
        return f"[스니핏 크롤링 실패: {e}]"


def crawl_tiktok_creative_center():
    """TikTok Creative Center 트렌드 페이지 크롤링"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(
            "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/ko",
            headers=headers, timeout=10
        )
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return text[:3000]
    except Exception as e:
        return f"[TikTok 크롤링 실패: {e}]"


def crawl_ditoday():
    """디지털인사이트 최신 마케팅 기사 크롤링"""
    try:
        res = requests.get("https://www.ditoday.com/articles/category/marketing", timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        # 기사 제목과 요약 추출
        articles = soup.find_all(["h2", "h3", "p"], limit=30)
        text = "\n".join([a.get_text(strip=True) for a in articles if a.get_text(strip=True)])
        return text[:3000]
    except Exception as e:
        return f"[디지털인사이트 크롤링 실패: {e}]"


# ---------- AI 분석 ----------

def analyze_with_gemini(raw_texts: dict) -> str:
    """수집된 텍스트를 Gemini로 분석해서 인사이트 요약"""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    combined = ""
    for source, text in raw_texts.items():
        combined += f"\n\n[{source}]\n{text}"

    prompt = f"""
당신은 퍼포먼스 마케터를 위한 크리에이티브 인사이트 분석가입니다.
아래는 이번 주 수집된 광고 크리에이티브 관련 콘텐츠입니다.

{combined}

위 내용을 바탕으로 아래 형식으로 이번 주 크리에이티브 인사이트를 정리해주세요.

형식:
1. 이번 주 주목할 트렌드 (3가지, 각 1~2줄)
2. 주목할 후킹/카피 패턴 (2~3가지 예시 포함)
3. 포맷 트렌드 (어떤 포맷이 뜨고 있는지)
4. 우리 소재 기획에 적용할 수 있는 포인트 (1~2가지)

없는 내용은 억측하지 말고, 수집된 내용 기반으로만 작성해주세요.
한국어로 작성해주세요.
"""

    response = model.generate_content(prompt)
    return response.text


# ---------- Slack 발송 ----------

def send_to_slack(insight_text: str):
    """Slack으로 브리핑 발송"""
    today = datetime.now().strftime("%Y.%m.%d")
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%m.%d")
    week_end = (datetime.now() + timedelta(days=4 - datetime.now().weekday())).strftime("%m.%d")

    message = f"""📢 *주간 크리에이티브 인사이트 브리핑* ({week_start}~{week_end})

```
{insight_text}
```

_소스: 스니핏 인사이트 · TikTok Creative Center · 디지털인사이트_
_발송: {today}_"""

    payload = {"text": message}
    res = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)

    if res.status_code == 200:
        print("✅ Slack 발송 완료")
    else:
        print(f"❌ Slack 발송 실패: {res.status_code} {res.text}")


# ---------- 메인 ----------

def main():
    print("🔍 크롤링 시작...")

    raw_texts = {
        "스니핏 인사이트": crawl_snipit_insight(),
        "TikTok Creative Center": crawl_tiktok_creative_center(),
        "디지털인사이트": crawl_ditoday(),
    }

    print("🤖 Gemini 분석 중...")
    insight = analyze_with_gemini(raw_texts)

    print("📨 Slack 발송 중...")
    send_to_slack(insight)

    print("✅ 완료!")


if __name__ == "__main__":
    main()
