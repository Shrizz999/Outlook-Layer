"""
Microsoft Graph API Client.
Handles authenticated Graph API requests, recursive folder discovery,
pagination, throttling (HTTP 429 Retry-After), and delta synchronization.
Supports live Microsoft Graph API requests as well as synthetic mock responses.
"""
from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import structlog

logger = structlog.get_logger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# Standard well-known folder names in Microsoft Graph
WELL_KNOWN_FOLDERS = {
    "inbox": "Inbox",
    "sentitems": "Sent Items",
    "drafts": "Drafts",
    "deleteditems": "Deleted Items",
    "junkemail": "Junk Email",
    "archive": "Archive",
    "outbox": "Outbox",
}


class GraphAPIError(Exception):
    def __init__(self, message: str, status_code: int = 500, error_code: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class MicrosoftGraphClient:
    def __init__(
        self,
        access_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.access_token = access_token
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client:
            return self._client
        return httpx.AsyncClient(timeout=45.0)

    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Execute an authenticated Microsoft Graph HTTP request with rate-limit / retry handling.
        Honors Retry-After headers on HTTP 429 and transient 503 errors.
        """
        full_url = url if url.startswith("https://") else f"{GRAPH_API_BASE}/{url.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Prefer": 'IdType="ImmutableId"',  # Keep message IDs stable across folder moves
        }

        client = await self._get_client()

        for attempt in range(max_retries):
            try:
                resp = await client.request(
                    method=method,
                    url=full_url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )

                if resp.status_code == 429 or resp.status_code == 503:
                    retry_after_sec = int(resp.headers.get("Retry-After", 2 ** attempt + 1))
                    logger.warning(
                        "Microsoft Graph throttled request; backing off",
                        status_code=resp.status_code,
                        retry_after=retry_after_sec,
                        attempt=attempt,
                    )
                    await asyncio.sleep(min(retry_after_sec, 30))
                    continue

                if resp.status_code >= 400:
                    err_json = {}
                    try:
                        err_json = resp.json()
                    except Exception:
                        pass
                    err_code = err_json.get("error", {}).get("code", "GraphError")
                    err_msg = err_json.get("error", {}).get("message", resp.text)
                    raise GraphAPIError(
                        message=f"Microsoft Graph error ({resp.status_code} {err_code}): {err_msg}",
                        status_code=resp.status_code,
                        error_code=err_code,
                    )

                return resp.json() if resp.content else {}

            except httpx.RequestError as exc:
                if attempt == max_retries - 1:
                    raise GraphAPIError(f"Network error communicating with Microsoft Graph: {str(exc)}")
                await asyncio.sleep(2 ** attempt)

        raise GraphAPIError("Max retries exceeded communicating with Microsoft Graph")

    # =========================================================================
    # User / Mailbox Identification
    # =========================================================================

    async def get_me(self) -> dict[str, Any]:
        """Get profile of authenticated user."""
        return await self._request("GET", "/me")

    # =========================================================================
    # Recursive Folder Discovery
    # =========================================================================

    async def discover_all_folders(self) -> list[dict[str, Any]]:
        """
        Recursively discover all accessible folders in the mailbox.
        Follows pagination and discovers child folders recursively.
        Preserves folder hierarchy with parent_folder_id.
        """
        all_folders: list[dict[str, Any]] = []

        # 1. Fetch top-level folders
        top_level = await self._fetch_folder_page("/me/mailFolders?$top=100")
        all_folders.extend(top_level)

        # 2. Recursively fetch child folders for every folder with childFolderCount > 0
        to_process = [f for f in top_level if f.get("childFolderCount", 0) > 0]
        while to_process:
            parent = to_process.pop(0)
            p_id = parent["id"]
            children = await self._fetch_folder_page(f"/me/mailFolders/{p_id}/childFolders?$top=100")
            for c in children:
                c["parent_folder_id"] = p_id
                all_folders.append(c)
                if c.get("childFolderCount", 0) > 0:
                    to_process.append(c)

        # Standardize folder structures
        normalized = []
        for f in all_folders:
            name = f.get("displayName", "Unnamed Folder")
            name_lower = name.lower()
            well_known = None
            for key, val in WELL_KNOWN_FOLDERS.items():
                if name_lower == key or name_lower == val.lower():
                    well_known = key
                    break

            is_system = well_known in ("deleteditems", "junkemail", "outbox")
            is_hidden = f.get("isHidden", False)

            # Sync is enabled by default except for trash/junk
            sync_enabled = not (well_known in ("deleteditems", "junkemail") or is_hidden)

            normalized.append({
                "graph_folder_id": f["id"],
                "parent_folder_id": f.get("parent_folder_id"),
                "display_name": name,
                "well_known_name": well_known,
                "is_hidden": is_hidden,
                "is_system_folder": is_system,
                "sync_enabled": sync_enabled,
                "total_item_count": f.get("totalItemCount", 0),
                "unread_item_count": f.get("unreadItemCount", 0),
            })

        return normalized

    async def _fetch_folder_page(self, url: str) -> list[dict[str, Any]]:
        folders: list[dict[str, Any]] = []
        next_url = url

        while next_url:
            data = await self._request("GET", next_url)
            values = data.get("value", [])
            folders.extend(values)
            next_url = data.get("@odata.nextLink")

        return folders

    # =========================================================================
    # Folder Message Synchronization (Initial & Paginated)
    # =========================================================================

    async def get_folder_messages(
        self,
        folder_id: str,
        top: int = 50,
        next_link: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        Fetch messages in a folder with pagination.
        Returns (messages, nextLink).
        """
        if next_link:
            url = next_link
            data = await self._request("GET", url)
        else:
            url = (
                f"/me/mailFolders/{folder_id}/messages"
                f"?$top={top}"
                f"&$select=id,internetMessageId,conversationId,subject,sender,from,toRecipients,ccRecipients,receivedDateTime,sentDateTime,body,bodyPreview,hasAttachments,importance,isRead,isDraft,webLink,lastModifiedDateTime"
                f"&$orderby=receivedDateTime desc"
            )
            data = await self._request("GET", url)

        messages = data.get("value", [])
        next_url = data.get("@odata.nextLink")
        return messages, next_url

    # =========================================================================
    # Continuous Delta Synchronization
    # =========================================================================

    async def get_folder_messages_delta(
        self,
        folder_id: str,
        delta_link: str | None = None,
        max_pages: int = 5,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        """
        Query folder changes via Microsoft Graph Delta Query.
        If delta_link is provided, continues from previous delta sync.
        Otherwise initiates fresh delta query.
        Returns: (changes_list, new_delta_link, intermediate_next_link).
        """
        url = delta_link or (
            f"/me/mailFolders/{folder_id}/messages/delta"
            f"?$select=id,internetMessageId,conversationId,subject,sender,from,toRecipients,ccRecipients,receivedDateTime,sentDateTime,body,bodyPreview,hasAttachments,importance,isRead,isDraft,webLink,lastModifiedDateTime"
        )

        all_changes: list[dict[str, Any]] = []
        new_delta_link = None
        next_link = url
        pages = 0

        while next_link and pages < max_pages:
            pages += 1
            data = await self._request("GET", next_link)
            items = data.get("value", [])
            all_changes.extend(items)

            new_delta = data.get("@odata.deltaLink")
            next_url = data.get("@odata.nextLink")

            if new_delta:
                new_delta_link = new_delta
                next_link = None
            else:
                next_link = next_url

        return all_changes, new_delta_link, next_link

    # =========================================================================
    # Email Client Operations: Send, Reply, Forward, Drafts, Flags, Moves
    # =========================================================================

    async def send_mail(self, message: dict[str, Any], save_to_sent_items: bool = True) -> dict[str, Any]:
        """
        Send a new email directly via /me/sendMail using delegated permissions.
        Message payload: {subject, body: {contentType, content}, toRecipients, ccRecipients, bccRecipients}
        """
        payload = {
            "message": message,
            "saveToSentItems": save_to_sent_items,
        }
        return await self._request("POST", "/me/sendMail", json_data=payload)

    async def create_draft(self, message: dict[str, Any]) -> dict[str, Any]:
        """
        Create a draft email in the user's Drafts folder.
        Returns the created draft message representation.
        """
        return await self._request("POST", "/me/messages", json_data=message)

    async def update_draft(self, graph_message_id: str, message: dict[str, Any]) -> dict[str, Any]:
        """Update fields of an existing draft message."""
        return await self._request("PATCH", f"/me/messages/{graph_message_id}", json_data=message)

    async def send_draft(self, graph_message_id: str) -> None:
        """Send a previously created draft message."""
        await self._request("POST", f"/me/messages/{graph_message_id}/send")

    async def create_reply_draft(self, graph_message_id: str, comment: str = "") -> dict[str, Any]:
        """Create a draft reply linked to an existing message."""
        payload = {"comment": comment} if comment else {}
        return await self._request("POST", f"/me/messages/{graph_message_id}/createReply", json_data=payload)

    async def create_reply_all_draft(self, graph_message_id: str, comment: str = "") -> dict[str, Any]:
        """Create a draft reply-all linked to an existing message."""
        payload = {"comment": comment} if comment else {}
        return await self._request("POST", f"/me/messages/{graph_message_id}/createReplyAll", json_data=payload)

    async def create_forward_draft(self, graph_message_id: str, comment: str = "") -> dict[str, Any]:
        """Create a draft forward linked to an existing message."""
        payload = {"comment": comment} if comment else {}
        return await self._request("POST", f"/me/messages/{graph_message_id}/createForward", json_data=payload)

    async def reply(self, graph_message_id: str, comment: str) -> None:
        """Direct reply to the sender of an existing message."""
        await self._request("POST", f"/me/messages/{graph_message_id}/reply", json_data={"comment": comment})

    async def reply_all(self, graph_message_id: str, comment: str) -> None:
        """Direct reply-all to all recipients of an existing message."""
        await self._request("POST", f"/me/messages/{graph_message_id}/replyAll", json_data={"comment": comment})

    async def forward(self, graph_message_id: str, to_recipients: list[dict[str, Any]], comment: str = "") -> None:
        """Forward an existing message to new recipients."""
        payload = {
            "comment": comment,
            "toRecipients": to_recipients,
        }
        await self._request("POST", f"/me/messages/{graph_message_id}/forward", json_data=payload)

    async def update_message(self, graph_message_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """
        Update message flags, categories, or read state.
        properties can include: isRead, flag: {flagStatus: 'flagged'|'notFlagged'}, categories: ['...']
        """
        return await self._request("PATCH", f"/me/messages/{graph_message_id}", json_data=properties)

    async def move_message(self, graph_message_id: str, destination_folder_id: str) -> dict[str, Any]:
        """Move a message to another folder."""
        payload = {"destinationId": destination_folder_id}
        return await self._request("POST", f"/me/messages/{graph_message_id}/move", json_data=payload)

    async def delete_message(self, graph_message_id: str) -> None:
        """Delete a message (moves to Deleted Items in Microsoft Graph)."""
        await self._request("DELETE", f"/me/messages/{graph_message_id}")

    # =========================================================================
    # Microsoft To Do Integration
    # =========================================================================

    async def list_todo_lists(self) -> list[dict[str, Any]]:
        """List To Do task lists for the user."""
        data = await self._request("GET", "/me/todo/lists")
        return data.get("value", [])

    async def create_todo_task(self, list_id: str, task_data: dict[str, Any]) -> dict[str, Any]:
        """Create a task in a Microsoft To Do list."""
        return await self._request("POST", f"/me/todo/lists/{list_id}/tasks", json_data=task_data)
