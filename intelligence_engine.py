"""
intelligence_engine.py — Uses Claude to analyze Solana news and identify
the best on-chain analysis + viral X post opportunities.
"""

import json
import logging
import re
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# ── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an elite crypto on-chain analyst and data journalist specializing in the Solana ecosystem. 
You have deep expertise in:
- Solana DeFi protocols (Jupiter, Raydium, Orca, Meteora, Kamino, Drift, Marginfi, Jito)
- Solana NFT/consumer apps (Magic Eden, Tensor)
- DePIN on Solana (Helium, Hivemapper)
- Solana infrastructure (validators, Firedancer, Helius, Triton)
- On-chain data analysis using Dune.com (SQL queries, dashboards, visualizations)
- Viral X (Twitter) content strategy for crypto audiences
- Identifying data-driven narratives that resonate with on-chain analysts and CT

Your job is to analyze incoming Solana news articles and identify the TOP opportunities 
where on-chain data from Dune.com can be used to create a viral dashboard + X thread.

You think like a data detective: you look for stories where the real signal is in the 
blockchain data, not just the headlines."""


ANALYSIS_PROMPT_TEMPLATE = """Below are {count} Solana ecosystem news articles from the past 7 days.

ARTICLES:
{articles_block}

---

TASK:
Analyze these articles and identify the TOP {top_n} stories that represent the BEST opportunities 
for an on-chain data analyst to:
1. Create a compelling Dune.com dashboard
2. Write a viral X thread/post with data-driven insights

SELECTION CRITERIA:
For each story you select, it MUST be verifiable/expandable using Solana on-chain data such as:
- Wallet activity, transaction counts, protocol usage
- DEX volume, swaps, liquidity flows
- TVL changes, deposits/withdrawals
- Token holder growth, transfer flows
- User retention / new users / DAU
- Aggregator routing, perps activity
- Staking/unstaking, revenue/fees
- Stablecoin mint/bridge flows
- Market share shifts between protocols

VIRALITY CRITERIA:
Rank higher if the story has:
- Strong "surprising data angle" (numbers that defy expectations)
- Clear "winner vs loser" framing
- Ecosystem-wide impact
- Fast growth / unusual spike
- Large numbers or market share shifts
- Institutional relevance
- User behavior change visible on-chain
- Clean visual/chart opportunity
- Potential for contrarian or insight-driven take

REJECT stories that:
- Are mostly narrative/PR with no on-chain signal
- Cannot be meaningfully measured with Dune
- Are too vague or speculative

OUTPUT FORMAT:
Return a JSON array of exactly {top_n} opportunity objects. 
Each object must have ALL of these fields:

{{
  "rank": 1,
  "title": "Story title (can be slightly rewritten for clarity)",
  "source": "Publication name",
  "source_url": "URL",
  "published": "Date string",
  "categories": ["defi", "dex"],
  "relevance_summary": "2-3 sentence explanation of why this story matters for Solana ecosystem right now",
  "onchain_angle": "Why this story is analyzable on-chain — what blockchain signals exist",
  "dune_dashboard_concept": "Name/concept for the Dune dashboard (e.g. 'Solana DEX Market Share Wars: Jan 2025')",
  "metrics_to_track": [
    "Specific metric 1 (e.g. Daily swap volume by protocol)",
    "Specific metric 2",
    "Specific metric 3",
    "Specific metric 4"
  ],
  "chart_ideas": [
    "Chart 1 description (e.g. Stacked bar: daily DEX volume by protocol, 30d)",
    "Chart 2 description",
    "Chart 3 description"
  ],
  "dune_query_hints": [
    "Hint for SQL query 1 (e.g. Use solana.transactions filtered by program_id for Jupiter v6)",
    "Hint for query 2"
  ],
  "viral_reasons": "Why this has strong viral potential on X — specific reasons",
  "x_hook": "The attention-grabbing first line for an X post (under 200 chars, punchy)",
  "x_thread_angle": "The story angle and narrative structure for a full X thread",
  "article_angle": "Suggested analytical article angle (for a longer-form piece)",
  "confidence_score": 8
}}

Return ONLY the raw JSON array. No markdown, no explanation, no preamble.
The array must contain exactly {top_n} objects."""


# ── IntelligenceEngine ───────────────────────────────────────────────────────

class IntelligenceEngine:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def analyze(self, articles: list[dict], top_n: int = 5) -> list[dict]:
        """
        Analyze articles with Claude and return ranked opportunities.
        This is async-friendly but makes sync Anthropic SDK calls via asyncio executor.
        """
        if not articles:
            return []

        # Cap articles to avoid token limits (send top 80 most recent)
        articles_to_send = articles[:80]

        articles_block = self._format_articles_for_prompt(articles_to_send)
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            count=len(articles_to_send),
            articles_block=articles_block,
            top_n=top_n,
        )

        logger.info(f"Sending {len(articles_to_send)} articles to Claude for analysis")

        # Run sync call in thread pool to avoid blocking event loop
        import asyncio
        loop = asyncio.get_event_loop()
        response_text = await loop.run_in_executor(
            None, self._call_claude, prompt
        )

        opportunities = self._parse_response(response_text, top_n)
        logger.info(f"Parsed {len(opportunities)} opportunities from Claude")
        return opportunities

    def _call_claude(self, prompt: str) -> str:
        """Synchronous Claude API call."""
        message = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def _format_articles_for_prompt(self, articles: list[dict]) -> str:
        """Format articles list into a compact block for the prompt."""
        lines = []
        for i, art in enumerate(articles, 1):
            cats = ", ".join(art.get("categories", [])) or "general"
            summary = art.get("summary", "")
            summary_snippet = summary[:200] + "…" if len(summary) > 200 else summary

            lines.append(
                f"[{i}] {art.get('title', 'Untitled')}\n"
                f"    Source: {art.get('source', '?')} | "
                f"Date: {art.get('published_str', '?')} | "
                f"Tags: {cats}\n"
                f"    URL: {art.get('url', '')}\n"
                f"    Summary: {summary_snippet}\n"
            )
        return "\n".join(lines)

    def _parse_response(self, text: str, top_n: int) -> list[dict]:
        """Parse Claude's JSON response into opportunity dicts."""
        # Strip any accidental markdown fences
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data[:top_n]
            elif isinstance(data, dict) and "opportunities" in data:
                return data["opportunities"][:top_n]
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Raw response: {text[:500]}")

            # Fallback: try to extract JSON array from response
            match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())[:top_n]
                except Exception:
                    pass

        logger.error("Could not parse Claude response as JSON")
        return []
