import json
import os
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULT_SETTINGS = {
    # 최소 거래대금 (원 단위). 기본값 2000억원.
    "min_trading_value": 200_000_000_000,
    # 최소 등락률 (%). 기본값 5%.
    "min_change_pct": 5.0,
    # 최소 상장 경과일. 신규 상장 종목 제외용. 기본값 30일.
    "min_listed_days": 30,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
}

# GitHub Actions 등 CI 환경에서는 settings.json(로컬 전용, git에 커밋되지 않음) 대신
# 이 환경변수들로 설정을 주입한다. (텔레그램 토큰을 저장소에 노출하지 않기 위함)
_ENV_OVERRIDES = {
    "TELEGRAM_BOT_TOKEN": ("telegram_bot_token", str),
    "TELEGRAM_CHAT_ID": ("telegram_chat_id", str),
    "MIN_TRADING_VALUE": ("min_trading_value", int),
    "MIN_CHANGE_PCT": ("min_change_pct", float),
    "MIN_LISTED_DAYS": ("min_listed_days", int),
}


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        settings = {**DEFAULT_SETTINGS, **data}
    else:
        settings = DEFAULT_SETTINGS.copy()

    for env_key, (setting_key, caster) in _ENV_OVERRIDES.items():
        value = os.environ.get(env_key)
        if value:
            settings[setting_key] = caster(value)

    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        settings["telegram_enabled"] = True

    return settings


def save_settings(settings: dict) -> None:
    merged = {**DEFAULT_SETTINGS, **settings}
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
