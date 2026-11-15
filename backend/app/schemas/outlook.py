"""
Pydantic Schemas for Multi-User Microsoft Outlook Integration.
Defines typed request/response models for connections, folder hierarchy,
email synchronization, delta state, and admin overview.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OutlookOAuthInitResponse(BaseModel):
    authorization_url: str
    state: str
    authority: str
    scopes: list[str]


class MicrosoftConnectionRead(BaseModel):
    id: UUID
    employee_id: UUID
    microsoft_user_id: str
    tenant_id: str | None = None
    email_address: str
    display_name: str | None = None
    account_type: str  # 'organizational' or 'personal'
    granted_scopes: list[str] = Field(default_factory=list)
    connection_status: str  # 'active', 'expired', 'error', 'disconnected', 'reauth_required'
    connected_at: datetime
    last_synced_at: datetime | None = None
    last_error: str | None = None
    disconnected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Note: encrypted_token_cache is NEVER exposed in the API
    model_config = ConfigDict(from_attributes=True)


class MicrosoftConnectionStatus(BaseModel):
    is_connected: bool
    connection: MicrosoftConnectionRead | None = None
    requires_reauth: bool = False
    folder_count: int = 0
    message_count: int = 0
    last_synced_at: datetime | None = None
    sync_status: str = "idle"  # idle, syncing, completed, error
    last_error: str | None = None


class EmailFolderRead(BaseModel):
    id: UUID
    connection_id: UUID
    graph_folder_id: str
    parent_folder_id: str | None = None
    display_name: str
    well_known_name: str | None = None
    is_hidden: bool = False
    is_system_folder: bool = False
    sync_enabled: bool = True
    total_item_count: int = 0
    unread_item_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FolderSyncStateRead(BaseModel):
    id: UUID
    connection_id: UUID
    folder_id: UUID
    folder_name: str | None = None
    sync_status: str  # 'idle', 'syncing', 'completed', 'error', 'expired'
    last_successful_sync: datetime | None = None
    last_attempted_sync: datetime | None = None
    last_error: str | None = None
    has_delta_link: bool = False
    model_config = ConfigDict(from_attributes=True)


class EmailRecipient(BaseModel):
    name: str | None = None
    email: str


class EmailMessageRead(BaseModel):
    id: UUID
    connection_id: UUID
    employee_id: UUID
    folder_id: UUID | None = None
    folder_name: str | None = None
    graph_message_id: str
    internet_message_id: str | None = None
    conversation_id: str | None = None
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    recipients: list[EmailRecipient] = Field(default_factory=list)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    bcc_recipients: list[EmailRecipient] = Field(default_factory=list)
    reply_to_recipients: list[EmailRecipient] = Field(default_factory=list)
    received_at: datetime | None = None
    sent_at: datetime | None = None
    body_preview: str | None = None
    has_attachments: bool = False
    importance: str = "normal"
    is_read: bool = False
    is_draft: bool = False
    is_deleted: bool = False
    is_flagged: bool = False
    flag_status: str = "notFlagged"
    categories: list[str] = Field(default_factory=list)
    send_status: str = "synced"
    send_error: str | None = None
    in_reply_to_id: str | None = None
    idempotency_key: str | None = None
    web_link: str | None = None
    source: str = "MICROSOFT_GRAPH"
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmailMessageDetail(EmailMessageRead):
    body_content: str | None = None
    body_type: str = "html"
    last_modified_at: datetime | None = None
    content_hash: str | None = None
    attachments_metadata: list[dict[str, Any]] = Field(default_factory=list)


class SyncRunRead(BaseModel):
    id: UUID
    connection_id: UUID
    sync_type: str  # 'INITIAL', 'DELTA', 'MANUAL'
    status: str     # 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED'
    started_at: datetime
    completed_at: datetime | None = None
    messages_discovered: int = 0
    messages_inserted: int = 0
    messages_updated: int = 0
    messages_deleted: int = 0
    errors_count: int = 0
    error_summary: str | None = None
    model_config = ConfigDict(from_attributes=True)


class EmailAnalysisResultRead(BaseModel):
    id: UUID
    email_message_id: UUID
    analysis_status: str  # 'PENDING', 'COMPLETED', 'FAILED', 'SKIPPED'
    classification: str   # 'PERSONAL', 'BUSINESS', 'SENSITIVE', 'UNCLASSIFIED'
    business_relevance: str  # 'HIGH', 'MEDIUM', 'LOW', 'NONE', 'UNKNOWN'
    summary: str | None = None
    extracted_entities: dict[str, Any] = Field(default_factory=dict)
    extracted_actions: list[dict[str, Any]] = Field(default_factory=list)
    extracted_dates: list[dict[str, Any]] = Field(default_factory=list)
    extracted_commitments: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    human_review_status: str = "UNREVIEWED"
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SyncTriggerResponse(BaseModel):
    status: str
    sync_run_id: UUID
    connection_id: UUID
    message: str


class OutlookAdminOverview(BaseModel):
    total_employees: int
    connected_employees_count: int
    active_connections_count: int
    expired_connections_count: int
    failed_connections_count: int
    total_synchronized_messages: int
    total_discovered_folders: int
    last_sync_completed_at: datetime | None = None
    active_sync_jobs: int = 0
    recent_sync_runs: list[SyncRunRead] = Field(default_factory=list)


# =============================================================================
# Email Operations & Draft Schemas
# =============================================================================

class EmailComposeSendRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=1000)
    body_content: str = Field(default="")
    body_type: str = Field(default="html", pattern="^(html|text)$")
    to_recipients: list[EmailRecipient] = Field(..., min_length=1)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    bcc_recipients: list[EmailRecipient] = Field(default_factory=list)
    importance: str = Field(default="normal", pattern="^(low|normal|high)$")
    draft_id: UUID | None = None
    idempotency_key: str | None = None


class EmailReplyRequest(BaseModel):
    comment: str = Field(default="")
    reply_all: bool = False
    to_recipients: list[EmailRecipient] | None = None
    cc_recipients: list[EmailRecipient] | None = None
    idempotency_key: str | None = None


class EmailForwardRequest(BaseModel):
    to_recipients: list[EmailRecipient] = Field(..., min_length=1)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    comment: str = Field(default="")
    idempotency_key: str | None = None


class EmailDraftCreateUpdateRequest(BaseModel):
    id: UUID | None = None
    reply_to_message_id: UUID | None = None
    reply_mode: str = Field(default="new", pattern="^(new|reply|reply_all|forward)$")
    subject: str = Field(default="")
    to_recipients: list[EmailRecipient] = Field(default_factory=list)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    bcc_recipients: list[EmailRecipient] = Field(default_factory=list)
    body_content: str = Field(default="")
    body_type: str = Field(default="html", pattern="^(html|text)$")
    importance: str = Field(default="normal", pattern="^(low|normal|high)$")


class EmailDraftRead(BaseModel):
    id: UUID
    connection_id: UUID
    employee_id: UUID
    graph_draft_id: str | None = None
    reply_to_message_id: UUID | None = None
    reply_mode: str
    subject: str
    to_recipients: list[EmailRecipient] = Field(default_factory=list)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    bcc_recipients: list[EmailRecipient] = Field(default_factory=list)
    body_content: str
    body_type: str
    importance: str
    status: str
    last_saved_at: datetime
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmailUpdateFlagsRequest(BaseModel):
    is_flagged: bool | None = None
    flag_status: str | None = Field(None, pattern="^(flagged|notFlagged|complete)$")


class EmailUpdateReadRequest(BaseModel):
    is_read: bool


class EmailUpdateCategoriesRequest(BaseModel):
    categories: list[str] = Field(default_factory=list)


class EmailMoveRequest(BaseModel):
    destination_folder_id: str = Field(..., description="Target folder UUID or Graph folder ID")


class EmailSendAuditRead(BaseModel):
    id: UUID
    connection_id: UUID
    employee_id: UUID
    draft_id: UUID | None = None
    sent_message_id: UUID | None = None
    sender_email: str
    recipients: list[EmailRecipient] = Field(default_factory=list)
    cc_recipients: list[EmailRecipient] = Field(default_factory=list)
    bcc_recipients: list[EmailRecipient] = Field(default_factory=list)
    subject: str
    action_type: str
    idempotency_key: str
    status: str
    graph_internet_message_id: str | None = None
    error_message: str | None = None
    initiated_at: datetime
    completed_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class TodoTaskCreateRequest(BaseModel):
    task_id: UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    due_date: datetime | None = None
    notes: str | None = None
    importance: str = Field(default="normal", pattern="^(low|normal|high)$")
    list_id: str | None = None


class TodoTaskMappingRead(BaseModel):
    id: UUID
    task_id: UUID
    connection_id: UUID
    provider: str
    external_list_id: str
    external_task_id: str
    title: str
    due_date: datetime | None = None
    status: str
    external_url: str | None = None
    synced_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ConversationThreadRead(BaseModel):
    conversation_id: str
    message_count: int
    messages: list[EmailMessageDetail] = Field(default_factory=list)
