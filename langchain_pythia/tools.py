"""Pythia Oracle tools for LangChain.

Provides access to on-chain calculated crypto indicators (EMA, RSI,
Bollinger Bands, Volatility) for 22 tokens via Chainlink on Polygon.
"""

import json
from typing import Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from langchain_pythia._client import fetch_data, fetch_data_sync

# ---------------------------------------------------------------------------
# Contracts (static, rarely changes)
# ---------------------------------------------------------------------------

CONTRACTS = {
    "chain": "Polygon",
    "chain_id": 137,
    "link_token_erc677": "0xb0897686c545045aFc77CF20eC7A532E3120E0F1",
    "operator": "0xAA37710aF244514691629Aa15f4A5c271EaE6891",
    "faucet": "0x640fC3B9B607E324D7A3d89Fcb62C77Cc0Bd420A",
    "consumers": {
        "discovery": {
            "address": "0xeC2865d66ae6Af47926B02edd942A756b394F820",
            "fee": "0.01 LINK",
            "returns": "uint256 (single indicator)",
        },
        "analysis": {
            "address": "0x3b3aC62d73E537E3EF84D97aB5B84B51aF8dB316",
            "fee": "0.03 LINK",
            "returns": "uint256[] (1H/1D/1W bundle)",
        },
        "speed": {
            "address": "0xC406e7d9AC385e7AB43cBD56C74ad487f085d47B",
            "fee": "0.05 LINK",
            "returns": "uint256[] (5M bundle)",
        },
        "complete": {
            "address": "0x2dEC98fd7173802b351d1E28d0Cd5DdD20C24252",
            "fee": "0.10 LINK",
            "returns": "uint256[] (all indicators)",
        },
    },
}


# ---------------------------------------------------------------------------
# Tool: List Tokens
# ---------------------------------------------------------------------------


class PythiaListTokensTool(BaseTool):
    """List all tokens tracked by Pythia Oracle with status and reliability.

    Returns token symbols, categories, data source count, 30-day uptime,
    and operational status. Covers cross-chain tokens (BTC, SOL, TAO,
    RENDER, ONDO, etc.) and Polygon DeFi tokens.
    """

    name: str = "pythia_list_tokens"
    description: str = (
        "List all crypto tokens tracked by Pythia Oracle with their status, "
        "30-day uptime, and data source count. Covers 22 tokens including "
        "BTC, SOL, TAO, RENDER, ONDO, AAVE, UNI, and more."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        data = fetch_data_sync()
        return _format_token_list(data)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None
    ) -> str:
        data = await fetch_data()
        return _format_token_list(data)


def _format_token_list(data: dict) -> str:
    tokens = data.get("tokens", [])
    stats = data.get("stats", {})
    lines = [
        f"Pythia Oracle — {stats.get('tokens', len(tokens))} tokens, "
        f"{stats.get('total_indicators', '?')} indicator feeds\n"
    ]
    lines.append(
        f"{'Symbol':<8} {'Engine ID':<28} {'Category':<16} "
        f"{'Status':<6} {'Uptime':>7}  {'Src':>3}"
    )
    lines.append("-" * 78)
    for t in sorted(tokens, key=lambda x: x.get("category", "")):
        uptime = (
            f"{t['uptime_30d']:.1f}%"
            if t.get("uptime_30d") is not None
            else "?"
        )
        lines.append(
            f"{t['symbol']:<8} {t['engine_id']:<28} "
            f"{t.get('category', '?'):<16} {t.get('status', '?'):<6} "
            f"{uptime:>7}  {t.get('sources', '?'):>3}"
        )
    lines.append(f"\nWebsite: https://pythia.c3x-solutions.com")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: Token Feeds
# ---------------------------------------------------------------------------


class _TokenFeedsInput(BaseModel):
    engine_id: str = Field(
        description=(
            "Token engine ID, e.g. 'bitcoin', 'solana', 'bittensor', "
            "'aave', 'render-token'. Use pythia_list_tokens to see all IDs."
        )
    )


class PythiaTokenFeedsTool(BaseTool):
    """Get all indicator feed names for a specific token.

    Shows every available feed (EMA, RSI, Bollinger, Volatility across
    all timeframes) plus the token's reliability stats.
    """

    name: str = "pythia_token_feeds"
    description: str = (
        "Get all available on-chain indicator feeds (EMA, RSI, Bollinger, "
        "Volatility) for a specific crypto token from Pythia Oracle. "
        "Returns feed names that can be used in smart contract calls."
    )
    args_schema: Type[BaseModel] = _TokenFeedsInput

    def _run(
        self,
        engine_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        data = fetch_data_sync()
        return _format_token_feeds(data, engine_id)

    async def _arun(
        self,
        engine_id: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_token_feeds(data, engine_id)


def _format_token_feeds(data: dict, engine_id: str) -> str:
    tokens = data.get("tokens", [])
    token = next((t for t in tokens if t["engine_id"] == engine_id), None)
    if not token:
        available = sorted(t["engine_id"] for t in tokens)
        return f"No token found for '{engine_id}'.\nAvailable: {', '.join(available)}"

    feed_names = token.get("feed_names", [])
    lines = [
        f"{token['symbol']} ({token['name']}) — {token.get('pair', '?')}",
        f"Status: {token.get('status', '?')}  |  "
        f"30d uptime: {token.get('uptime_30d', '?')}%  |  "
        f"Data sources: {token.get('sources', '?')}",
        f"\n{len(feed_names)} indicator feeds:\n",
    ]
    groups: dict[str, list[str]] = {}
    for name in sorted(feed_names):
        suffix = name[len(engine_id) + 1 :]
        cat = suffix.split("_")[0]
        groups.setdefault(cat, []).append(name)
    for cat, feeds in sorted(groups.items()):
        lines.append(f"  {cat}:")
        for feed in feeds:
            lines.append(f"    {feed}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: Health Check
# ---------------------------------------------------------------------------


class PythiaHealthCheckTool(BaseTool):
    """Check Pythia Oracle reliability and uptime.

    Returns per-token 30-day uptime (worst-first), data source health,
    infrastructure status, and active incidents.
    """

    name: str = "pythia_health_check"
    description: str = (
        "Check the reliability and uptime of Pythia Oracle. Returns "
        "per-token 30-day uptime, data source health, infrastructure "
        "status, and active incidents. Use before integrating."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        data = fetch_data_sync()
        return _format_health(data)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_health(data)


def _format_health(data: dict) -> str:
    tokens = data.get("tokens", [])
    system = data.get("system", {})
    stats = data.get("stats", {})
    generated = data.get("generated_at", "unknown")

    lines = [f"Pythia Oracle — Health Report ({generated})\n"]

    incidents = stats.get("active_incidents", 0)
    lines.append(
        f"  *** {incidents} ACTIVE INCIDENT(S) ***\n"
        if incidents > 0
        else "  No active incidents.\n"
    )

    sources = system.get("sources", [])
    for s in sources:
        marker = " " if s["status"] == "ok" else "!"
        lines.append(f" {marker} {s['name']:<15} {s['status']}")
    lines.append("")

    lines.append(f"{'Token':<8} {'Uptime 30d':>10}  {'Status':<6}  {'Src':>3}")
    lines.append("-" * 40)
    for t in sorted(tokens, key=lambda x: x.get("uptime_30d", 0)):
        uptime = (
            f"{t['uptime_30d']:.1f}%"
            if t.get("uptime_30d") is not None
            else "?"
        )
        lines.append(
            f"{t['symbol']:<8} {uptime:>10}  "
            f"{t.get('status', '?'):<6}  {t.get('sources', '?'):>3}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: Contracts
# ---------------------------------------------------------------------------


class PythiaContractsTool(BaseTool):
    """Get Pythia contract addresses for on-chain integration."""

    name: str = "pythia_contracts"
    description: str = (
        "Get Pythia Oracle contract addresses on Polygon for smart contract "
        "integration. Returns operator, LINK token, faucet, and consumer "
        "contract addresses for all pricing tiers."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return json.dumps(CONTRACTS, indent=2)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return json.dumps(CONTRACTS, indent=2)


# ---------------------------------------------------------------------------
# Tool: Pricing
# ---------------------------------------------------------------------------


class PythiaPricingTool(BaseTool):
    """Get Pythia Oracle pricing tiers and free trial info."""

    name: str = "pythia_pricing"
    description: str = (
        "Get Pythia Oracle pricing tiers (Discovery 0.01 LINK, Analysis "
        "0.03, Speed 0.05, Complete 0.10) and free trial faucet info."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        return _PRICING_TEXT

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return _PRICING_TEXT


_PRICING_TEXT = """Pythia Oracle Pricing

  DISCOVERY — 0.01 LINK: Any single indicator. Returns uint256.
  ANALYSIS  — 0.03 LINK: All 1H/1D/1W indicators bundled. Returns uint256[].
  SPEED     — 0.05 LINK: All 5-minute indicators bundled. Returns uint256[].
  COMPLETE  — 0.10 LINK: Every indicator for a token. Returns uint256[].

  FREE TRIAL — PythiaFaucet (0x640fC3B9B607E324D7A3d89Fcb62C77Cc0Bd420A)
  No LINK needed. 5 requests/day/address. Real data.

  Website: https://pythia.c3x-solutions.com"""
