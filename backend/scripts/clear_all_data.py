"""Script to clear all emails, tasks, proposals, dependencies, and business cases."""
import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.repositories.store import get_store, get_supabase_client

def clear_all():
    print("Clearing in-memory store...")
    store = get_store()
    store.clear()
    print("In-memory store cleared.")

    client = get_supabase_client()
    if not client:
        print("No live Supabase client configured. Only in-memory store cleared.")
        return

    print("Live Supabase client detected. Clearing tables in safe dependency order...")
    # List of tables to clear in reverse foreign key order
    tables_to_clear = [
        "bi_physical_verifications",
        "bi_task_handovers",
        "bi_dependencies",
        "task_dependencies",
        "bi_task_assignment_history",
        "bi_task_updates",
        "bi_task_metadata",
        "bi_task_sources",
        "bi_task_proposals",
        "tasks",
        "task_history",
        "workflows",
        "bi_monitoring_alerts",
        "bi_smart_drafts",
        "bi_case_links",
        "bi_case_parties",
        "bi_business_cases",
        "bi_commitments",
        "bi_extracted_facts",
        "bi_email_analyses",
        "bi_source_attachments",
        "bi_source_messages",
        "bi_conversations",
        "bi_sales_order_lines",
        "bi_sales_orders",
        "bi_rfq_lines",
        "bi_rfqs",
        "bi_mrp_records",
        "bi_mrp_snapshots",
        "bi_purchase_order_lines",
        "bi_purchase_order_ext",
        "bi_review_queue",
        "bi_imports",
        "bi_ai_usage",
    ]

    for tbl in tables_to_clear:
        try:
            # Delete all rows where id is not null (or task_id is not null)
            # In Supabase/PostgREST, we can use neq("id", "00000000-0000-0000-0000-000000000000")
            # or for tasks neq("task_id", "")
            id_col = "task_id" if tbl in ("tasks", "task_history") else ("workflow_id" if tbl == "workflows" else "id")
            client.table(tbl).delete().neq(id_col, "00000000-0000-0000-0000-000000000000").execute()
            print(f"Cleared table: {tbl}")
        except Exception as exc:
            # Some tables might not exist or might use a different filter
            try:
                client.table(tbl).delete().gt("created_at", "1970-01-01").execute()
                print(f"Cleared table: {tbl} (via created_at)")
            except Exception as e2:
                print(f"Note: {tbl}: {exc} / {e2}")

    print("All system operational data cleared successfully!")

if __name__ == "__main__":
    clear_all()
