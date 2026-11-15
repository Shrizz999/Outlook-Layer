import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.clear_all_data import clear_all
from app.services.email.train_data_service import TrainDataService
from app.services.tasks.workflow_engine import WorkflowCoordinationEngine
from app.repositories.email_repo import EmailRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.business_case_repo import BusinessCaseRepository

async def main():
    print("==================================================")
    print("STEP 1: Resetting all operational data...")
    print("==================================================")
    clear_all()
    print("Reset complete!")

    print("\n==================================================")
    print("STEP 2: Importing 2 emails per employee from Train Data...")
    print("==================================================")
    train_service = TrainDataService()
    res = await train_service.import_batch(batch_name="all", limit=2)
    print("Import summary:")
    print(f" - Ingested: {res.get('total_ingested')}")
    print(f" - Tasks created: {res.get('total_tasks_created')}")
    print(f" - Dependencies created: {res.get('total_dependencies_created')}")
    print(f" - Errors: {len(res.get('errors', []))}")
    if res.get('errors'):
        print(" Errors detail:", res.get('errors'))

    print("\n==================================================")
    print("STEP 3: Checking Ingested Emails & Attachments...")
    print("==================================================")
    email_repo = EmailRepository()
    messages = await email_repo.list_messages(limit=20)
    print(f"Total messages in system: {len(messages)}")
    for m in messages:
        sender = m.sender_address or m.sender_display_name
        has_att = m.has_attachments
        print(f" - Msg ID: {str(m.id)[:8]}... | Sender: {sender} | Subject: {m.subject[:40]} | Attachments: {has_att}")

    attachments = await email_repo.list_all_attachments()
    print(f"\nTotal attachments recorded: {len(attachments)}")
    for att in attachments[:5]:
        print(f" - File: {att.get('filename')} ({att.get('file_type')}, {att.get('file_size_bytes')} bytes) | Extracted Items: {len(att.get('extracted_line_items', []))}")

    print("\n==================================================")
    print("STEP 4: Checking Workflow & Active Bottlenecks...")
    print("==================================================")
    wf_engine = WorkflowCoordinationEngine()
    bottlenecks = await wf_engine.get_active_bottlenecks_across_cases()
    print(f"Active bottlenecks across all cases: {len(bottlenecks)}")
    for b in bottlenecks:
        print(f" * Case: {b.get('case_id')} | Stage {b.get('stage_number')}: {b.get('title')}")
        print(f"   Assignee: {b.get('assignee_name')} <{b.get('assignee_email')}> | Status: {b.get('status')}")

    print("\n==================================================")
    print("STEP 5: Checking Traceability of First Case...")
    print("==================================================")
    cases = await BusinessCaseRepository().list_cases(limit=5)
    if cases:
        c = cases[0]
        print(f"Examining Business Case: {c.case_number} ({c.title}) - ID: {c.id}")
        trace = await wf_engine.get_workflow_traceability(c.id)
        print(f" - Progress: {trace.get('completed_tasks')} / {trace.get('total_tasks')} tasks ({trace.get('progress_percentage')}%)")
        print(f" - Active Bottleneck: {trace.get('active_bottleneck')}")
        print(" - Workflow Timeline (first 5 stages):")
        for s in trace.get("timeline", [])[:5]:
            pred = f" [Predecessor: {s.get('predecessor_task_id')}]" if s.get('predecessor_task_id') else " [Initial Trigger]"
            print(f"   Task: {s.get('task_id')} | {s.get('description')[:40]} -> {s.get('status')} | Assignee: {s.get('assigned_to')}{pred}")

    print("\n==================================================")
    print("VERIFICATION COMPLETE!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
