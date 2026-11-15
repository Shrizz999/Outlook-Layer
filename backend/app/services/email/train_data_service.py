"""Train Data Batch Ingestion & Manufacturing Workflow Orchestration Service.

Ingests test dataset fixtures from `Train Data` covering:
- Swapnali: Enquiry registration & quotation coordination (100 .eml files)
- Ganesh: Part checking, OEM cross-references & PO verification (100 .eml files + 24 attachments)
- Vaibhav: SO booking, capacity planning & cross-department coordination (38 .eml files + 9 attachments)

Coordinates attachments, line item extraction, 13-stage manufacturing workflow task creation,
and sequential blocking dependencies automatically without human intervention.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

from app.integrations.email_providers.fixture_provider import FixtureEmailProvider, RawMessage
from app.repositories.business_case_repo import BusinessCaseRepository
from app.repositories.email_repo import EmailRepository
from app.repositories.task_repo import TaskRepository
from app.services.email.ingestion import EmailIngestionService
from app.services.tasks.workflow_engine import WorkflowCoordinationEngine

logger = structlog.get_logger(__name__)


class TrainDataService:
    def __init__(
        self,
        base_dir: str | Path = "Train Data",
        email_repo: EmailRepository | None = None,
        ingestion_service: EmailIngestionService | None = None,
    ) -> None:
        base_path = Path(base_dir)
        if not base_path.exists():
            for cand in [
                Path("../Train Data"),
                Path(__file__).resolve().parents[4] / "Train Data",
                Path(__file__).resolve().parents[3] / "Train Data",
            ]:
                if cand.exists():
                    base_path = cand
                    break
        self.base_dir = base_path
        self.email_repo = email_repo or EmailRepository()
        self.ingestion_service = ingestion_service or EmailIngestionService(email_repo=self.email_repo, auto_analyse=True)
        self.provider = FixtureEmailProvider()
        self.task_repo = TaskRepository()
        self.case_repo = BusinessCaseRepository()
        self.workflow_engine = WorkflowCoordinationEngine(task_repo=self.task_repo)

    def _locate_batch_dir(self, name_pattern: str) -> Path | None:
        """Locates the directory containing .eml files for a given employee pattern."""
        if not self.base_dir.exists():
            return None
        matches = [p for p in self.base_dir.glob(f"*{name_pattern}*") if p.is_dir()]
        if not matches:
            return None
        outer_dir = matches[0]

        # Check inside subdirectories
        for sub in outer_dir.glob(f"*{name_pattern}*"):
            if sub.is_dir():
                return sub
        return outer_dir

    async def import_batch(
        self,
        batch_name: str = "all",
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Imports and analyzes one or all batches from `Train Data`.
        batch_name options: 'all', 'swapnali', 'ganesh', 'vaibhav'.
        """
        log = logger.bind(batch_name=batch_name, limit=limit)
        log.info("Starting Train Data batch import")

        results = {
            "batch_name": batch_name,
            "batches_processed": [],
            "total_imported": 0,
            "total_duplicates": 0,
            "total_tasks_created": 0,
            "total_dependencies_created": 0,
            "active_bottlenecks": [],
        }

        batches_to_run = []
        if batch_name.lower() in ("all", "swapnali"):
            batches_to_run.append("swapnali")
        if batch_name.lower() in ("all", "ganesh"):
            batches_to_run.append("ganesh")
        if batch_name.lower() in ("all", "vaibhav"):
            batches_to_run.append("vaibhav")

        for b in batches_to_run:
            if b == "swapnali":
                b_res = await self._import_swapnali(limit)
            elif b == "ganesh":
                b_res = await self._import_ganesh(limit)
            elif b == "vaibhav":
                b_res = await self._import_vaibhav(limit)
            else:
                continue

            results["batches_processed"].append(b_res)
            results["total_imported"] += b_res.get("imported_count", 0)
            results["total_duplicates"] += b_res.get("duplicate_count", 0)

        # Collect current tasks and bottlenecks across all business cases
        tasks = await self.task_repo.list_legacy_tasks(limit=500)
        results["total_tasks_created"] = len(tasks)
        deps = await self.task_repo.list_dependencies()
        results["total_dependencies_created"] = len(deps)

        bottlenecks = await self.workflow_engine.get_active_bottlenecks_across_cases()
        results["active_bottlenecks"] = bottlenecks

        log.info("Train Data batch import complete", total_imported=results["total_imported"])
        return results

    async def _import_swapnali(self, limit: int | None = None) -> dict[str, Any]:
        """Imports Swapnali's enquiry and quotation batch."""
        batch_dir = self._locate_batch_dir("Swapnali")
        if not batch_dir:
            return {"name": "swapnali", "error": "Swapnali directory not found in Train Data"}

        mailbox_id = await self.email_repo.get_or_create_default_mailbox("EML", "Swapnali Mailbox (Train Data)")
        eml_files = sorted(batch_dir.glob("*.eml"))
        if limit:
            eml_files = eml_files[:limit]

        imported = 0
        duplicates = 0
        imported_ids = []

        for f in eml_files:
            raw = self.provider._load_eml_fixture(f)
            if not raw:
                continue
            raw.source_type = "TRAIN_DATA_SWAPNALI"
            msg, is_dup = await self.ingestion_service.ingest_raw_message(mailbox_id, raw)
            if is_dup:
                duplicates += 1
            elif msg:
                imported += 1
                imported_ids.append(str(msg.id))

        return {
            "name": "swapnali",
            "directory": str(batch_dir),
            "files_found": len(eml_files),
            "imported_count": imported,
            "duplicate_count": duplicates,
            "imported_ids": imported_ids,
        }

    async def _import_ganesh(self, limit: int | None = None) -> dict[str, Any]:
        """Imports Ganesh's part check and PO verification batch."""
        batch_dir = self._locate_batch_dir("Ganesh")
        if not batch_dir:
            return {"name": "ganesh", "error": "Ganesh directory not found in Train Data"}

        mailbox_id = await self.email_repo.get_or_create_default_mailbox("EML", "Ganesh Mailbox (Train Data)")
        eml_dir = batch_dir / "emails" if (batch_dir / "emails").is_dir() else batch_dir
        eml_files = sorted(eml_dir.glob("*.eml"))
        if limit:
            eml_files = eml_files[:limit]

        imported = 0
        duplicates = 0
        imported_ids = []

        for f in eml_files:
            raw = self.provider._load_eml_fixture(f)
            if not raw:
                continue
            raw.source_type = "TRAIN_DATA_GANESH"
            msg, is_dup = await self.ingestion_service.ingest_raw_message(mailbox_id, raw)
            if is_dup:
                duplicates += 1
            elif msg:
                imported += 1
                imported_ids.append(str(msg.id))

        return {
            "name": "ganesh",
            "directory": str(batch_dir),
            "files_found": len(eml_files),
            "imported_count": imported,
            "duplicate_count": duplicates,
            "imported_ids": imported_ids,
        }

    async def _import_vaibhav(self, limit: int | None = None) -> dict[str, Any]:
        """Imports Vaibhav's SO booking and capacity coordination batch."""
        batch_dir = self._locate_batch_dir("Vaibhav")
        if not batch_dir:
            return {"name": "vaibhav", "error": "Vaibhav directory not found in Train Data"}

        mailbox_id = await self.email_repo.get_or_create_default_mailbox("EML", "Vaibhav Mailbox (Train Data)")
        eml_dir = batch_dir / "emails" if (batch_dir / "emails").is_dir() else batch_dir
        eml_files = sorted(eml_dir.glob("*.eml"))
        if limit:
            eml_files = eml_files[:limit]

        imported = 0
        duplicates = 0
        imported_ids = []

        for f in eml_files:
            raw = self.provider._load_eml_fixture(f)
            if not raw:
                continue
            raw.source_type = "TRAIN_DATA_VAIBHAV"
            msg, is_dup = await self.ingestion_service.ingest_raw_message(mailbox_id, raw)
            if is_dup:
                duplicates += 1
            elif msg:
                imported += 1
                imported_ids.append(str(msg.id))

        return {
            "name": "vaibhav",
            "directory": str(batch_dir),
            "files_found": len(eml_files),
            "imported_count": imported,
            "duplicate_count": duplicates,
            "imported_ids": imported_ids,
        }
