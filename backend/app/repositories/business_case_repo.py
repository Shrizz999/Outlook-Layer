"""Business Case Repository."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.repositories.store import get_store, get_supabase_client
from app.schemas.business_case import (
    BusinessCaseCreate,
    BusinessCaseRead,
    CaseLinkCreate,
    CaseLinkRead,
    CasePartyCreate,
    CasePartyRead,
)


class BusinessCaseRepository:
    def __init__(self) -> None:
        self._store = get_store()
        self._client = get_supabase_client()

    async def list_cases(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        customer_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BusinessCaseRead]:
        if self._client:
            q = self._client.table("bi_business_cases").select("*, bi_case_parties(*), bi_case_links(*)")
            if status:
                q = q.eq("status", status)
            if priority:
                q = q.eq("priority", priority)
            if customer_id:
                q = q.eq("primary_customer_id", str(customer_id))
            res = q.range(offset, offset + limit - 1).order("opened_at", desc=True).execute()
            cases = []
            for row in res.data:
                parties = [CasePartyRead(**p) for p in row.get("bi_case_parties", [])]
                links = [CaseLinkRead(**l) for l in row.get("bi_case_links", [])]
                c_data = {k: v for k, v in row.items() if k not in ("bi_case_parties", "bi_case_links")}
                cases.append(BusinessCaseRead(**c_data, parties=parties, links=links))
            return cases

        # In-memory
        results = []
        for case in self._store.bi_business_cases.values():
            if status and case["status"] != status:
                continue
            if priority and case["priority"] != priority:
                continue
            if customer_id and case["primary_customer_id"] != customer_id:
                continue

            case_id_str = str(case["id"])
            parties = [
                CasePartyRead(**p)
                for p in self._store.bi_case_parties.values()
                if str(p["business_case_id"]) == case_id_str
            ]
            links = [
                CaseLinkRead(**l)
                for l in self._store.bi_case_links.values()
                if str(l["business_case_id"]) == case_id_str
            ]
            results.append(BusinessCaseRead(**case, parties=parties, links=links))

        # Sort descending by opened_at
        results.sort(key=lambda x: x.opened_at, reverse=True)
        return results[offset : offset + limit]

    async def get_case_by_id(self, case_id: UUID) -> BusinessCaseRead | None:
        case_id_str = str(case_id)
        if self._client:
            res = self._client.table("bi_business_cases").select("*, bi_case_parties(*), bi_case_links(*)").eq("id", case_id_str).execute()
            if not res.data:
                return None
            row = res.data[0]
            parties = [CasePartyRead(**p) for p in row.get("bi_case_parties", [])]
            links = [CaseLinkRead(**l) for l in row.get("bi_case_links", [])]
            c_data = {k: v for k, v in row.items() if k not in ("bi_case_parties", "bi_case_links")}
            return BusinessCaseRead(**c_data, parties=parties, links=links)

        case = self._store.bi_business_cases.get(case_id_str)
        if not case:
            return None
        parties = [
            CasePartyRead(**p)
            for p in self._store.bi_case_parties.values()
            if str(p["business_case_id"]) == case_id_str
        ]
        links = [
            CaseLinkRead(**l)
            for l in self._store.bi_case_links.values()
            if str(l["business_case_id"]) == case_id_str
        ]
        return BusinessCaseRead(**case, parties=parties, links=links)

    async def get_case_by_number(self, case_number: str) -> BusinessCaseRead | None:
        if self._client:
            res = self._client.table("bi_business_cases").select("id").eq("case_number", case_number).execute()
            if res.data:
                return await self.get_case_by_id(UUID(res.data[0]["id"]))
            return None
        for case in self._store.bi_business_cases.values():
            if case["case_number"] == case_number:
                return await self.get_case_by_id(case["id"])
        return None

    async def create_case(self, data: BusinessCaseCreate) -> BusinessCaseRead:
        now = datetime.now(UTC)
        case_id = uuid4()
        if data.case_number:
            case_number = data.case_number
        elif self._client:
            import time
            ts = int(time.time() * 1000) % 1000000
            case_number = f"CASE-2026-{ts:06d}"
            while self._client.table("bi_business_cases").select("id").eq("case_number", case_number).execute().data:
                ts += 1
                case_number = f"CASE-2026-{ts:06d}"
        else:
            case_number = self._store.generate_case_number()

        record = {
            "id": case_id,
            "case_number": case_number,
            "title": data.title,
            "case_type": data.case_type,
            "status": data.status,
            "primary_customer_id": data.primary_customer_id,
            "primary_owner_employee_id": data.primary_owner_employee_id,
            "priority": data.priority,
            "summary": data.summary,
            "summary_is_ai_generated": data.summary_is_ai_generated,
            "opened_at": now,
            "closed_at": None,
            "created_at": now,
            "updated_at": now,
            "created_by_employee_id": data.created_by_employee_id,
        }

        if self._client:
            payload = {
                **record,
                "id": str(case_id),
                "primary_customer_id": str(data.primary_customer_id) if data.primary_customer_id else None,
                "primary_owner_employee_id": str(data.primary_owner_employee_id) if data.primary_owner_employee_id else None,
                "created_by_employee_id": str(data.created_by_employee_id) if data.created_by_employee_id else None,
                "opened_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            res = self._client.table("bi_business_cases").insert(payload).execute()
            row = res.data[0]
            return BusinessCaseRead(**row, parties=[], links=[])

        self._store.bi_business_cases[str(case_id)] = record
        return BusinessCaseRead(**record, parties=[], links=[])

    async def add_case_link(self, case_id: UUID, link: CaseLinkCreate, employee_id: UUID | None = None) -> CaseLinkRead:
        now = datetime.now(UTC)
        link_id = uuid4()
        record = {
            "id": link_id,
            "business_case_id": case_id,
            "linked_object_type": link.linked_object_type,
            "linked_object_id": link.linked_object_id,
            "relationship_type": link.relationship_type,
            "match_method": link.match_method,
            "match_confidence": link.match_confidence,
            "validation_status": link.validation_status,
            "created_at": now,
            "created_by_employee_id": employee_id,
        }
        if self._client:
            payload = {
                **record,
                "id": str(link_id),
                "business_case_id": str(case_id),
                "created_by_employee_id": str(employee_id) if employee_id else None,
                "created_at": now.isoformat(),
            }
            res = self._client.table("bi_case_links").insert(payload).execute()
            return CaseLinkRead(**res.data[0])

        self._store.bi_case_links[str(link_id)] = record
        return CaseLinkRead(**record)

    async def update_case_status(self, case_id: UUID, status: str) -> None:
        case_id_str = str(case_id)
        now = datetime.now(UTC)
        if self._client:
            self._client.table("bi_business_cases").update({"status": status, "updated_at": now.isoformat()}).eq("id", case_id_str).execute()
        elif case_id_str in self._store.bi_business_cases:
            self._store.bi_business_cases[case_id_str]["status"] = status
            self._store.bi_business_cases[case_id_str]["updated_at"] = now
