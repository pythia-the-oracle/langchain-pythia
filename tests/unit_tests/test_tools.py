"""Unit tests for Pythia Oracle LangChain tools."""

from langchain_pythia import (
    PythiaListTokensTool,
    PythiaTokenFeedsTool,
    PythiaHealthCheckTool,
    PythiaContractsTool,
    PythiaPricingTool,
)


def test_tool_names():
    """Each tool has a unique, descriptive name."""
    tools = [
        PythiaListTokensTool(),
        PythiaTokenFeedsTool(),
        PythiaHealthCheckTool(),
        PythiaContractsTool(),
        PythiaPricingTool(),
    ]
    names = [t.name for t in tools]
    assert len(names) == len(set(names)), "Tool names must be unique"
    for name in names:
        assert name.startswith("pythia_"), f"Tool name should start with pythia_: {name}"


def test_tool_descriptions():
    """Each tool has a non-empty description."""
    tools = [
        PythiaListTokensTool(),
        PythiaTokenFeedsTool(),
        PythiaHealthCheckTool(),
        PythiaContractsTool(),
        PythiaPricingTool(),
    ]
    for tool in tools:
        assert len(tool.description) > 20, f"Description too short for {tool.name}"


def test_contracts_tool_returns_json():
    """Contracts tool returns valid JSON with expected keys."""
    import json

    tool = PythiaContractsTool()
    result = tool._run()
    data = json.loads(result)
    assert "operator" in data
    assert "faucet" in data
    assert "consumers" in data
    assert "discovery" in data["consumers"]


def test_pricing_tool_returns_tiers():
    """Pricing tool mentions all 4 tiers."""
    tool = PythiaPricingTool()
    result = tool._run()
    assert "DISCOVERY" in result
    assert "ANALYSIS" in result
    assert "SPEED" in result
    assert "COMPLETE" in result
    assert "FREE TRIAL" in result


def test_token_feeds_input_schema():
    """Token feeds tool has proper input schema."""
    tool = PythiaTokenFeedsTool()
    schema = tool.args_schema.model_json_schema()
    assert "engine_id" in schema["properties"]
