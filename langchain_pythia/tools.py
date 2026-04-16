"""Pythia Oracle tools for LangChain.

Provides access to on-chain calculated crypto indicators (EMA, RSI,
Bollinger Bands, Volatility) for 22+ tokens via Chainlink across
supported networks. Includes Pythia Events (indicator alert subscriptions).
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
# Constants & helpers
# ---------------------------------------------------------------------------

FAUCET_ADDRESS = "0x640fC3B9B607E324D7A3d89Fcb62C77Cc0Bd420A"

_TIER_RETURNS = {
    "discovery": "uint256 (single indicator)",
    "analysis": "uint256[] (1H/1D/1W bundle)",
    "speed": "uint256[] (5M bundle)",
    "complete": "uint256[] (all indicators)",
}

_FALLBACK_PRICING = {
    "discovery": 0.01,
    "analysis": 0.03,
    "speed": 0.05,
    "complete": 0.10,
}

_FALLBACK_CONTRACTS = {
    "polygon_mainnet": {
        "display_name": "Polygon PoS",
        "chain_id": 137,
        "explorer": "https://polygonscan.com",
        "operator": "0xAA37710aF244514691629Aa15f4A5c271EaE6891",
        "link_token": "0xb0897686c545045aFc77CF20eC7A532E3120E0F1",
        "consumers": {
            "discovery": "0xeC2865d66ae6Af47926B02edd942A756b394F820",
            "analysis": "0x3b3aC62d73E537E3EF84D97aB5B84B51aF8dB316",
            "speed": "0xC406e7d9AC385e7AB43cBD56C74ad487f085d47B",
            "complete": "0x2dEC98fd7173802b351d1E28d0Cd5DdD20C24252",
        },
    },
}

_CONDITION_NAMES = {0: "ABOVE", 1: "BELOW", 2: "CROSSES_ABOVE", 3: "CROSSES_BELOW"}

# Fallback Visions data — offline resilience (static backtest results 2017-2026)
_VISIONS_REGISTRY = "0x39407eEc3Ba80746BC6156eD924D16C2689533Ed"
_VISIONS_PATTERNS = [
    {"name": "CAPITULATION_STRONG", "code": "0x11", "accuracy": "85-87%", "avg_return": "+7-8%", "sample": 62},
    {"name": "CAPITULATION_BOUNCE", "code": "0x10", "accuracy": "80%", "avg_return": "+5-7%", "sample": 78},
    {"name": "EMA_DIVERGENCE_STRONG", "code": "0x21", "accuracy": "89%", "avg_return": "+6%", "sample": 36},
    {"name": "EMA_DIVERGENCE_SNAP", "code": "0x20", "accuracy": "74-80%", "avg_return": "+4-5%", "sample": 67},
    {"name": "BOLLINGER_EXTREME", "code": "0x30", "accuracy": "74%", "avg_return": "+3-4%", "sample": 38},
    {"name": "OVERBOUGHT_CONTINUATION", "code": "0x40", "accuracy": "60-65%", "avg_return": "+1-2%", "sample": 127},
]


def _parse_consumers(raw: dict) -> dict[str, str]:
    """Convert {"Discovery (0.01 LINK)": "0x..."} → {"discovery": "0x..."}."""
    parsed = {}
    for display_name, address in raw.items():
        tier = display_name.split()[0].lower() if display_name else ""
        if tier and address:
            parsed[tier] = address
    return parsed


def _get_contracts(data: dict | None = None) -> dict:
    """Get normalized contracts from feed-status.json, or fallback."""
    if data and "developer" in data and "contracts" in data["developer"]:
        result = {}
        for chain_key, chain_data in data["developer"]["contracts"].items():
            result[chain_key] = {
                "display_name": chain_data.get("display_name", chain_key),
                "chain_id": chain_data.get("chain_id"),
                "explorer": chain_data.get("explorer", ""),
                "operator": chain_data.get("operator", ""),
                "link_token": chain_data.get("link_token", ""),
                "consumers": _parse_consumers(chain_data.get("consumers", {})),
            }
        if result:
            return result
    return _FALLBACK_CONTRACTS.copy()


def _get_mainnet(data: dict | None = None) -> dict:
    """Get polygon_mainnet contracts entry."""
    contracts = _get_contracts(data)
    return contracts.get("polygon_mainnet", next(iter(contracts.values())))


def _get_tier_fees(data: dict | None = None) -> dict:
    """Extract tier fees from feed-status.json data, or return fallback."""
    if data and "tiers" in data:
        return {t["id"]: t["fee"] for t in data["tiers"] if "id" in t and "fee" in t}
    return _FALLBACK_PRICING.copy()


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
        "contract addresses with live pricing for all tiers."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        data = fetch_data_sync()
        return _format_contracts(data)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_contracts(data)


def _format_contracts(data: dict) -> str:
    all_contracts = _get_contracts(data)
    fees = _get_tier_fees(data)
    events = data.get("events", {}) if data else {}
    result = {"faucet": FAUCET_ADDRESS, "chains": {}}
    for chain_key, chain in all_contracts.items():
        consumers = {}
        for tier in ("discovery", "analysis", "speed", "complete"):
            addr = chain["consumers"].get(tier)
            if addr:
                consumers[tier] = {
                    "address": addr,
                    "returns": _TIER_RETURNS.get(tier, "?"),
                    "fee": f"{fees.get(tier, '?')} LINK",
                }
        result["chains"][chain_key] = {
            "display_name": chain["display_name"],
            "chain_id": chain["chain_id"],
            "operator": chain["operator"],
            "link_token": chain["link_token"],
            "consumers": consumers,
        }
    registries = events.get("registries", [])
    if registries:
        result["event_registries"] = {r["chain"]: r["address"] for r in registries}
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: Pricing
# ---------------------------------------------------------------------------


class PythiaPricingTool(BaseTool):
    """Get Pythia Oracle pricing tiers and free trial info."""

    name: str = "pythia_pricing"
    description: str = (
        "Get Pythia Oracle pricing tiers and free trial faucet info. "
        "Prices are live from the data feed."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        data = fetch_data_sync()
        return _format_pricing(data)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_pricing(data)


def _format_pricing(data: dict) -> str:
    fees = _get_tier_fees(data)
    d = fees.get("discovery", "?")
    a = fees.get("analysis", "?")
    s = fees.get("speed", "?")
    c = fees.get("complete", "?")
    return f"""Pythia Oracle Pricing

  DISCOVERY — {d} LINK: Any single indicator. Returns uint256.
  ANALYSIS  — {a} LINK: All 1H/1D/1W indicators bundled. Returns uint256[].
  SPEED     — {s} LINK: All 5-minute indicators bundled. Returns uint256[].
  COMPLETE  — {c} LINK: Every indicator for a token. Returns uint256[].

  FREE TRIAL — PythiaFaucet ({FAUCET_ADDRESS})
  No LINK needed. 5 requests/day/address. Real data.

  Website: https://pythia.c3x-solutions.com"""


# ---------------------------------------------------------------------------
# Tool: Events Info
# ---------------------------------------------------------------------------


class PythiaEventsInfoTool(BaseTool):
    """Get overview of Pythia Events — on-chain indicator alert subscriptions."""

    name: str = "pythia_events_info"
    description: str = (
        "Get overview of Pythia Events: on-chain indicator alert subscriptions. "
        "Returns pricing, conditions (ABOVE/BELOW), registry addresses, "
        "subscriber flow, and current stats."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        data = fetch_data_sync()
        return _format_events_info(data)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_events_info(data)


def _format_events_info(data: dict) -> str:
    events = data.get("events", {}) if data else {}
    if not events:
        return ("Pythia Events info not available. "
                "Visit https://pythia.c3x-solutions.com for details.")

    lines = ["Pythia Events — On-Chain Indicator Alerts\n"]
    lines.append("Subscribe once, get notified when your condition is met.")
    lines.append("One-shot: fires once, remaining whole days refunded in LINK.\n")

    lines.append(f"Pricing: {events.get('pricing', '?')}")
    lines.append(f"Max duration: {events.get('max_days', 365)} days")
    lines.append(f"Threshold scale: {events.get('threshold_scale', '?')}")
    lines.append(f"Refund policy: {events.get('refund', '?')}\n")

    conditions = events.get("conditions", {})
    for c in conditions.get("active", []):
        lines.append(f"  {c}  [active]")
    for c in conditions.get("future", []):
        lines.append(f"  {c}  [future — accepted, not yet processed]")
    lines.append("")

    lines.append("Subscriber Flow:")
    for i, step in enumerate(events.get("subscriber_flow", []), 1):
        lines.append(f"  {i}. {step}")
    lines.append("")

    registries = events.get("registries", [])
    if registries:
        lines.append("Registry Contracts:")
        for reg in registries:
            lines.append(f"  {reg['chain']}: {reg['address']}")
        lines.append("")

    stats = events.get("stats", {})
    lines.append(
        f"Stats: {stats.get('active_subscriptions', 0)} active / "
        f"{stats.get('total_subscriptions', 0)} total subscriptions"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: Subscribe Info
# ---------------------------------------------------------------------------


class _SubscribeInfoInput(BaseModel):
    feed_name: str = Field(
        description="Feed name to monitor, e.g. 'pol_RSI_5M_14', 'bitcoin_EMA_1H_20'"
    )
    condition: int = Field(
        default=1,
        description="0=ABOVE, 1=BELOW, 2=CROSSES_ABOVE, 3=CROSSES_BELOW",
    )
    days: int = Field(default=7, description="Subscription duration in days (1-365)")


class PythiaSubscribeInfoTool(BaseTool):
    """Plan a specific Pythia Events subscription with cost and exact calls."""

    name: str = "pythia_subscribe_info"
    description: str = (
        "Plan a specific Pythia Events subscription. Returns cost calculation, "
        "registry addresses, exact Solidity calls, threshold scaling guide, "
        "and refund policy for a given feed, condition, and duration."
    )
    args_schema: Type[BaseModel] = _SubscribeInfoInput

    def _run(
        self,
        feed_name: str,
        condition: int = 1,
        days: int = 7,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        data = fetch_data_sync()
        return _format_subscribe_info(data, feed_name, condition, days)

    async def _arun(
        self,
        feed_name: str,
        condition: int = 1,
        days: int = 7,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_subscribe_info(data, feed_name, condition, days)


def _format_subscribe_info(
    data: dict, feed_name: str, condition: int, days: int
) -> str:
    if condition < 0 or condition > 3:
        return "Invalid condition. Use: 0=ABOVE, 1=BELOW, 2=CROSSES_ABOVE, 3=CROSSES_BELOW"
    if days < 1 or days > 365:
        return "Days must be 1-365."

    events = data.get("events", {}) if data else {}
    mainnet = _get_mainnet(data)
    cond_name = _CONDITION_NAMES.get(condition, "UNKNOWN")
    registries = events.get("registries", [])

    lines = [f"Pythia Events — Subscription Plan\n"]
    lines.append(f"  Feed:      {feed_name}")
    lines.append(f"  Condition: {cond_name} ({condition})")
    lines.append(f"  Duration:  {days} days")
    lines.append(f"  Cost:      {days} LINK ({events.get('pricing', '1 LINK/day')})")

    if condition >= 2:
        lines.append(f"\n  WARNING: {cond_name} is accepted but not yet processed.")

    lines.append(f"\n  Threshold: scaled to 8 decimals.")
    lines.append("  Examples: RSI 30 → 3000000000, RSI 70 → 7000000000")
    lines.append(f"            EMA $2500 → 250000000000, Vol 5% → 500000000")

    lines.append("\nExact Calls:\n")
    lines.append(f'  LINK.approve(registry, {days} * 1e18);')
    lines.append(f'  registry.subscribe("{feed_name}", {days}, {condition}, YOUR_THRESHOLD);')

    if registries:
        lines.append("\nRegistry Addresses:")
        for reg in registries:
            lines.append(f"  {reg['chain']}: {reg['address']}")

    lines.append(f"\nLINK Token (mainnet): {mainnet['link_token']}")
    lines.append(f"Refund: {events.get('refund', 'unused whole days refunded')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: Visions Info
# ---------------------------------------------------------------------------


class PythiaVisionsInfoTool(BaseTool):
    """Get overview of Pythia Visions — AI-calibrated market intelligence on-chain."""

    name: str = "pythia_visions_info"
    description: str = (
        "Get overview of Pythia Visions: AI-calibrated market intelligence. "
        "Returns 6 backtested patterns with accuracy (74-89%), contract address, "
        "subscription info (FREE), evaluation frequency, integration guide, "
        "and Solidity code for subscribing to VisionFired events."
    )

    def _run(
        self, run_manager: Optional[CallbackManagerForToolRun] = None
    ) -> str:
        data = fetch_data_sync()
        return _format_visions_info(data)

    async def _arun(
        self, run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_visions_info(data)


def _format_visions_info(data: dict) -> str:
    visions = data.get("visions", {}) if data else {}

    registry = visions.get("registry", _VISIONS_REGISTRY)
    patterns = visions.get("patterns", _VISIONS_PATTERNS)
    tokens = visions.get("tokens", ["BTC"])
    stats = visions.get("stats", {})

    lines = ["Pythia Visions — AI Market Intelligence On-Chain\n"]
    lines.append(
        "Backtested, AI-calibrated pattern detections delivered on-chain via "
        "Chainlink. Evaluated every 6 hours. FREE to subscribe."
    )
    lines.append("")

    lines.append("Detected Patterns (validated 2017-2026, 75K+ candles):\n")
    for p in patterns:
        lines.append(
            f"  {p['name']:<28} {p['code']:<6} "
            f"{p['accuracy']:<10} {p['avg_return']:<12} {p['sample']} samples"
        )
    lines.append("")

    lines.append("How It Works:")
    lines.append("  1. Every 6h: read live indicators (EMA, RSI, Bollinger, VWAP, ATR)")
    lines.append("  2. Mechanical pattern detection checks 6 known patterns")
    lines.append("  3. If pattern found: Claude Haiku calibrates confidence (55-89)")
    lines.append("  4. Vision fires on-chain via Chainlink webhook")
    lines.append("  5. Subscribers receive VisionFired event with full payload")
    lines.append("")

    lines.append(f"Vision Registry: {registry}")
    lines.append(f"Chain: Polygon PoS (mainnet)")
    lines.append(f"Subscription fee: FREE")
    lines.append(f"Tokens: {', '.join(tokens)}")
    lines.append(f"Signal frequency: ~30 Visions/year for BTC")
    lines.append("")

    if stats.get("total_fired"):
        lines.append(f"Stats: {stats['total_fired']} total fired, "
                     f"avg confidence {stats.get('avg_confidence', 'N/A')}")
        lines.append("")

    # Include integration guide (LangChain combines info + guide)
    lines.append("Integration:\n")
    lines.append("```solidity")
    lines.append("interface IPythiaVisionRegistry {")
    lines.append("    function subscribe(bytes32 tokenId) external;")
    lines.append("    function unsubscribe(bytes32 tokenId) external;")
    lines.append("    function isSubscribed(address, bytes32) external view returns (bool);")
    lines.append("}")
    lines.append("")
    lines.append("// Token IDs: keccak256 of token name")
    lines.append('// BTC = keccak256("BTC")')
    lines.append(f"// Registry: {registry}")
    lines.append("```")
    lines.append("")
    lines.append("Pattern Types in VisionFired event:")
    lines.append("  0x11=CAPITULATION_STRONG, 0x10=CAPITULATION_BOUNCE")
    lines.append("  0x21=EMA_DIVERGENCE_STRONG, 0x20=EMA_DIVERGENCE_SNAP")
    lines.append("  0x30=BOLLINGER_EXTREME, 0x40=OVERBOUGHT_CONTINUATION")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: Vision History
# ---------------------------------------------------------------------------


class _VisionHistoryInput(BaseModel):
    token: str = Field(
        default="BTC",
        description="Token symbol to check Visions for, e.g. 'BTC'",
    )


class PythiaVisionHistoryTool(BaseTool):
    """Get recent Pythia Visions fired for a token with pattern breakdown."""

    name: str = "pythia_vision_history"
    description: str = (
        "Get recent Pythia Visions fired for a token. Returns pattern "
        "detections with confidence, direction, price, and pattern breakdown."
    )
    args_schema: Type[BaseModel] = _VisionHistoryInput

    def _run(
        self,
        token: str = "BTC",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        data = fetch_data_sync()
        return _format_vision_history(data, token)

    async def _arun(
        self,
        token: str = "BTC",
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await fetch_data()
        return _format_vision_history(data, token)


def _format_vision_history(data: dict, token: str) -> str:
    visions = data.get("visions", {}) if data else {}

    if not visions:
        return ("Pythia Visions data not available yet. "
                "Use pythia_visions_info for pattern details and contract address.")

    recent = visions.get("recent", [])
    stats = visions.get("stats", {})
    registry = visions.get("registry", _VISIONS_REGISTRY)
    token_upper = token.upper()

    filtered = [v for v in recent if v.get("token", "").upper() == token_upper]

    lines = [f"Pythia Visions — {token_upper} History\n"]
    lines.append(f"Registry: {registry}")
    lines.append(f"Subscription: FREE\n")

    if not filtered:
        lines.append(f"No Visions have fired for {token_upper} yet.")
        lines.append(f"\nAvailable tokens: {', '.join(visions.get('tokens', []))}")
        return "\n".join(lines)

    lines.append(f"Recent Visions ({len(filtered)} shown):\n")
    for v in filtered:
        lines.append(f"  {v.get('fired_at', '?')}")
        lines.append(f"    Pattern:    {v.get('pattern_name', '?')}")
        lines.append(f"    Confidence: {v.get('confidence', '?')}")
        lines.append(f"    Direction:  {v.get('direction', '?')}")
        lines.append(f"    Price:      ${v.get('price_usd', 0):,.2f}")
        lines.append("")

    # Pattern breakdown
    pattern_counts: dict[str, list[int]] = {}
    for v in filtered:
        name = v.get("pattern_name", "?")
        conf = v.get("confidence", 0)
        if name not in pattern_counts:
            pattern_counts[name] = []
        pattern_counts[name].append(conf)

    lines.append("Pattern Breakdown:\n")
    for name, confs in sorted(pattern_counts.items(), key=lambda x: -len(x[1])):
        avg = sum(confs) / len(confs) if confs else 0
        lines.append(f"  {name:<28} {len(confs)} fires, avg confidence {avg:.1f}")
    lines.append("")

    if stats.get("total_fired"):
        lines.append(f"Overall: {stats['total_fired']} total fired, "
                     f"avg confidence {stats.get('avg_confidence', 'N/A')}")
    return "\n".join(lines)
