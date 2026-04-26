"""
scheduler.py — Automatic scheduled scans sent to a configured Telegram chat.

Configure via environment variables:
  SCHEDULE_CHAT_ID  — Telegram chat ID to send results to
  SCHEDULE_TIME     — Daily scan time in HH:MM UTC (default: 08:00)
  SCHEDULE_ENABLED  — "true" to enable (default: false)

Usage: Integrate with bot.py by importing and calling setup_scheduler(application)
"""

import logging
import os
from datetime import time

from telegram.ext import Application

logger = logging.getLogger(__name__)


def setup_scheduler(application: Application) -> None:
    """Register scheduled jobs on the PTB Application."""
    if os.getenv("SCHEDULE_ENABLED", "false").lower() != "true":
        logger.info("Scheduled scans disabled (set SCHEDULE_ENABLED=true to enable)")
        return

    chat_id = os.getenv("SCHEDULE_CHAT_ID", "")
    if not chat_id:
        logger.warning("SCHEDULE_ENABLED=true but SCHEDULE_CHAT_ID is not set — skipping")
        return

    schedule_time_str = os.getenv("SCHEDULE_TIME", "08:00")
    try:
        hour, minute = map(int, schedule_time_str.split(":"))
    except ValueError:
        logger.warning(f"Invalid SCHEDULE_TIME '{schedule_time_str}', defaulting to 08:00")
        hour, minute = 8, 0

    job_queue = application.job_queue
    if job_queue is None:
        logger.warning("JobQueue not available — install python-telegram-bot[job-queue]")
        return

    job_queue.run_daily(
        callback=_scheduled_scan,
        time=time(hour=hour, minute=minute),
        data={"chat_id": chat_id, "top_n": 5},
        name="daily_solana_scan",
    )
    logger.info(f"Daily scan scheduled at {hour:02d}:{minute:02d} UTC → chat {chat_id}")


async def _scheduled_scan(context) -> None:
    """Job callback: run scan and send results to configured chat."""
    from news_fetcher import NewsFetcher
    from intelligence_engine import IntelligenceEngine
    from formatters import format_opportunity_message, format_summary_message
    import os

    chat_id = context.job.data["chat_id"]
    top_n = context.job.data.get("top_n", 5)

    await context.bot.send_message(
        chat_id=chat_id,
        text="🕗 *Scheduled Solana intelligence scan starting…*",
        parse_mode="Markdown",
    )

    try:
        fetcher = NewsFetcher()
        engine = IntelligenceEngine(api_key=os.getenv("ANTHROPIC_API_KEY"))

        articles = await fetcher.fetch_all(days_back=7)
        opportunities = await engine.analyze(articles, top_n=top_n)

        summary = format_summary_message(opportunities, len(articles))
        await context.bot.send_message(
            chat_id=chat_id, text=summary, parse_mode="Markdown"
        )

        for i, opp in enumerate(opportunities, 1):
            text = format_opportunity_message(opp, rank=i, total=len(opportunities))
            await context.bot.send_message(
                chat_id=chat_id, text=text, parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Scheduled scan failed: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Scheduled scan failed: {str(e)[:200]}",
        )
