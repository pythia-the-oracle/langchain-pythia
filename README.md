# langchain-pythia

[![PyPI](https://img.shields.io/pypi/v/langchain-pythia)](https://pypi.org/project/langchain-pythia/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LangChain integration for Pythia Oracle — on-chain calculated crypto indicators via Chainlink.**

Access EMA, RSI, Bollinger Bands, Volatility, and more for 22 crypto tokens directly from your LangChain agents. Pythia is the first oracle delivering calculated technical indicators on-chain, not just prices. Includes Pythia Events (indicator alert subscriptions) and Pythia Visions (AI-calibrated market intelligence).

## Installation

```bash
pip install langchain-pythia
```

## Quick Start

```python
from langchain_pythia import PythiaListTokensTool, PythiaTokenFeedsTool

# Use with any LangChain agent
tools = [PythiaListTokensTool(), PythiaTokenFeedsTool()]

# Or call directly
list_tool = PythiaListTokensTool()
print(list_tool.invoke(""))

feeds_tool = PythiaTokenFeedsTool()
print(feeds_tool.invoke({"engine_id": "bitcoin"}))
```

## With a LangChain Agent

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_pythia import (
    PythiaListTokensTool,
    PythiaTokenFeedsTool,
    PythiaHealthCheckTool,
    PythiaContractsTool,
    PythiaPricingTool,
    PythiaEventsInfoTool,
    PythiaSubscribeInfoTool,
    PythiaVisionsInfoTool,
    PythiaVisionHistoryTool,
)

tools = [
    PythiaListTokensTool(),
    PythiaTokenFeedsTool(),
    PythiaHealthCheckTool(),
    PythiaContractsTool(),
    PythiaPricingTool(),
    PythiaEventsInfoTool(),
    PythiaSubscribeInfoTool(),
    PythiaVisionsInfoTool(),
    PythiaVisionHistoryTool(),
]

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, tools)

# Ask about on-chain indicators
response = agent.invoke(
    {"messages": [{"role": "user", "content": "What RSI feeds does Pythia have for Bitcoin?"}]}
)
```

## Available Tools

| Tool | Description |
|------|-------------|
| `PythiaListTokensTool` | List every tracked token with status, uptime, and data sources |
| `PythiaTokenFeedsTool` | Get all indicator feed names (EMA, RSI, Bollinger, Volatility) for a token |
| `PythiaHealthCheckTool` | Per-token 30-day uptime, data source health, incident report |
| `PythiaContractsTool` | Contract addresses (operator, consumers, faucet, LINK) for on-chain integration |
| `PythiaPricingTool` | Current pricing tiers and free trial faucet info |
| `PythiaEventsInfoTool` | Pythia Events overview — indicator alert subscriptions |
| `PythiaSubscribeInfoTool` | Plan a specific event subscription with cost and exact calls |
| `PythiaVisionsInfoTool` | Pythia Visions overview — current pattern catalog, accuracy ranges, integration guide |
| `PythiaVisionHistoryTool` | Recent Visions fired for a token with pattern breakdown |

## What Pythia Provides

- **A growing catalog of indicator feeds across multiple tokens** — for the live token list and feed count, run `PythiaListTokensTool` or fetch [`feed-status.json`](https://pythia.c3x-solutions.com/feed-status.json)
- **Indicator types:** EMA, RSI, Bollinger Bands, VWAP, Volatility, USD Price (catalog evolves; `PythiaTokenFeedsTool` returns the active list per token)
- **Timeframes:** 5-minute, 1-hour, 1-day, 1-week
- **On-chain delivery** via Chainlink
- **Free trial** via PythiaFaucet — no LINK needed
- **Pythia Events:** Subscribe to indicator conditions (ABOVE/BELOW thresholds), get triggered on-chain
- **Pythia Visions:** AI-calibrated market intelligence on-chain — walk-forward validated patterns, FREE. Live catalog via `PythiaVisionsInfoTool`.

## Use Cases

- **AI trading agents** that need on-chain technical signals
- **DeFi vault rebalancing** based on RSI or volatility thresholds
- **Risk management** using Bollinger Band width
- **Portfolio analysis** with real-time calculated metrics

## Related

- [Pythia MCP Server](https://pypi.org/project/pythia-oracle-mcp/) — MCP integration for Claude, Cursor, VS Code
- [Integration Examples](https://github.com/pythia-the-oracle/pythia-oracle-examples) — Solidity contracts with Hardhat
- [Website & Feed Explorer](https://pythia.c3x-solutions.com)

## License

MIT
