"""거래대금/등락률 기준 추천 종목 조회.

KRX(data.krx.co.kr)는 2025-12-27부터 무료 공개 API 접근을 막고 로그인 기반
'KRX 정보데이터시스템'으로 전환했다. 또한 네이버 금융도 2026-09경 상승률/거래상위
페이지를 서버 렌더링 HTML에서 클라이언트 렌더링(Next.js) 앱으로 전면 개편해,
기존의 HTML 테이블 스크래핑 방식이 더 이상 동작하지 않게 되었다.

이 모듈은 그 신규 앱이 내부적으로 호출하는 공개 JSON API
(stock.naver.com/api/domestic/market/stock/default)를 대신 사용한다. 로그인이
필요 없고, 종목당 거래대금(원 단위)·등락률·종가·거래량을 한 번의 요청으로 모두
제공하며, ETF/ETN은 애초에 이 목록에 포함되지 않아 별도 제외 처리가 필요 없다.

orderType=up 으로 조회하면 등락률이 양수인 종목만 등락률 내림차순으로 반환되므로,
거래대금/등락률 조건은 클라이언트 측에서 그대로 필터링하면 된다.
"""
import warnings
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"
_STOCK_LIST_URL = "https://stock.naver.com/api/domestic/market/stock/default"
_REFERENCE_TICKER = "005930"  # 휴장일 판단 기준 종목 (삼성전자)
_PAGE_SIZE = 3000  # 코스피+코스닥 전체 종목 수(약 2,900개)보다 여유 있게 큰 값
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


def get_recommendations(
    min_trading_value: float, min_change_pct: float, min_listed_days: int = 0
) -> pd.DataFrame:
    """가장 최근 거래일 기준, 거래대금/등락률 조건을 만족하는 종목을 조회한다.

    min_listed_days: 상장 후 최소 경과일. 신규 상장 종목은 거래 내역이 짧아 거래대금·
    등락률 조건을 쉽게 만족하지만 추천 의도와 맞지 않으므로, 기준값보다 상장일이
    최근인 종목은 제외한다. 0이면 걸러내지 않는다.
    """
    params = {
        "tradeType": "KRX",
        "marketType": "ALL",
        "orderType": "up",
        "startIdx": 0,
        "pageSize": _PAGE_SIZE,
    }
    try:
        resp = requests.get(_STOCK_LIST_URL, params=params, headers=_HEADERS, timeout=15)
        data = resp.json()
    except (requests.RequestException, ValueError):
        return pd.DataFrame(columns=_RESULT_COLUMNS)

    if not isinstance(data, list):
        return pd.DataFrame(columns=_RESULT_COLUMNS)

    today = datetime.now(_KST).date()

    records = []
    for item in data:
        try:
            change_pct = float(item["prevChangeRate"])
            trade_amount = int(item["tradeAmount"])
        except (KeyError, TypeError, ValueError):
            continue
        if change_pct < min_change_pct or trade_amount < min_trading_value:
            continue

        if min_listed_days > 0:
            listed_date = _parse_yyyymmdd(item.get("listedDate"))
            if listed_date is None or (today - listed_date).days < min_listed_days:
                continue

        try:
            price = int(item["nowPrice"])
            volume = int(item["tradeVolume"])
        except (KeyError, TypeError, ValueError):
            price, volume = 0, 0
        records.append(
            {
                "종목코드": item.get("itemcode", ""),
                "종목명": item.get("itemname", ""),
                "종가": price,
                "등락률": change_pct,
                "거래량": volume,
                "거래대금": trade_amount,
            }
        )

    if not records:
        return pd.DataFrame(columns=_RESULT_COLUMNS)

    df = pd.DataFrame(records).sort_values("등락률", ascending=False).reset_index(drop=True)
    return df[_RESULT_COLUMNS]


def _parse_yyyymmdd(value: Optional[str]):
    if not value or len(value) != 8 or not value.isdigit():
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None
