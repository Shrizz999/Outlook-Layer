# Known Limitations & Planned Extensions — Balbird Intelligence POC

## 1. Intentional POC Limitations

| Limitation | Impact | Planned Resolution in Production |
|---|---|---|
| **Synthetic Mailbox Only** | System runs on JSON/.eml fixtures rather than real Microsoft Graph Exchange Online mailbox. | Connect Microsoft Graph API after customer security review and tenant admin consent. |
| **No Automatic Email Sending** | Smart Drafts generate response previews and provide copy-to-clipboard, but do not send emails. | Customer requirement: outbound emails must remain human-reviewed in pilot phases. |
| **Immutable Spreadsheet Snapshots** | SO registers and MRP files are imported as read-only snapshot records; the system never modifies source workbooks. | Direct ERP/MRP bidirectional sync via certified connectors. |
| **Default MockAIProvider** | Offline tests use MockAIProvider; OpenRouter requires setting `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in `.env`. | Multi-provider fallback and Azure OpenAI enterprise integration. |
| **Local In-Memory Repository Fallback** | When `SUPABASE_URL` is omitted, the backend runs against an in-memory repository for offline test suite execution. | Live Supabase instance in production staging. |

---

## 2. Unresolved Customer Decisions

Refer to `docs/decisions/OPEN_QUESTIONS.md` for customer IT decisions currently pending:
- Target Azure subscription and resource groups.
- Specific Exchange Online mailbox for pilot observation.
- Final department code vocabulary and working day deadline calculations.
