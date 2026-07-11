from hive_web_runtime.mcp_server.tools import tool_names


def test_mcp_exports_static_and_action_namespaces():
    names = set(tool_names())
    assert "static_web_search" in names
    assert "static_web_extract" in names
    assert "action_web_session_create" in names
    assert "action_web_navigate" in names
    assert "action_web_snapshot" in names
    assert "action_web_close" in names
