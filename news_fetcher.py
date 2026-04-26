"""
news_fetcher.py — Collects Solana ecosystem news from multiple sources.

Sources:
  - RSS feeds (The Block, Decrypt, CoinDesk, Blockworks, The Defiant, etc.)
  - DeFi Llama news endpoint
  - Solana Foundation / project blogs via RSS
  - CryptoPanic Solana filter (optional, requires API key)
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urljoin

import aiohttp
import feedparser

logger = logging.getLogger(__name__)


# ── RSS Feed Definitions ─────────────────────────────────────────────────────

RSS_FEEDS = [
    # General crypto — high Solana coverage
    {
        "name": "The Block",
        "url": "https://www.theblock.co/rss.xml",
        "category": "media",
    },
    {
        "name": "Decrypt",
        "url": "https://decrypt.co/feed",
        "category": "media",
    },
    {
        "name": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "category": "media",
    },
    {
        "name": "Blockworks",
        "url": "https://blockworks.co/feed",
        "category": "media",
    },
    {
        "name": "The Defiant",
        "url": "https://thedefiant.io/feed",
        "category": "defi_media",
    },
    {
        "name": "CryptoSlate",
        "url": "https://cryptoslate.com/feed/",
        "category": "media",
    },
    {
        "name": "Cointelegraph",
        "url": "https://cointelegraph.com/rss",
        "category": "media",
    },
    {
        "name": "DL News",
        "url": "https://www.dlnews.com/rss/",
        "category": "media",
    },
    # Solana-specific
    {
        "name": "Solana Foundation Blog",
        "url": "https://solana.com/news/rss.xml",
        "category": "solana_official",
    },
    {
        "name": "Helius Blog",
        "url": "https://www.helius.dev/blog/rss.xml",
        "category": "solana_infra",
    },
    # DeFi
    {
        "name": "DeFi Llama",
        "url": "https://news.llama.fi/feed",
        "category": "defi",
    },
    {
        "name": "Bankless",
        "url": "https://www.bankless.com/feed",
        "category": "defi_media",
    },
    # NFT / Consumer
    {
        "name": "NFT Now",
        "url": "https://nftnow.com/feed/",
        "category": "nft",
    },
]

# JSON / API endpoints (no RSS)
JSON_SOURCES = [
    {
        "name": "CryptoPanic Solana",
        "url": "https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&currencies=SOL&kind=news&public=true",
        "type": "cryptopanic",
        "requires_key": "CRYPTOPANIC_API_KEY",
    },
]

# Solana-related keywords for filtering general crypto feeds
SOLANA_KEYWORDS = [
    "solana", "sol ", "$sol", "solana foundation",
    "jupiter", "jup", "raydium", "orca", "meteora", "kamino",
    "drift protocol", "mango markets", "marginfi",
    "magic eden", "tensor", "compressed nft",
    "helium", "hivemapper", "hivemapper",
    "phantom wallet", "solflare",
    "helius", "triton",
    "jito", "marinade", "sanctum",
    "pyth network", "switchboard",
    "wormhole", "debridge",
    "bonk", "wif", "dogwifhat", "popcat",
    "spl token", "solana program",
    "firedancer", "agave",
]

# Categories to help with scoring
CATEGORY_KEYWORDS = {
    "defi": ["defi", "tvl", "liquidity", "yield", "lending", "borrow", "vault", "amm"],
    "dex": ["dex", "swap", "volume", "liquidity pool", "aggregator", "routing", "perp", "perpetual"],
    "stablecoin": ["stablecoin", "usdc", "usdt", "pyusd", "eurc", "mint", "bridge", "depeg"],
    "nft": ["nft", "collection", "mint", "royalty", "marketplace", "floor price", "tensor", "magic eden"],
    "depin": ["depin", "helium", "hivemapper", "hotspot", "wireless", "physical network", "iot"],
    "ai": ["ai agent", "artificial intelligence", "llm", "eliza", "agent framework", "autonomous"],
    "infrastructure": ["rpc", "validator", "firedancer", "agave", "tps", "latency", "uptime", "node"],
    "wallet": ["wallet", "phantom", "solflare", "backpack", "mobile wallet", "embedded wallet"],
    "institutional": ["blackrock", "visa", "paypal", "stripe", "coinbase", "franklin", "fidelity", "etf"],
    "token_launch": ["launch", "airdrop", "tge", "token generation", "listing", "ido", "fair launch"],
    "exploit": ["exploit", "hack", "vulnerability", "drain", "attack", "rug", "scam", "bug"],
    "staking": ["staking", "unstaking", "liquid staking", "lst", "validator", "epoch", "rewards"],
}


# ── NewsFetcher ───────────────────────────────────────────────────────────────

class NewsFetcher:
    def __init__(self, timeout: int = 15):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

    async def fetch_all(self, days_back: int = 7) -> list[dict]:
        """Fetch articles from all configured sources."""
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers={"User-Agent": "SolanaIntelBot/1.0 (news aggregator)"},
        ) as session:
            tasks = [self._fetch_rss(session, feed) for feed in RSS_FEEDS]
            tasks += [self._fetch_json_source(session, src) for src in JSON_SOURCES]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        articles = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Feed fetch error: {result}")
                continue
            articles.extend(result)

        # Deduplicate by title similarity
        articles = self._deduplicate(articles)

        # Sort newest first
        articles.sort(key=lambda a: a.get("published_ts", 0), reverse=True)

        logger.info(f"Fetched {len(articles)} unique Solana-relevant articles")
        return articles

    async def _fetch_rss(self, session: aiohttp.ClientSession, feed: dict) -> list[dict]:
        """Fetch and parse a single RSS feed."""
        articles = []
        try:
            async with session.get(feed["url"]) as resp:
                if resp.status != 200:
                    logger.warning(f"RSS {feed['name']}: HTTP {resp.status}")
                    return []
                content = await resp.text()

            parsed = feedparser.parse(content)

            for entry in parsed.entries:
                article = self._parse_rss_entry(entry, feed)
                if article is None:
                    continue
                articles.append(article)

        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching {feed['name']}")
        except Exception as e:
            logger.warning(f"Error fetching {feed['name']}: {e}")

        return articles

    def _parse_rss_entry(self, entry: object, feed: dict) -> Optional[dict]:
        """Parse a single RSS entry into a normalized article dict."""
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or ""
        link = getattr(entry, "link", "") or ""

        # Parse published date
        published_ts = 0
        published_str = ""
        for date_field in ("published_parsed", "updated_parsed"):
            t = getattr(entry, date_field, None)
            if t:
                try:
                    dt = datetime(*t[:6], tzinfo=timezone.utc)
                    published_ts = dt.timestamp()
                    published_str = dt.strftime("%Y-%m-%d %H:%M UTC")
                    break
                except Exception:
                    pass

        # Filter by date
        if published_ts and published_ts < self.cutoff_date.timestamp():
            return None

        # For general crypto media, filter by Solana relevance
        if feed["category"] in ("media", "defi_media", "nft"):
            combined = (title + " " + summary).lower()
            if not any(kw in combined for kw in SOLANA_KEYWORDS):
                return None

        # Build article
        categories = self._detect_categories(title + " " + summary)

        return {
            "title": title.strip(),
            "summary": summary.strip()[:500],
            "url": link,
            "source": feed["name"],
            "source_category": feed["category"],
            "published_ts": published_ts,
            "published_str": published_str,
            "categories": categories,
        }

    async def _fetch_json_source(
        self, session: aiohttp.ClientSession, source: dict
    ) -> list[dict]:
        """Fetch a JSON API source (e.g. CryptoPanic)."""
        # Check if required API key is present
        key_name = source.get("requires_key")
        if key_name:
            api_key = os.getenv(key_name, "")
            if not api_key:
                logger.info(f"Skipping {source['name']}: {key_name} not set")
                return []
            url = source["url"].replace(f"{{{key_name}}}", api_key)
        else:
            url = source["url"]

        articles = []
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

            if source["type"] == "cryptopanic":
                articles = self._parse_cryptopanic(data)

        except Exception as e:
            logger.warning(f"JSON source {source['name']} error: {e}")

        return articles

    def _parse_cryptopanic(self, data: dict) -> list[dict]:
        """Parse CryptoPanic API response."""
        articles = []
        for item in data.get("results", []):
            published_at = item.get("published_at", "")
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if dt < self.cutoff_date:
                    continue
                ts = dt.timestamp()
                pub_str = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                ts = 0
                pub_str = published_at

            title = item.get("title", "")
            url = item.get("url", "")
            source_name = item.get("source", {}).get("title", "CryptoPanic")

            categories = self._detect_categories(title)

            articles.append({
                "title": title,
                "summary": "",
                "url": url,
                "source": source_name,
                "source_category": "media",
                "published_ts": ts,
                "published_str": pub_str,
                "categories": categories,
            })
        return articles

    def _detect_categories(self, text: str) -> list[str]:
        """Tag article with relevant Solana ecosystem categories."""
        text_lower = text.lower()
        found = []
        for cat, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                found.append(cat)
        return found

    def _deduplicate(self, articles: list[dict]) -> list[dict]:
        """Remove near-duplicate articles by title."""
        seen_titles = set()
        unique = []
        for article in articles:
            # Normalize title for comparison
            norm = article["title"].lower().strip()
            norm = "".join(c for c in norm if c.isalnum() or c == " ")
            norm = " ".join(norm.split()[:8])  # first 8 words

            if norm not in seen_titles and norm:
                seen_titles.add(norm)
                unique.append(article)
        return unique
