"""종목별 최근 1개월 일봉 조회 (네이버 금융 차트 API, 로그인 불필요)."""
import warnings

import pandas as pd
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CHART_URL = "https://fchart.stock.naver.com/sise.nhn"


def get_month_ohlcv(code: str, trading_days: int = 22) -> pd.DataFrame:
    """최근 약 1개월(거래일 기준) 일봉 데이터를 반환한다.

    columns: 시가, 고가, 저가, 종가, 거래량 (index: 날짜, DatetimeIndex)
    """
    params = {"symbol": code, "timeframe": "day", "count": trading_days, "requestType": 0}
    try:
        resp = requests.get(_CHART_URL, params=params, headers=_HEADERS, timeout=5)
        resp.encoding = "euc-kr"
    except requests.RequestException:
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    records = []
    for item in soup.find_all("item"):
        parts = (item.get("data") or "").split("|")
        if len(parts) != 6:
            continue
        date, o, h, l, c, v = parts
        try:
            records.append(
                {
                    "날짜": pd.to_datetime(date, format="%Y%m%d"),
                    "시가": int(o),
                    "고가": int(h),
                    "저가": int(l),
                    "종가": int(c),
                    "거래량": int(v),
                }
            )
        except ValueError:
            continue

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).set_index("날짜")
