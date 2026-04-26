# 🔭 Solana Intelligence Bot

A Telegram bot that monitors the Solana ecosystem, filters news for on-chain analyzability, and surfaces the **best opportunities for viral Dune dashboards + X threads** — powered by Claude AI.

---

## What It Does

1. **Fetches** Solana ecosystem news from 13+ sources (The Block, Decrypt, CoinDesk, Blockworks, The Defiant, DeFi Llama, Solana Foundation blog, Helius blog, and more) over the last 7 days
2. **Filters** for Solana-relevant articles using keyword matching across 13 category tags (DeFi, DEX, stablecoins, NFTs, DePIN, AI, infrastructure, wallets, institutional, exploits, staking, token launches)
3. **Analyzes** with Claude to score and rank every story by on-chain analyzability + virality potential
4. **Returns** the top 5 structured opportunities with Dune dashboard concepts, SQL hints, chart ideas, X hooks, and thread angles

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- An Anthropic API key (from [console.anthropic.com](https://console.anthropic.com))

### 2. Install

```bash
git clone <this-repo>
cd solana_intel_bot
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and fill in your keys
nano .env
```

Minimum required:
```
TELEGRAM_BOT_TOKEN=7123456789:AAF...
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Run

```bash
python bot.py
```

Open Telegram, find your bot, and send `/scan`.

---

## Commands

| Command | Description |
|---------|-------------|
| `/scan` | Full 7-day scan → top 5 opportunities (~60–90 sec) |
| `/quick` | Quick scan → top 3 opportunities (faster) |
| `/sources` | List all monitored sources |
| `/help` | Show help |

---

## Output Format

For each opportunity you receive:

```
🥇 Opportunity 1/5  🔄

📅 Jan 15, 2025

Jupiter dominates 65% of all Solana DEX volume in January
The Block | DEX • DEFI

Why it matters:
Jupiter's aggregator share has grown 12pp in 30 days, compressing 
Raydium and Orca's direct volume...

On-chain angle:
All swaps on Solana are on-chain and attributable to specific router 
program IDs. Jupiter v6 vs Raydium CLMM vs Orca Whirlpool routing...

📊 Dune Dashboard: "Solana DEX Aggregator Wars — Jan 2025"

Metrics to track:
  · Daily swap volume by protocol (Jupiter, Raydium, Orca, Meteora)
  · Aggregator routing share over 90 days
  · Unique swappers per protocol per day
  · Fee revenue by protocol

Chart ideas:
  · Stacked area: daily volume share by DEX, 90d
  · Line: Jupiter routing % of total Solana DEX volume
  · Bar: protocol revenue per swap (efficiency metric)

Dune query hints:
  · Filter solana.instruction_calls by program_id for Jupiter v6 aggregator
  · Join with solana.transactions for fee data

Why it could go viral:
Winner/loser framing is clear. Large numbers. The "65%" headline is 
shareable. CT loves DEX market share debates...

🐦 X Hook:
Jupiter now routes 65% of all Solana DEX volume.
The other 35% is everyone else combined. Let's look at the data 🧵

X Thread angle:
Open with the shocking stat → show 90-day chart of share shift → 
break down who is losing (Raydium direct, Orca) → analyze why 
(better routing, UI integrations) → end with fee revenue comparison

Article angle:
"How Jupiter became the Solana DEX black hole" — long-form analysis 
of aggregator flywheel dynamics with on-chain data

🔥 Confidence: 9/10
```

---

## Architecture

```
bot.py               — Telegram bot, command handlers
news_fetcher.py      — Async RSS + JSON news collection from 13+ sources
intelligence_engine.py — Claude API integration, prompt engineering, JSON parsing
formatters.py        — Telegram Markdown message formatting
scheduler.py         — Optional: daily automatic scans
```

---

## Adding More Sources

Edit `RSS_FEEDS` in `news_fetcher.py`:

```python
RSS_FEEDS.append({
    "name": "Your Source",
    "url": "https://yoursource.com/feed.xml",
    "category": "media",   # or: solana_official, solana_infra, defi, nft
})
```

Sources with `category: "media"` are filtered by SOLANA_KEYWORDS automatically.
Sources with `category: "solana_official"` or `"solana_infra"` are included without filtering.

---

## Scheduled Scans

To receive automatic daily reports:

```bash
# In .env:
SCHEDULE_ENABLED=true
SCHEDULE_CHAT_ID=your_chat_id   # Get from @userinfobot
SCHEDULE_TIME=08:00              # UTC time
```

Then update `bot.py` to import and call `setup_scheduler`:

```python
from scheduler import setup_scheduler
# After: app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
setup_scheduler(app)
```

---

## Docker Deployment

```bash
docker build -t solana-intel-bot .
docker run -d --env-file .env --name solana-bot solana-intel-bot
```

For production, use a process manager or deploy to Railway / Fly.io / a VPS.

---

## Optional: CryptoPanic Integration

Register free at [cryptopanic.com/developers/api](https://cryptopanic.com/developers/api/) and add:
```
CRYPTOPANIC_API_KEY=your_key_here
```
This adds a high-quality curated Solana news stream as an additional source.

---

## Cost Estimate

Each `/scan` call:
- Fetches ~50–100 articles → Claude input: ~15,000–25,000 tokens
- Claude output: ~3,000–5,000 tokens
- Model: `claude-opus-4-5`
- Cost: ~$0.20–0.40 per scan at current pricing

For daily scheduled scans: ~$6–12/month.

---

## Troubleshooting

**Bot not responding:** Check `bot.log` for errors. Verify `TELEGRAM_BOT_TOKEN` is correct.

**No articles found:** Some RSS feeds may be temporarily unavailable. The bot handles this gracefully and continues with other sources.

**JSON parse error:** Rare edge case where Claude returns malformed JSON. The bot logs the raw response — retry usually works.

**Slow scan:** Normal. RSS fetching + Claude analysis takes 45–90 seconds for a full scan.
