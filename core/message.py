"""추천 종목 메시지 포맷팅."""
import pandas as pd


def format_recommendation_message(date_str: str, df: pd.DataFrame) -> str:
    pretty_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    if df is None or df.empty:
        return f"📈 {pretty_date} 추천 종목 없음 (조건을 만족하는 종목이 없습니다)"

    lines = [f"📈 <b>{pretty_date} 급등 종목 추천</b> (총 {len(df)}건)", ""]
    for i, row in enumerate(df.itertuples(index=False), start=1):
        trading_value_eok = row.거래대금 / 100_000_000
        lines.append(
            f"{i}. <b>{row.종목명}</b>({row.종목코드}) "
            f"등락률 +{row.등락률:.2f}% / 거래대금 {trading_value_eok:,.0f}억원"
        )
    return "\n".join(lines)
