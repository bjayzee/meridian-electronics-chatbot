from types import SimpleNamespace

from mcp.types import CallToolResult, TextContent

from meridian_support.mcp_bridge import (
    call_tool_result_to_text,
    mcp_tool_to_openai_function,
)


def test_call_tool_result_to_text_plain() -> None:
    r = CallToolResult(content=[TextContent(type="text", text="hello")], isError=False)
    assert call_tool_result_to_text(r) == "hello"


def test_call_tool_result_error_flag() -> None:
    r = CallToolResult(content=[TextContent(type="text", text="bad")], isError=True)
    assert "[tool error]" in call_tool_result_to_text(r)


def test_mcp_tool_to_openai_function() -> None:
    tool = SimpleNamespace(
        name="get_product",
        description="Get SKU",
        inputSchema={
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    )
    out = mcp_tool_to_openai_function(tool)
    assert out["type"] == "function"
    assert out["function"]["name"] == "get_product"
    assert out["function"]["parameters"]["properties"]["sku"]["type"] == "string"


def test_redact_sensitive_tool_args_logged_via_safe_path() -> None:
    from meridian_support.mcp_bridge import _redact_tool_args

    assert _redact_tool_args("verify_customer_pin", {"email": "a@b.com", "pin": "1234"})[
        "pin"
    ] == "**redacted**"
    assert _redact_tool_args("get_product", {"sku": "x"})["sku"] == "x"
