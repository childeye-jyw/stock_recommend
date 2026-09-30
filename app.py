"""한국 주식 급등 종목 추천 - Streamlit UI."""
import plotly.graph_objects as go
import streamlit as st

from config import load_settings, save_settings
from core.chart import get_month_ohlcv
from core.market import get_latest_session_date, get_recommendations
from core.message import format_recommendation_message
from core.news import get_stock_news
from core.telegram import TelegramError, send_telegram_message

st.set_page_config(page_title="한국 주식 급등 종목 추천", layout="wide")

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

settings = st.session_state.settings

# ---------------- Sidebar: 설정 ----------------
with st.sidebar:
    st.header("⚙️ 추천 조건 설정")

    min_trading_value_eok = st.number_input(
        "최소 거래대금 (억원)",
        min_value=0,
        value=int(settings["min_trading_value"] // 100_000_000),
        step=100,
        help="당일 총 거래대금이 이 값 이상인 종목만 추천합니다.",
    )
    min_change_pct = st.number_input(
        "최소 등락률 (%)",
        min_value=0.0,
        value=float(settings["min_change_pct"]),
        step=0.5,
        help="당일 등락률이 이 값 이상인 종목만 추천합니다.",
    )
    min_listed_days = st.number_input(
        "최소 상장 경과일 (일)",
        min_value=0,
        value=int(settings.get("min_listed_days", 30)),
        step=5,
        help="상장한 지 이 일수 미만인 신규 상장 종목은 추천에서 제외합니다. 0이면 제외하지 않습니다.",
    )

    st.divider()
    st.header("📨 텔레그램 알림")
    telegram_enabled = st.checkbox("텔레그램 알림 사용", value=bool(settings.get("telegram_enabled", False)))
    telegram_bot_token = st.text_input(
        "봇 토큰", value=settings.get("telegram_bot_token", ""), type="password"
    )
    telegram_chat_id = st.text_input("Chat ID", value=settings.get("telegram_chat_id", ""))

    if st.button("💾 설정 저장", use_container_width=True):
        new_settings = {
            "min_trading_value": int(min_trading_value_eok) * 100_000_000,
            "min_change_pct": float(min_change_pct),
            "min_listed_days": int(min_listed_days),
            "telegram_enabled": telegram_enabled,
            "telegram_bot_token": telegram_bot_token,
            "telegram_chat_id": telegram_chat_id,
        }
        save_settings(new_settings)
        st.session_state.settings = new_settings
        st.success("설정을 저장했습니다.")

    if st.button("🔔 텔레그램 테스트 메시지 전송", use_container_width=True):
        try:
            send_telegram_message(telegram_bot_token, telegram_chat_id, "✅ 테스트 메시지입니다.")
            st.success("전송 완료!")
        except TelegramError as e:
            st.error(str(e))

# ---------------- Main ----------------
st.title("📊 한국 주식 급등 종목 추천")
st.caption("거래대금 및 등락률 조건을 만족하는 종목을 조회합니다. (데이터: 네이버 금융, 최근 거래일 기준)")

col1, col2 = st.columns([1, 3])
with col1:
    fetch = st.button("🔍 최신 데이터 조회", type="primary", use_container_width=True)

if fetch or "last_df" not in st.session_state:
    with st.spinner("데이터를 조회 중입니다..."):
        latest_date = get_latest_session_date()
        if not latest_date:
            st.session_state.last_df = None
            st.error("시세 데이터를 가져오지 못했습니다. 잠시 후 다시 시도하세요.")
        else:
            df = get_recommendations(
                min_trading_value=int(settings["min_trading_value"]),
                min_change_pct=float(settings["min_change_pct"]),
                min_listed_days=int(settings.get("min_listed_days", 0)),
            )
            st.session_state.last_df = df
            st.session_state.last_date = latest_date

if st.session_state.get("last_date"):
    st.caption(f"기준 거래일: {st.session_state['last_date']}")

df = st.session_state.get("last_df")

if df is not None:
    if df.empty:
        st.info("조건을 만족하는 종목이 없습니다.")
    else:
        st.subheader(f"추천 종목 ({len(df)}건)")
        display_df = df.copy()
        display_df["거래대금(억원)"] = (display_df["거래대금"] / 100_000_000).round(0)
        st.dataframe(
            display_df[["종목코드", "종목명", "종가", "등락률", "거래대금(억원)", "거래량"]],
            use_container_width=True,
            hide_index=True,
        )

        if settings.get("telegram_enabled") and st.button("📨 추천 종목 텔레그램으로 전송"):
            try:
                msg = format_recommendation_message(st.session_state.last_date, df)
                send_telegram_message(
                    settings["telegram_bot_token"], settings["telegram_chat_id"], msg
                )
                st.success("텔레그램 전송 완료!")
            except TelegramError as e:
                st.error(str(e))

        st.divider()
        st.subheader("📈 종목 상세 (차트 & 뉴스)")
        options = {f"{row.종목명} ({row.종목코드})": row.종목코드 for row in df.itertuples()}
        picked_label = st.selectbox("종목 선택", list(options.keys()))
        picked_code = options[picked_label]

        chart_col, news_col = st.columns([2, 1])

        with chart_col:
            st.markdown(f"**{picked_label} - 최근 1개월 일봉**")
            ohlcv = get_month_ohlcv(picked_code)
            if ohlcv.empty:
                st.info("차트 데이터가 없습니다.")
            else:
                fig = go.Figure(
                    data=[
                        go.Candlestick(
                            x=ohlcv.index.strftime("%Y-%m-%d"),
                            open=ohlcv["시가"],
                            high=ohlcv["고가"],
                            low=ohlcv["저가"],
                            close=ohlcv["종가"],
                            increasing_line_color="red",
                            decreasing_line_color="blue",
                        )
                    ]
                )
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=450,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)

        with news_col:
            st.markdown(f"**{picked_label} - 관련 뉴스**")
            news_items = get_stock_news(picked_code, count=10)
            if not news_items:
                st.info("뉴스를 불러올 수 없습니다.")
            else:
                for item in news_items:
                    st.markdown(f"- [{item['title']}]({item['link']})  \n  <sub>{item['source']} · {item['date']}</sub>", unsafe_allow_html=True)
