"""
formatters.py — Formats opportunity data into polished Telegram messages.
"""

from datetime import datetime, timezone


# ── Score emoji ───────────────────────────────────────────────────────────────

def score_emoji(score: int) -> str:
    if score >= 9:
        return "🔥"
    elif score >= 7:
        return "⚡"
    elif score >= 5:
        return "✅"
    else:
        return "📊"


def category_emoji(categories: list[str]) -> str:
    emoji_map = {
        "defi": "🏦",
        "dex": "🔄",
        "stablecoin": "💵",
        "nft": "🖼",
        "depin": "📡",
        "ai": "🤖",
        "infrastructure": "⚙️",
        "wallet": "👛",
        "institutional": "🏛",
        "token_launch": "🚀",
        "exploit": "⚠️",
        "staking": "🥩",
    }
    if not categories:
        return "📰"
    return emoji_map.get(categories[0], "📰")


def rank_medal(rank: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(rank, f"#{rank}")


# ── Summary message ───────────────────────────────────────────────────────────

def format_summary_message(opportunities: list[dict], article_count: int) -> str:
    now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    lines = [
        f"🔭 *Solana Intelligence Scan Complete*",
        f"_Scanned {article_count} articles • {now}_",
        "",
        f"Found *{len(opportunities)} top opportunities* for Dune dashboards + viral X threads:",
        "",
    ]

    for opp in opportunities:
        rank = opp.get("rank", "?")
        title = opp.get("title", "Untitled")[:60]
        score = opp.get("confidence_score", 0)
        cats = opp.get("categories", [])
        cat_e = category_emoji(cats)
        medal = rank_medal(rank)
        s_e = score_emoji(score)

        lines.append(f"{medal} {cat_e} *{title}*")
        lines.append(f"   {s_e} Confidence: {score}/10")
        lines.append("")

    lines.append("_Full analysis for each opportunity follows below ↓_")
    return "\n".join(lines)


# ── Individual opportunity message ────────────────────────────────────────────

def format_opportunity_message(opp: dict, rank: int, total: int) -> str:
    rank_n = opp.get("rank", rank)
    title = opp.get("title", "Untitled")
    source = opp.get("source", "Unknown")
    published = opp.get("published", "")
    categories = opp.get("categories", [])
    score = opp.get("confidence_score", 0)
    cat_e = category_emoji(categories)
    medal = rank_medal(rank_n)
    s_e = score_emoji(score)

    cats_str = " • ".join(c.upper() for c in categories[:3]) if categories else "GENERAL"

    # Metrics list
    metrics = opp.get("metrics_to_track", [])
    metrics_lines = "\n".join(f"  · {m}" for m in metrics[:4])

    # Chart ideas
    charts = opp.get("chart_ideas", [])
    charts_lines = "\n".join(f"  · {c}" for c in charts[:3])

    # Dune query hints
    hints = opp.get("dune_query_hints", [])
    hints_lines = "\n".join(f"  · {h}" for h in hints[:2])

    # Truncate long text fields
    relevance = _truncate(opp.get("relevance_summary", ""), 280)
    onchain = _truncate(opp.get("onchain_angle", ""), 250)
    dune_concept = opp.get("dune_dashboard_concept", "")
    viral = _truncate(opp.get("viral_reasons", ""), 250)
    x_hook = _truncate(opp.get("x_hook", ""), 200)
    x_thread = _truncate(opp.get("x_thread_angle", ""), 300)
    article_angle = _truncate(opp.get("article_angle", ""), 250)

    # Published date
    pub_line = f"_📅 {published}_\n" if published else ""

    msg = (
        f"{medal} *Opportunity {rank_n}/{total}* {cat_e}\n"
        f"{pub_line}"
        f"*{title}*\n"
        f"_{source}_ | {cats_str}\n"
        f"\n"
        f"*Why it matters:*\n{relevance}\n"
        f"\n"
        f"*On-chain angle:*\n{onchain}\n"
        f"\n"
        f"📊 *Dune Dashboard:* _{dune_concept}_\n"
        f"\n"
        f"*Metrics to track:*\n{metrics_lines}\n"
        f"\n"
        f"*Chart ideas:*\n{charts_lines}\n"
    )

    if hints_lines:
        msg += f"\n*Dune query hints:*\n{hints_lines}\n"

    msg += (
        f"\n"
        f"*Why it could go viral:*\n{viral}\n"
        f"\n"
        f"🐦 *X Hook:*\n_{x_hook}_\n"
        f"\n"
        f"*X Thread angle:*\n{x_thread}\n"
        f"\n"
        f"*Article angle:*\n{article_angle}\n"
        f"\n"
        f"{s_e} *Confidence: {score}/10*"
    )

    return msg


def _truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"
