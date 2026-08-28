"""네이버 금융 종목 뉴스 조회.

news_news.naver 엔드포인트는 종목 메인 페이지에서 iframe으로 삽입되는 것을
전제로 하며, 세션/Referer 없이 직접 요청하면 빈 결과("뉴스가 없습니다")를
반환한다. 따라서 종목 메인 페이지를 먼저 방문해 세션을 만든 뒤 Referer를
붙여 요청한다.
"""
from typing import List, TypedDict

import requests
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_MAIN_URL = "https://finance.naver.com/item/main.naver"
_NEWS_URL = "https://finance.naver.com/item/news_news.naver"


class NewsItem(TypedDict):
    title: str
    link: str
    source: str
    date: str


def get_stock_news(code: str, count: int = 10) -> List[NewsItem]:
    session = requests.Session()
    session.headers.update(_HEADERS)

    try:
        session.get(_MAIN_URL, params={"code": code}, timeout=5)
        res = session.get(
            _NEWS_URL,
            params={"code": code, "page": 1},
            headers={"Referer": f"{_MAIN_URL}?code={code}"},
            timeout=5,
        )
        res.encoding = "euc-kr"
    except requests.RequestException:
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    news_list: List[NewsItem] = []
    seen_links = set()
    for row in soup.select("table.type5 tr"):
        title_tag = row.select_one("td.title a")
        if not title_tag:
            continue
        href = title_tag.get("href", "")
        link = href if href.startswith("http") else f"https://finance.naver.com{href}"
        if link in seen_links:
            continue
        seen_links.add(link)

        info_tag = row.select_one("td.info")
        date_tag = row.select_one("td.date")
        news_list.append(
            {
                "title": title_tag.get_text(strip=True),
                "link": link,
                "source": info_tag.get_text(strip=True) if info_tag else "",
                "date": date_tag.get_text(strip=True) if date_tag else "",
            }
        )
        if len(news_list) >= count:
            break
    return news_list
