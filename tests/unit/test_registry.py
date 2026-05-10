"""Unit tests for tool registry (T004 — must FAIL before implementation)."""

from pydantic import BaseModel

from src.tools.registry import (
    ToolDefinition,
    get_registry,
    get_tool,
    get_tool_descriptions,
)


class _FakeInput(BaseModel):
    order_id: str


class _FakeOutput(BaseModel):
    status: str


def _fake_fn(params: _FakeInput) -> _FakeOutput:
    return _FakeOutput(status="ok")


_FAKE_TOOL = ToolDefinition(
    name="fake_tool",
    description="A fake tool for testing",
    input_schema=_FakeInput,
    output_schema=_FakeOutput,
    risk_level="read-only",
    execute_fn=_fake_fn,
    rate_limit=10,
    dollar_cap=None,
    allowed_agents=["support"],
)


class TestToolDefinition:
    def test_dataclass_fields(self):
        assert _FAKE_TOOL.name == "fake_tool"
        assert _FAKE_TOOL.risk_level == "read-only"
        assert _FAKE_TOOL.dollar_cap is None
        assert _FAKE_TOOL.allowed_agents == ["support"]

    def test_execute_fn_callable(self):
        result = _FAKE_TOOL.execute_fn(_FakeInput(order_id="ORD-001"))
        assert isinstance(result, _FakeOutput)


class TestGetRegistry:
    def test_returns_dict(self):
        registry = get_registry()
        assert isinstance(registry, dict)

    def test_registered_tools_present(self):
        registry = get_registry()
        assert "order_status_lookup" in registry
        assert "create_support_ticket" in registry
        assert "issue_refund" in registry

    def test_values_are_tool_definitions(self):
        registry = get_registry()
        for tool in registry.values():
            assert isinstance(tool, ToolDefinition)


class TestGetTool:
    def test_returns_tool_by_name(self):
        tool = get_tool("order_status_lookup")
        assert tool is not None
        assert tool.name == "order_status_lookup"

    def test_returns_none_for_unknown(self):
        tool = get_tool("nonexistent_tool")
        assert tool is None


class TestGetToolDescriptions:
    def test_returns_list(self):
        descriptions = get_tool_descriptions()
        assert isinstance(descriptions, list)
        assert len(descriptions) >= 3

    def test_each_entry_has_required_keys(self):
        for desc in get_tool_descriptions():
            assert "name" in desc
            assert "description" in desc
            assert "parameters" in desc
            assert "risk_level" in desc

    def test_parameters_is_json_schema(self):
        for desc in get_tool_descriptions():
            params = desc["parameters"]
            assert isinstance(params, dict)
            assert "properties" in params or "type" in params

    def test_allow_list_filtering(self):
        descriptions = get_tool_descriptions(agent_type="support")
        for desc in descriptions:
            tool = get_tool(desc["name"])
            assert "support" in tool.allowed_agents
