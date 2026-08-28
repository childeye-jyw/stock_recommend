# 한국 주식 급등 종목 추천

한국 주식 시장 기준으로 장이 열린 날, 거래대금과 등락률 조건을 만족하는 종목을 추천합니다.
- 데이터 출처: 네이버 금융(finance.naver.com) 공개 페이지 — 로그인/API 키 불필요
- 기본 조건: 거래대금 2,000억원 이상, 등락률 5% 이상 (UI에서 자유롭게 변경 가능)

> **왜 pykrx/KRX 공식 API가 아닌가요?**
> KRX(data.krx.co.kr)는 2025-12-27부터 비로그인 공개 API 제공을 중단하고, 로그인 기반
> '(KRX 정보데이터시스템, KRX Data Marketplace)'으로 전환했습니다. 이로 인해 `pykrx` 등
> 기존 스크래핑 라이브러리는 더 이상 로그인 없이 동작하지 않습니다. 이 프로젝트는 대신
> 로그인 없이 접근 가능한 네이버 금융의 시장별 거래대금 순위 페이지와 종목별 차트 API를
> 사용합니다. 다만 이 페이지는 "가장 최근 거래일(마감 후에는 당일, 장중에는 실시간)" 기준
> 데이터만 제공하며 임의의 과거 날짜를 조회할 수는 없습니다 — 매일 마감 후 최신 추천을
> 확인하는 이 프로그램의 용도에는 문제가 없습니다.

## 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 1. UI 실행 (수동 조회 / 설정)

```bash
streamlit run app.py
```

브라우저가 열리면:
- 왼쪽 사이드바에서 최소 거래대금(억원 단위), 최소 등락률을 조정하고 "설정 저장"을 누르세요.
- "최신 데이터 조회"를 누르면 가장 최근 거래일 기준으로 조건에 맞는 종목 목록이 표시됩니다.
- 종목을 선택하면 최근 1개월 일봉 차트와 관련 뉴스를 볼 수 있습니다.

## 2. 텔레그램 알림 설정

1. 텔레그램에서 [@BotFather](https://t.me/BotFather) 와 대화를 시작해 `/newbot` 으로 봇을 생성하고, 발급받은 **봇 토큰**을 복사합니다.
2. 생성한 봇과 대화를 한 번 시작합니다(아무 메시지나 전송).
3. 브라우저에서 `https://api.telegram.org/bot<봇토큰>/getUpdates` 에 접속해 `chat.id` 값을 확인합니다. (또는 [@userinfobot](https://t.me/userinfobot) 사용)
4. Streamlit UI 사이드바의 "텔레그램 알림" 섹션에 봇 토큰과 Chat ID를 입력하고, "텔레그램 알림 사용"을 체크한 뒤 저장합니다.
5. "텔레그램 테스트 메시지 전송" 버튼으로 정상 동작을 확인하세요.

설정은 `settings.json` 파일에 저장되며, UI와 아래 스케줄러가 이 파일을 공유합니다.

## 3. 매일 22:00 자동 실행 (스케줄러)

장이 열린 날 22:00(KST)에 자동으로 조건을 확인하고, 추천 종목이 있으면 텔레그램으로 전송합니다.

```bash
python scheduler.py
```

이 스크립트는 터미널을 켜둔 채 상시 실행되어야 합니다. 컴퓨터를 항상 켜두고 자동 실행하려면:
- macOS: `launchd` 등록 (plist로 로그인 시 자동 시작 + 재시작 설정)
- 또는 `nohup python scheduler.py &` 로 백그라운드 실행
- 또는 상시 켜져 있는 서버/NAS에 배포
- 또는 아래 4번의 GitHub Actions 사용 (컴퓨터를 켜둘 필요 없음)

## 4. 컴퓨터 없이 자동 실행 (GitHub Actions, 무료)

`scheduler.py --once`를 매 평일 22:00(KST)에 1회 실행하고 종료하는 GitHub Actions
워크플로(`.github/workflows/daily.yml`)가 포함되어 있습니다. 컴퓨터를 켜둘 필요가 없습니다.

1. GitHub에 새 저장소를 만들고 이 프로젝트를 push 합니다.
   ```bash
   git remote add origin https://github.com/<사용자명>/<저장소명>.git
   git branch -M main
   git push -u origin main
   ```
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 등록합니다. (`settings.json`은 git에 포함되지
   않으므로, CI에서는 이 두 값을 환경변수로 주입받습니다.)
3. 거래대금/등락률 기본값을 바꾸고 싶다면 같은 화면의 **Variables** 탭에서
   `MIN_TRADING_VALUE`(원 단위), `MIN_CHANGE_PCT`를 선택적으로 추가합니다. 설정하지 않으면
   기본값(2,000억원/5%)을 사용합니다.
4. 저장소 **Actions** 탭 → `Daily Stock Recommendation` → **Run workflow**로 즉시 수동
   실행해 정상 동작을 확인할 수 있습니다.

> Public 저장소는 Actions 실행 시간이 무제한 무료이고, Private 저장소도 매달 2,000분
> 무료(이 작업은 1회 실행에 1분 내외)로 충분합니다. 단, 60일 이상 저장소에 커밋이 없으면
> GitHub가 예약 실행을 자동 정지시키니, 그 경우 Actions 탭에서 다시 활성화해야 합니다.
> 이 방식은 텔레그램 알림만 자동화하며, Streamlit UI(설정 화면)는 필요할 때 로컬에서
> `streamlit run app.py`로 실행합니다.

## 파일 구조

```
app.py                        # Streamlit UI (수동 조회, 설정, 차트/뉴스)
scheduler.py                  # 22:00 자동 실행(상시) / --once (1회 실행, CI용) + 텔레그램 알림
config.py                     # 설정 로드/저장 (settings.json 또는 환경변수)
settings.json                 # 사용자 설정 (거래대금/등락률 임계값, 텔레그램 정보) — git에는 포함되지 않음
settings.example.json         # settings.json 예시 템플릿
.github/workflows/daily.yml   # GitHub Actions로 매일 22:00 자동 실행하는 워크플로
core/market.py                # 추천 종목 조회 및 필터링 (네이버 금융 기반)
core/chart.py                 # 종목별 1개월 일봉 조회
core/news.py                  # 네이버 금융 종목 뉴스 조회
core/telegram.py              # 텔레그램 메시지 전송
core/message.py      # 추천 메시지 포맷팅
```

## 참고

- `등락률`, `거래대금`은 당일 확정 데이터이므로, 장 마감(15:30) 이후 조회해야 정확합니다. 22:00 스케줄은 이 시점 이후로 데이터가 안정적으로 집계된 뒤 실행되도록 설정되어 있습니다.
- 뉴스는 네이버 금융 페이지를 파싱하여 가져오므로, 네이버 페이지 구조가 변경되면 `core/news.py` 수정이 필요할 수 있습니다.
