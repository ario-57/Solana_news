"""
Solana Ecosystem News Intelligence Bot
A Telegram bot that monitors Solana news and surfaces the best on-chain analysis opportunities.

Requirements:
    pip install python-telegram-bot>=20.0 anthropic feedparser aiohttp python-dotenv

Usage:
    1. Copy .env.example to .env and fill in your keys
    2. python bot.py
"""

import asyncio
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from news_fetcher import NewsFetcher
from intelligence_engine import IntelligenceEngine
from formatters import format_opportunity_message, format_summary_message

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALLOWED_USER_IDS = os.getenv("ALLOWED_USER_IDS", "")  # Comma-separated, leave empty to allow all

# ── Auth helper ──────────────────────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS.strip():
        return True
    allowed = [uid.strip() for uid in ALLOWED_USER_IDS.split(",")]
    return str(user_id) in allowed


# ── Command handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    welcome = (
        "🔭 *Solana Intelligence Bot*\n\n"
        "I monitor the Solana ecosystem and surface the best on-chain analysis opportunities "
        "for Dune dashboards and viral X threads.\n\n"
        "*Commands:*\n"
        "• /scan — Full 7-day scan + top 5 opportunities\n"
        "• /quick — Top 3 opportunities (faster)\n"
        "• /sources — List monitored sources\n"
        "• /help — Show this message\n\n"
        "_Scans typically take 60–90 seconds._"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List monitored news sources."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return

    sources_text = (
        "📡 *Monitored Sources*\n\n"
        "*RSS / Web Feeds:*\n"
        "• The Block — theblock.co\n"
        "• Decrypt — decrypt.co\n"
        "• CoinDesk — coindesk.com\n"
        "• Blockworks — blockworks.co\n"
        "• CryptoSlate — cryptoslate.com\n"
        "• The Defiant — thedefiant.io\n"
        "• DeFi Llama News\n"
        "• Solana Foundation Blog\n"
        "• Helius Blog\n\n"
        "*X/Twitter Accounts (via search):*\n"
        "• @solana, @SolanaFndn\n"
        "• @aeyakovenko, @rajgokal\n"
        "• @JupiterExchange, @orca_so\n"
        "• @RaydiumProtocol, @MarginFi\n"
        "• @kamino_finance, @MeteoraAG\n"
        "• @driftprotocol, @mango_markets\n"
        "• @MagicEden, @tensor_hq\n"
        "• @helium, @HiveMapper\n"
        "• @phantom, @solflare_wallet\n"
        "• @Helius_RPC, @triton_one\n\n"
        "*Categories tracked:*\n"
        "DeFi • DEX • Stablecoins • NFTs • DePIN • AI×Solana\n"
        "Infrastructure • Wallets • Perps • Airdrops • Institutional"
    )
    await update.message.reply_text(sources_text, parse_mode=ParseMode.MARKDOWN)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run full 7-day scan returning top 5 opportunities."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    await _run_scan(update, context, top_n=5)


async def quick_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run quick scan returning top 3 opportunities."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    await _run_scan(update, context, top_n=3)


async def _run_scan(
    update: Update, context: ContextTypes.DEFAULT_TYPE, top_n: int = 5
) -> None:
    """Core scan logic shared by /scan and /quick."""
    status_msg = await update.message.reply_text(
        "🔍 *Starting Solana ecosystem scan…*\n\n"
        "⏳ Fetching news from all sources…",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        fetcher = NewsFetcher()
        engine = IntelligenceEngine(api_key=ANTHROPIC_API_KEY)

        # Step 1: fetch
        await status_msg.edit_text(
            "🔍 *Scanning Solana ecosystem…*\n\n"
            "📰 Fetching news from all sources…",
            parse_mode=ParseMode.MARKDOWN,
        )
        articles = await fetcher.fetch_all(days_back=7)
        article_count = len(articles)

        # Step 2: filter + rank
        await status_msg.edit_text(
            f"🔍 *Scanning Solana ecosystem…*\n\n"
            f"✅ Fetched {article_count} articles\n"
            f"🧠 Running intelligence analysis…",
            parse_mode=ParseMode.MARKDOWN,
        )
        opportunities = await engine.analyze(articles, top_n=top_n)

        # Step 3: send summary
        await status_msg.edit_text(
            f"🔍 *Scanning Solana ecosystem…*\n\n"
            f"✅ Fetched {article_count} articles\n"
            f"✅ Identified top {len(opportunities)} opportunities\n"
            f"📤 Sending results…",
            parse_mode=ParseMode.MARKDOWN,
        )

        summary = format_summary_message(opportunities, article_count)
        await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)

        # Step 4: send each opportunity with navigation buttons
        for i, opp in enumerate(opportunities, 1):
            text = format_opportunity_message(opp, rank=i, total=len(opportunities))

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔗 Open Source", url=opp.get("source_url", "https://dune.com")
                    ),
                    InlineKeyboardButton(
                        "📊 Dune.com", url="https://dune.com/browse/dashboards?q=solana"
                    ),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup
            )
            await asyncio.sleep(0.5)  # avoid Telegram rate limits

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ *Scan failed.*\n\n`{str(e)[:200]}`\n\nPlease try again.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks (future expansion)."""
    query = update.callback_query
    await query.answer()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("quick", quick_command))
    app.add_handler(CommandHandler("sources", sources_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Solana Intelligence Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
