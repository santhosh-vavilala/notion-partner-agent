from app.mcp.notion_client import is_write_tool

def test_write_detection():
    assert is_write_tool("notion-create-pages")
    assert is_write_tool("update-page")
    assert is_write_tool("issue_write")
    assert is_write_tool("create_issue")
    assert not is_write_tool("notion-search")
    assert not is_write_tool("fetch")
