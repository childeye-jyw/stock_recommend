"""거래대금/등락률 기준 추천 종목 조회.

KRX(data.krx.co.kr)는 2025-12-27부터 무료 공개 API 접근을 막고 로그인 기반
'KRX 정보데이터시스템'으로 전환했다. 이 모듈은 로그인 없이 접근 가능한
네이버 금융의 등락률 순위 페이지 + 실시간 시세 API를 조합해 동일한 정보를 얻는다.

절차:
  1. 시장별(KOSPI/KOSDAQ) 등락률 상위 페이지(내림차순, 페이지네이션 없음)에서
     등락률 조건을 만족하는 후보 종목을 뽑는다. (ETF/ETN 제외)
  2. 후보 종목들의 정확한 거래대금/거래량/종가를 실시간 시세 API로 일괄 조회한다.
  3. 거래대금 조건까지 만족하는 종목만 남긴다.
"""
import re
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_RISE_URL = "https://finance.naver.com/sise/sise_rise.naver"
_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
_QUOTE_URL = "https://polling.finance.naver.com/api/realtime/domestic/stock/{codes}"
_MARKETS = (0, 1)  # 0: KOSPI, 1: KOSDAQ
_REFERENCE_TICKER = "005930"  # 휴장일 판단 기준 종목 (삼성전자)
_QUOTE_BATCH_SIZE = 80
_KST = ZoneInfo("Asia/Seoul")

_RESULT_COLUMNS = ["종목코드", "종목명", "종가", "등락률", "거래량", "거래대금"]


def today_str() -> str:
    """실행 환경의 로컬 시간대와 무관하게 한국 시간(KST) 기준 오늘 날짜를 반환한다."""
    return datetime.now(_KST).strftime("%Y%m%d")


def yesterday_str() -> str:
    """한국 시간(KST) 기준 어제 날짜.

    GitHub Actions의 schedule 트리거는 정각 부하로 인해 자정을 넘겨 지연 실행되는
    경우가 잦다. 이 경우 실행 시점의 '오늘'은 이미 다음 날로 넘어갔지만, 아직 새 거래일
    장이 열리기 전이라 최근 거래일은 여전히 어제로 조회된다. is_recent_trading_day()가
    이런 지연 실행에서도 놓치지 않도록 오늘/어제 범위를 함께 확인하는 데 사용한다.
    """
    return (datetime.now(_KST) - timedelta(days=1)).strftime("%Y%m%d")


def get_latest_session_date() -> Optional[str]:
    """가장 최근 거래일(YYYYMMDD)을 기준 종목의 최신 일봉 날짜로 조회한다."""
    params = {"symbol": _REFERENCE_TICKER, "timeframe": "day", "count": 1, "requestType": 0}
    try:
        resp = requests.get(_CHART_URL, params=params, headers=_HEADERS, timeout=5)
        resp.encoding = "euc-kr"
    except requests.RequestException:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    item = soup.find("item")
    if not item or not item.get("data"):
        return None
    return item["data"].split("|")[0]


def is_trading_day(date_str: str) -> bool:
    """해당 날짜가 가장 최근 거래일과 일치하는지 여부."""
    return get_latest_session_date() == date_str


def is_recent_trading_day(latest_session: Optional[str]) -> bool:
    """조회된 최근 거래일이 '오늘' 또는 '어제'(KST)에 해당하는지 여부.

    예약 실행이 지연되어 자정을 넘긴 뒤 실행되더라도, 그 직전 거래일 데이터를
    놓치지 않고 보고할 수 있도록 하루의 여유를 둔다.
    """
    return latest_session is not None and latest_session in (today_str(), yesterday_str())


def _get_etf_etn_codes() -> Set[str]:
    """ETF/ETN 종목코드 목록 (추천 대상에서 제외하기 위함)."""
    codes: Set[str] = set()
    sources = [
        ("https://finance.naver.com/api/sise/etfItemList.naver", "etfItemList"),
        ("https://finance.naver.com/api/sise/etnItemList.naver", "etnItemList"),
    ]
    for url, key in sources:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=5)
            resp.encoding = "euc-kr"
            data = resp.json()
            for item in data.get("result", {}).get(key, []):
                code = item.get("itemcode")
                if code:
                    codes.add(code)
        except (requests.RequestException, ValueError, KeyError):
            continue
    return codes


def _parse_rise_page(sosok: int, min_change_pct: float) -> List[Dict]:
    """등락률 내림차순 상승 종목 목록에서 min_change_pct 이상인 종목만 추출한다.

    이 페이지는 (확인 결과) 페이지네이션 없이 조건에 맞는 전체 종목을 한 번에 반환하며,
    등락률 기준 내림차순으로 정렬되어 있다.
    """
    resp = requests.get(_RISE_URL, params={"sosok": sosok}, headers=_HEADERS, timeout=10)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    rows: List[Dict] = []
    for tr in soup.select("table.type_2 tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue
        link = tds[1].find("a")
        if not link or "code=" not in link.get("href", ""):
            continue
        try:
            change_pct = float(tds[4].get_text(strip=True).replace("%", "").replace("+", ""))
        except ValueError:
            continue
        if change_pct < min_change_pct:
            continue
        code = link["href"].split("code=")[-1]
        rows.append(
            {
                "종목코드": code,
                "종목명": tds[1].get_text(strip=True),
                "등락률": change_pct,
            }
        )
    return rows


def _parse_won_amount(text: str) -> int:
    """'3조 8,198억' / '2,529억' / '-' 형태의 문자열을 원 단위 정수로 변환한다."""
    if not text:
        return 0
    text = text.strip()
    if text in ("", "-"):
        return 0

    total = 0
    m = re.search(r"([\d,]+)\s*조", text)
    if m:
        total += int(m.group(1).replace(",", "")) * 1_000_000_000_000
    m = re.search(r"([\d,]+)\s*억", text)
    if m:
        total += int(m.group(1).replace(",", "")) * 100_000_000

    if "조" not in text and "억" not in text:
        cleaned = text.replace(",", "")
        if cleaned.lstrip("-").isdigit():
            total = int(cleaned)

    return total


def _fetch_quote_details(codes: List[str]) -> Dict[str, Dict]:
    """종목코드 목록에 대해 정확한 종가/거래량/거래대금 정보를 일괄 조회한다."""
    details: Dict[str, Dict] = {}
    for i in range(0, len(codes), _QUOTE_BATCH_SIZE):
        batch = codes[i : i + _QUOTE_BATCH_SIZE]
        url = _QUOTE_URL.format(codes=",".join(batch))
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue

        for item in data.get("datas", []):
            code = item.get("itemCode")
            if not code:
                continue
            try:
                price = int(str(item.get("closePrice", "0")).replace(",", ""))
            except ValueError:
                price = 0
            try:
                volume = int(str(item.get("accumulatedTradingVolume", "0")).replace(",", ""))
            except ValueError:
                volume = 0
            details[code] = {
                "종가": price,
                "거래량": volume,
                "거래대금": _parse_won_amount(item.get("accumulatedTradingValue", "")),
            }
        time.sleep(0.1)
    return details


def get_recommendations(min_trading_value: float, min_change_pct: float) -> pd.DataFrame:
    """가장 최근 거래일 기준, 거래대금/등락률 조건을 만족하는 종목(ETF/ETN 제외)을 조회한다."""
    exclude_codes = _get_etf_etn_codes()

    candidates: Dict[str, Dict] = {}
    for sosok in _MARKETS:
        for row in _parse_rise_page(sosok, min_change_pct):
            if row["종목코드"] not in exclude_codes:
                candidates[row["종목코드"]] = row

    if not candidates:
        return pd.DataFrame(columns=_RESULT_COLUMNS)

    details = _fetch_quote_details(list(candidates.keys()))

    records = []
    for code, row in candidates.items():
        detail = details.get(code)
        if not detail or detail["거래대금"] < min_trading_value:
            continue
        records.append({**row, **detail})

    if not records:
        return pd.DataFrame(columns=_RESULT_COLUMNS)

    df = pd.DataFrame(records)
    df = df.sort_values("등락률", ascending=False).reset_index(drop=True)
    return df[_RESULT_COLUMNS]
