"""주간 크리에이티브 인사이트 브리핑 봇 (진입점).

실제 로직은 briefing 패키지에 있다. GitHub Actions가 이 파일을 실행한다.
"""

from briefing.main import run

if __name__ == "__main__":
    run()
