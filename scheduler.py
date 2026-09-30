"""매 거래일 22:00(KST)에 추천 종목을 조회해 텔레그램으로 전송하는 스케줄러.

실행 방식:
  - python scheduler.py         : 상시 실행 (터미널을 켜두거나 launchd/systemd 등으로 관리)
  - python scheduler.py --once  : 즉시 1회만 실행하고 종료 (GitHub Actions 등 CI 스케줄러용)
"""
import argparse
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import load_settings
from core.market import get_latest_session_date, get_recommendations, is_recent_trading_day
from core.message import format_recommendation_message
from core.telegram import TelegramError, send_telegram_message


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("stock_recommend_scheduler")


def run_daily_job() -> None:
    settings = load_settings()

    latest_session = get_latest_session_date()
    if not is_recent_trading_day(latest_session):
        logger.info(
            "최근 거래일(%s)이 오늘/어제 범위를 벗어나 스킵합니다. "
            "(휴장일이거나, 예약 실행이 자정을 넘겨 지연되었을 수 있습니다.)",
            latest_session,
        )
        return

    df = get_recommendations(
        min_trading_value=int(settings["min_trading_value"]),
        min_change_pct=float(settings["min_change_pct"]),
        min_listed_days=int(settings.get("min_listed_days", 0)),
    )
    logger.info("%s 추천 종목 %d건 발견", latest_session, len(df))

    if not settings.get("telegram_enabled"):
        logger.info("텔레그램 알림이 비활성화되어 있어 전송하지 않습니다.")
        return

    message = format_recommendation_message(latest_session, df)
    try:
        send_telegram_message(
            settings["telegram_bot_token"], settings["telegram_chat_id"], message
        )
        logger.info("텔레그램 전송 완료")
    except TelegramError:
        logger.exception("텔레그램 전송 실패")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--once",
        action="store_true",
        help="상시 스케줄러 대신 즉시 1회만 실행하고 종료한다 (CI 환경용).",
    )
    args = parser.parse_args()

    if args.once:
        run_daily_job()
        return

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        run_daily_job,
        CronTrigger(day_of_week="mon-fri", hour=22, minute=0, timezone="Asia/Seoul"),
        id="daily_recommendation",
    )
    logger.info("스케줄러 시작. 매 평일 22:00(KST)에 실행됩니다. (Ctrl+C로 종료)")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러를 종료합니다.")


if __name__ == "__main__":
    main()
