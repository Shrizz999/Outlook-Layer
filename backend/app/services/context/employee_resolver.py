"""Employee Directory and Identity Resolution Service.

Resolves employees, canonical names, and emails from email headers,
shared mailboxes, signatures, and body mentions.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# Standard organizational roster definitions
ORGANIZATIONAL_ROSTER = [
    {
        "name": "Swapnali",
        "email": "swapnali@balbird.invalid",
        "aliases": ["swapnali@example.test", "sales@example.test"],
        "department": "Sales Operations",
        "designation": "Enquiry & Quotation Lead",
        "role": "DEPT_HEAD",
        "keywords": ["swapnali", "quotation", "quote", "enquiry registration", "rfq registration"],
    },
    {
        "name": "Ganesh",
        "email": "ganesh@balbird.invalid",
        "aliases": ["ganesh@demo-company.test", "sales@demo-company.test", "sshrishette@gmail.com", "ganesh@example.test"],
        "department": "Sales Operations",
        "designation": "Part Verification & Customer PO Specialist",
        "role": "EMPLOYEE",
        "keywords": ["ganesh", "part details", "verify po", "customer po", "catalogue check"],
    },
    {
        "name": "Vaibhav",
        "email": "vaibhav@balbird.invalid",
        "aliases": ["vaibhav@stauff.example", "sales@stauff.example", "vaibhav@example.test"],
        "department": "Sales Operations",
        "designation": "Order Booking & Capacity Coordinator",
        "role": "EMPLOYEE",
        "keywords": ["vaibhav", "so booking", "sales order", "capacity outlook", "order booking"],
    },
    {
        "name": "Frank Engineering",
        "email": "engineering@balbird.invalid",
        "aliases": ["engineering@stauff.example", "engineering@example.test", "productdata@demo-company.test", "frank.eng@balbird.invalid"],
        "department": "Engineering",
        "designation": "Chief Technical Lead",
        "role": "DEPT_HEAD",
        "keywords": ["engineering", "technical", "drawing", "specification", "tolerance", "bom"],
    },
    {
        "name": "Bob PPC",
        "email": "ppc@balbird.invalid",
        "aliases": ["ppc@stauff.example", "ppc@example.test", "ppc@demo-company.test", "bob.ppc@balbird.invalid"],
        "department": "PPC",
        "designation": "Production Planning & Control Lead",
        "role": "DEPT_HEAD",
        "keywords": ["ppc", "production planning", "material availability", "capacity", "schedule"],
    },
    {
        "name": "Alice Purchase",
        "email": "purchase@balbird.invalid",
        "aliases": ["purchase.local@stauff.example", "purchase.import@stauff.example", "local.purchase@demo-company.test", "alice.purchase@balbird.invalid", "purchase.local@example.test", "purchase.import@example.test"],
        "department": "Purchase",
        "designation": "Procurement Manager",
        "role": "DEPT_HEAD",
        "keywords": ["purchase", "procurement", "shortage material", "raw material", "supplier"],
    },
    {
        "name": "Stores Desk",
        "email": "stores@balbird.invalid",
        "aliases": ["stores@stauff.example", "stores@example.test", "stores@demo-company.test"],
        "department": "Stores",
        "designation": "Stores & Inventory In-Charge",
        "role": "EMPLOYEE",
        "keywords": ["stores", "inventory", "stock receipt", "usable stock", "physical count"],
    },
    {
        "name": "Carol Production",
        "email": "production@balbird.invalid",
        "aliases": ["production@stauff.example", "production@example.test", "carol.prod@balbird.invalid"],
        "department": "Production",
        "designation": "Shop Floor Production Supervisor",
        "role": "DEPT_HEAD",
        "keywords": ["production", "machining", "cutting", "assembly", "shop floor"],
    },
    {
        "name": "David Quality",
        "email": "quality@balbird.invalid",
        "aliases": ["quality@stauff.example", "quality@example.test", "quality@demo-company.test", "david.qc@balbird.invalid"],
        "department": "Quality",
        "designation": "Senior Quality Inspector",
        "role": "DEPT_HEAD",
        "keywords": ["quality", "qc", "inspection", "test certificate", "pass"],
    },
    {
        "name": "Emma Dispatch",
        "email": "dispatch@balbird.invalid",
        "aliases": ["dispatch@stauff.example", "dispatch@example.test", "dispatch@demo-company.test", "emma.dispatch@balbird.invalid"],
        "department": "Dispatch",
        "designation": "Logistics & Dispatch In-Charge",
        "role": "EMPLOYEE",
        "keywords": ["dispatch", "shipping", "delivery challan", "transport", "freight"],
    },
]


class EmployeeResolver:
    """Resolves email addresses, names, and signature hints to employees."""

    @classmethod
    def resolve_by_email(cls, email: str | None) -> dict[str, Any] | None:
        if not email:
            return None
        clean_email = email.strip().lower()
        for emp in ORGANIZATIONAL_ROSTER:
            if emp["email"].lower() == clean_email:
                return emp
            if any(alias.lower() == clean_email for alias in emp["aliases"]):
                return emp
        return None

    @classmethod
    def resolve_by_name(cls, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        clean_name = name.strip().lower()
        for emp in ORGANIZATIONAL_ROSTER:
            if emp["name"].lower() == clean_name:
                return emp
            first_name = emp["name"].lower().split()[0]
            if first_name == clean_name:
                return emp
        return None

    @classmethod
    def resolve_by_text(cls, text: str | None) -> dict[str, Any] | None:
        """Scan text or signature for employee identifiers or keywords."""
        if not text:
            return None
        text_lower = text.lower()
        for emp in ORGANIZATIONAL_ROSTER:
            first_name = emp["name"].lower().split()[0]
            # Match standalone first name e.g. "Regards,\nVaibhav" or "Vaibhav\nSales Operations"
            if re.search(r"\b" + re.escape(first_name) + r"\b", text_lower):
                return emp
        return None

    @classmethod
    def get_employee_for_stage(cls, stage: str) -> dict[str, Any]:
        """Returns the canonical employee responsible for a specific workflow stage."""
        stage_upper = stage.upper()
        if "ENQUIRY_REGISTRATION" in stage_upper or "REGISTER" in stage_upper:
            return cls.resolve_by_name("Swapnali")
        elif "PART_CHECK" in stage_upper or "CATALOGUE" in stage_upper:
            return cls.resolve_by_name("Ganesh")
        elif "ENGINEERING" in stage_upper or "SPEC" in stage_upper or "TECHNICAL" in stage_upper:
            return cls.resolve_by_name("Frank Engineering")
        elif "QUOTATION" in stage_upper or "QUOTE" in stage_upper:
            return cls.resolve_by_name("Swapnali")
        elif "VERIFY_PO" in stage_upper or "PO_CHECK" in stage_upper:
            return cls.resolve_by_name("Ganesh")
        elif "SO_BOOKING" in stage_upper or "SALES_ORDER" in stage_upper:
            return cls.resolve_by_name("Vaibhav")
        elif "PPC" in stage_upper or "MATERIAL_AVAILABILITY" in stage_upper or "CAPACITY" in stage_upper:
            return cls.resolve_by_name("Bob PPC")
        elif "PROCUREMENT" in stage_upper or "PURCHASE" in stage_upper or "SHORTAGE" in stage_upper:
            return cls.resolve_by_name("Alice Purchase")
        elif "STORES" in stage_upper or "STOCK_RECEIPT" in stage_upper:
            return cls.resolve_by_name("Stores Desk")
        elif "PRODUCTION" in stage_upper or "MACHINING" in stage_upper or "ASSEMBLY" in stage_upper:
            return cls.resolve_by_name("Carol Production")
        elif "QUALITY" in stage_upper or "INSPECTION" in stage_upper:
            return cls.resolve_by_name("David Quality")
        elif "DISPATCH" in stage_upper or "SHIPPING" in stage_upper:
            return cls.resolve_by_name("Emma Dispatch")
        return cls.resolve_by_name("Swapnali")
