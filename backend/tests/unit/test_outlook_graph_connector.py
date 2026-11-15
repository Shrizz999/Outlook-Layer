"""
Unit Tests for Microsoft Graph Client & Recursive Folder Discovery.
Tests pagination, child folder traversal, well-known folder identification,
throttling with Retry-After backoff, and error handling.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from app.integrations.email_providers.graph_client import GraphAPIError, MicrosoftGraphClient


@pytest.mark.asyncio
async def test_recursive_folder_discovery():
    """Verify recursive folder discovery traverses root and child folders with hierarchy preserved."""
    client = MicrosoftGraphClient(access_token="mock_token")

    # Mock top-level and child folders
    top_level_resp = {
        "value": [
            {"id": "f_inbox", "displayName": "Inbox", "childFolderCount": 0, "totalItemCount": 42, "unreadItemCount": 3},
            {"id": "f_projects", "displayName": "Projects", "childFolderCount": 2, "totalItemCount": 10, "unreadItemCount": 0},
            {"id": "f_trash", "displayName": "Deleted Items", "childFolderCount": 0, "totalItemCount": 15, "unreadItemCount": 0},
        ],
        "@odata.nextLink": None,
    }

    child_resp = {
        "value": [
            {"id": "f_proj_a", "displayName": "Project Alpha", "childFolderCount": 0, "totalItemCount": 5, "unreadItemCount": 1},
            {"id": "f_proj_b", "displayName": "Project Beta", "childFolderCount": 0, "totalItemCount": 2, "unreadItemCount": 0},
        ],
        "@odata.nextLink": None,
    }

    async def mock_request(method, url, **kwargs):
        if "childFolders" in url:
            return child_resp
        return top_level_resp

    client._request = AsyncMock(side_effect=mock_request)

    folders = await client.discover_all_folders()

    # Total 5 folders (3 top-level + 2 child)
    assert len(folders) == 5

    inbox = next(f for f in folders if f["graph_folder_id"] == "f_inbox")
    assert inbox["well_known_name"] == "inbox"
    assert inbox["sync_enabled"] is True

    trash = next(f for f in folders if f["graph_folder_id"] == "f_trash")
    assert trash["well_known_name"] == "deleteditems"
    assert trash["is_system_folder"] is True
    assert trash["sync_enabled"] is False  # System trash disabled by default

    child_a = next(f for f in folders if f["graph_folder_id"] == "f_proj_a")
    assert child_a["parent_folder_id"] == "f_projects"
    assert child_a["display_name"] == "Project Alpha"


@pytest.mark.asyncio
async def test_graph_throttling_retry_after():
    """Verify Graph client handles HTTP 429 throttling and retries with backoff."""
    mock_http = AsyncMock()

    resp_429 = MagicMock(spec=httpx.Response)
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "1"}

    resp_200 = MagicMock(spec=httpx.Response)
    resp_200.status_code = 200
    resp_200.content = b'{"value": []}'
    resp_200.json.return_value = {"value": [{"id": "msg_001", "subject": "Test"}]}

    # First call returns 429, second call succeeds with 200
    mock_http.request.side_effect = [resp_429, resp_200]

    client = MicrosoftGraphClient(access_token="mock_token", http_client=mock_http)

    res = await client._request("GET", "/me/messages")
    assert "value" in res
    assert len(res["value"]) == 1
    assert mock_http.request.call_count == 2


@pytest.mark.asyncio
async def test_graph_error_parsing():
    """Verify Graph API error messages and status codes are parsed into GraphAPIError."""
    mock_http = AsyncMock()
    resp_404 = MagicMock(spec=httpx.Response)
    resp_404.status_code = 404
    resp_404.content = b'{"error": {"code": "ErrorItemNotFound", "message": "The specified object was not found."}}'
    resp_404.json.return_value = {"error": {"code": "ErrorItemNotFound", "message": "The specified object was not found."}}
    resp_404.text = "ErrorItemNotFound"

    mock_http.request.return_value = resp_404

    client = MicrosoftGraphClient(access_token="mock_token", http_client=mock_http)

    with pytest.raises(GraphAPIError) as excinfo:
        await client._request("GET", "/me/messages/missing-id")

    assert excinfo.value.status_code == 404
    assert excinfo.value.error_code == "ErrorItemNotFound"
    assert "not found" in str(excinfo.value).lower()
