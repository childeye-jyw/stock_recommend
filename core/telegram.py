"""텔레그램 메시지 전송."""
import requests


class TelegramError(Exception):
    pass


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        raise TelegramError("텔레그램 봇 토큰과 chat_id를 먼저 설정하세요.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=10,
    )
    if resp.status_code != 200:
        raise TelegramError(f"텔레그램 전송 실패 ({resp.status_code}): {resp.text}")
