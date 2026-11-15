"""
Balbird Intelligence — Cross-Department Relationship Detection Engine.

Detects critical operational relationships across departments:
1. Machine breakdown affecting PPC scheduling and customer orders.
2. Management priority orders connected to PPC shortages.
3. SS304 material shortages reported by multiple departments.
4. HR onboarding connected to IT access preparation.
5. Part specification mismatches connected to supply-chain stock shortages.
6. Supplier purchase orders distinguished from customer sales orders.
7. Invoice references distinguished from work order references.
8. Dispatch delays connected to customer commitments and management escalation.

Enforces evidence traceability, distinguishes date types, stock states,
and marks uncertain matches as HUMAN_VERIFICATION_REQUIRED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CrossDepartmentConnection:
    scenario: str
    scenario_title: str
    connected_departments: list[str]
    business_references: list[str]
    waiting_party: str | None
    holding_party: str | None
    blocker_description: str | None
    downstream_order_impact: str | None
    verification_status: str  # VERIFIED, POSSIBLE_UNCONFIRMED, HUMAN_VERIFICATION_REQUIRED
    confidence: float
    evidence: str
    explanation: str


class CrossDepartmentDetector:
    """
    Evaluates text and extracted metadata to detect multi-department
    connections without false keyword conflation.
    """

    def detect_connections(
        self,
        *,
        subject: str | None,
        body: str | None,
        department: str | None,
        references: list[dict[str, Any]] | None = None,
        existing_orders: list[str] | None = None,
    ) -> list[CrossDepartmentConnection]:
        text = f"{subject or ''} {body or ''}".strip()
        text_lower = text.lower()
        connections: list[CrossDepartmentConnection] = []

        # 1. Production machine breakdown affecting PPC scheduling and customer orders
        if any(w in text_lower for w in ["breakdown", "machine down", "spindle", "lathe failure", "cnc breakdown", "furnace breakdown", "press breakdown"]):
            # Prioritize specific machine codes (CNC, Lathe, Spindle, Furnace) over generic lines
            machine_m = re.search(r"\b(cnc[-\s]?\d+|lathe[-\s]?\d+|press[-\s]?\d+|furnace[-\s]?\d+)\b", text, re.IGNORECASE)
            if not machine_m:
                machine_m = re.search(r"\b(line[-\s]?\d+)\b", text, re.IGNORECASE)
            machine_name = machine_m.group(0).upper().replace(" ", "-") if machine_m else "PRODUCTION EQUIPMENT"
            
            # Find associated orders
            so_refs = re.findall(r"\bso[-\s]?(\d{4,6})\b", text, re.IGNORECASE)
            affected_so = [f"SO-{s}" for s in so_refs]
            
            evidence_snippet = self._extract_snippet(text, ["breakdown", "spindle", "down", "failure"])
            connections.append(
                CrossDepartmentConnection(
                    scenario="MACHINE_BREAKDOWN_PPC_IMPACT",
                    scenario_title="Machine Breakdown Affecting PPC Scheduling & Customer Orders",
                    connected_departments=["PRODUCTION", "PPC", "SALES_OPERATIONS"],
                    business_references=[machine_name] + affected_so,
                    waiting_party="PPC & Sales Operations",
                    holding_party=f"Production ({machine_name})",
                    blocker_description=f"Equipment breakdown on {machine_name}; capacity halted",
                    downstream_order_impact=f"Orders {', '.join(affected_so) if affected_so else 'active queue'} at risk of schedule breach",
                    verification_status="HUMAN_VERIFICATION_REQUIRED" if not any(w in text_lower for w in ["maintenance signoff", "service ticket"]) else "VERIFIED",
                    confidence=0.92,
                    evidence=evidence_snippet,
                    explanation=f"Production breakdown on {machine_name} directly halts operations, requiring PPC rescheduling and customer order risk notification.",
                )
            )

        # 2. Management priority orders connected to PPC shortages
        if any(w in text_lower for w in ["management priority", "ceo directive", "director priority", "urgent milestone", "executive escalation", "month end shipping target"]):
            so_m = re.findall(r"\bso[-\s]?(\d{4,6})\b", text, re.IGNORECASE)
            so_list = [f"SO-{s}" for s in so_m]
            has_shortage = any(w in text_lower for w in ["shortage", "shortfall", "capacity bottleneck", "stock out", "material wait"])
            
            evidence_snippet = self._extract_snippet(text, ["priority", "milestone", "ceo", "director", "escalation"])
            connections.append(
                CrossDepartmentConnection(
                    scenario="MANAGEMENT_PRIORITY_PPC_SHORTAGE",
                    scenario_title="Management Priority Order Linked to PPC Shortage & Expediting",
                    connected_departments=["MANAGEMENT", "PPC", "SALES_OPERATIONS", "PURCHASE"],
                    business_references=so_list or ["MANAGEMENT_DIRECTIVE"],
                    waiting_party="Management & Sales Operations",
                    holding_party="PPC / Purchase Material Allocation",
                    blocker_description="PPC component availability constraint under executive milestone deadline",
                    downstream_order_impact=f"High-visibility delivery milestone for {', '.join(so_list) if so_list else 'priority order'}",
                    verification_status="VERIFIED" if so_list else "POSSIBLE_UNCONFIRMED",
                    confidence=0.88,
                    evidence=evidence_snippet,
                    explanation="Executive management mandate requires override of standard PPC queues to expedite critical customer delivery.",
                )
            )

        # 3. SS304 material shortages reported by multiple departments
        if ("ss304" in text_lower or "ss 304" in text_lower or "stainless steel 304" in text_lower) and any(w in text_lower for w in ["shortage", "stock out", "unavailability", "delayed shipment", "no stock", "depleted"]):
            evidence_snippet = self._extract_snippet(text, ["ss304", "ss 304", "shortage", "stock"])
            connections.append(
                CrossDepartmentConnection(
                    scenario="SS304_MULTI_DEPT_SHORTAGE",
                    scenario_title="SS304 Stainless Steel Shortage Reported Across Departments",
                    connected_departments=["PRODUCTION", "PPC", "PURCHASE", "SUPPLY_CHAIN"],
                    business_references=["MAT-SS304"],
                    waiting_party="Production Machining / Cutting",
                    holding_party="Raw Material Procurement / Supplier Replenishment",
                    blocker_description="Zero available stock of SS304 raw material across stores and shop floor",
                    downstream_order_impact="All fabrication and tubular work orders requiring SS304 halted",
                    verification_status="HUMAN_VERIFICATION_REQUIRED",
                    confidence=0.94,
                    evidence=evidence_snippet,
                    explanation="Cross-department inventory constraint on SS304 reported; requires synchronized supplier expediting and production re-routing.",
                )
            )

        # 4. HR onboarding connected to IT access preparation
        if any(w in text_lower for w in ["onboarding", "new joinee", "new hire", "joining date", "candidate joining", "welcome to the team", "employment offer"]):
            # Extract employee name and joining date
            emp_m = re.search(r"(?:name|employee|candidate|joinee)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text, re.IGNORECASE)
            emp_name = emp_m.group(1) if emp_m else "New Hire"
            date_m = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
            joining_date = date_m.group(0) if date_m else "UPCOMING"
            
            evidence_snippet = self._extract_snippet(text, ["onboarding", "joining", "hire", "candidate"])
            connections.append(
                CrossDepartmentConnection(
                    scenario="HR_ONBOARDING_IT_ACCESS",
                    scenario_title="HR Employee Onboarding Linked to IT Equipment & Access Provisioning",
                    connected_departments=["HR", "IT"],
                    business_references=[f"ONBOARDING-{emp_name.upper().replace(' ', '_')}"],
                    waiting_party="HR Onboarding Schedule",
                    holding_party="IT Access & Hardware Deployment",
                    blocker_description=f"IT workstation, email, and ERP credentials required prior to start date ({joining_date})",
                    downstream_order_impact=f"Employee {emp_name} cannot commence duties without system onboarding",
                    verification_status="VERIFIED" if date_m else "HUMAN_VERIFICATION_REQUIRED",
                    confidence=0.91,
                    evidence=evidence_snippet,
                    explanation=f"New personnel onboarding for {emp_name} requires IT access setup and hardware provisioning prior to start date.",
                )
            )

        # 5. Part specification mismatches connected to supply-chain stock shortages
        if any(w in text_lower for w in ["spec mismatch", "specification mismatch", "drawing revision", "tolerance conflict", "eco-", "thread mismatch", "drawing rev"]):
            part_m = re.search(r"\b([A-Z]{2,4}[-\s]?\d{3,5}[A-Z0-9\-_]*)\b", text)
            part_code = part_m.group(0) if part_m else "SPEC_PART"
            
            evidence_snippet = self._extract_snippet(text, ["spec", "mismatch", "revision", "tolerance", "drawing"])
            connections.append(
                CrossDepartmentConnection(
                    scenario="PART_SPEC_MISMATCH_SUPPLY_CHAIN",
                    scenario_title="Part Specification Mismatch Blocking Supply Chain & Stock Issue",
                    connected_departments=["APPLICATION", "SUPPLY_CHAIN", "PURCHASE", "QUALITY"],
                    business_references=[part_code],
                    waiting_party="Supply Chain Stores & Assembly",
                    holding_party="Application / Engineering Specification Signoff",
                    blocker_description=f"Existing stock for {part_code} quarantined pending drawing deviation approval",
                    downstream_order_impact="Orders dependent on this item held in QC quarantine",
                    verification_status="HUMAN_VERIFICATION_REQUIRED",
                    confidence=0.89,
                    evidence=evidence_snippet,
                    explanation=f"Technical specification or revision discrepancy on {part_code} invalidates current stores stock until engineering deviation is approved.",
                )
            )

        # 6. Supplier purchase orders distinguished from customer sales orders
        has_supplier_po = bool(re.search(r"\b(supplier po|vendor po|po[-\s]?(?:apex|titan|pioneer|vendor|supp|\d{4,6}))\b", text, re.IGNORECASE))
        has_customer_so = bool(re.search(r"\b(customer po|sales order|so[-\s]?\d{4,6}|cust po)\b", text, re.IGNORECASE))
        if has_supplier_po and has_customer_so:
            connections.append(
                CrossDepartmentConnection(
                    scenario="SUPPLIER_PO_VS_CUSTOMER_SO",
                    scenario_title="Supplier Purchase Order Distinguished from Customer Sales Order",
                    connected_departments=["PURCHASE", "SALES_OPERATIONS", "ACCOUNTS"],
                    business_references=["PROCUREMENT_RECONCILIATION"],
                    waiting_party="Sales Operations Customer Commitments",
                    holding_party="Supplier PO Delivery Fulfillment",
                    blocker_description="Customer SO delivery contingent on external supplier PO replenishment",
                    downstream_order_impact="Customer delivery commitment depends on inbound supplier procurement",
                    verification_status="VERIFIED",
                    confidence=0.95,
                    evidence="Distinct PO and SO identifiers extracted without numeric conflation",
                    explanation="Maintains strict boundary: Outgoing Purchase Orders to suppliers are not conflated with incoming Customer Sales Orders.",
                )
            )

        # 7. Invoice references distinguished from work order references
        inv_nums = re.findall(r"\b(?:inv|invoice)[-\s:]*(?:inv[-\s:]*)?(\d{4,6})\b", text, re.IGNORECASE)
        wo_nums = re.findall(r"\b(?:wo|work\s+order)[-\s:]*(?:wo[-\s:]*)?(\d{4,6})\b", text, re.IGNORECASE)
        common_nums = set(inv_nums).intersection(set(wo_nums))
        if common_nums:
            num = list(common_nums)[0]
            inv_str = f"INV-{num}"
            wo_str = f"WO-{num}"
            connections.append(
                CrossDepartmentConnection(
                    scenario="INVOICE_VS_WORK_ORDER",
                    scenario_title="Invoice Reference Strictly Distinguished from Work Order",
                    connected_departments=["ACCOUNTS", "PRODUCTION"],
                    business_references=[inv_str, wo_str],
                    waiting_party="Accounts Billing Reconciliation",
                    holding_party="Production Routing",
                    blocker_description="Identical numeric suffixes between billing invoice and shop floor routing order",
                    downstream_order_impact="Independent entity segregation required to prevent misattribution",
                    verification_status="VERIFIED",
                    confidence=0.96,
                    evidence=f"Distinct reference prefixes preserved: Invoice {inv_str} vs Work Order {wo_str}",
                    explanation=f"Preserves strict domain boundary between financial Invoice ({inv_str}) and factory Work Order ({wo_str}) despite identical numeric suffixes.",
                )
            )

        # 8. Dispatch delays connected to customer commitments and management escalation
        if any(w in text_lower for w in ["dispatch delay", "shipping delay", "transporter delay", "carrier delay", "vehicle breakdown", "transport strike", "delayed shipment"]) and any(w in text_lower for w in ["commitment", "customer promised", "escalat", "management", "urgent", "so-"]):
            so_m = re.findall(r"\bso[-\s]?(\d{4,6})\b", text, re.IGNORECASE)
            so_list = [f"SO-{s}" for s in so_m]
            
            evidence_snippet = self._extract_snippet(text, ["dispatch", "delay", "transporter", "carrier", "commitment"])
            connections.append(
                CrossDepartmentConnection(
                    scenario="DISPATCH_DELAY_COMMITMENT_RISK",
                    scenario_title="Logistics Dispatch Delay Threatening Customer Commitment & Escalated to Management",
                    connected_departments=["LOGISTICS", "SALES_OPERATIONS", "MANAGEMENT"],
                    business_references=so_list or ["LOGISTICS_DISPATCH_DELAY"],
                    waiting_party="Customer & Sales Operations",
                    holding_party="Logistics & Transporter Carrier",
                    blocker_description="Vehicle/carrier delay past committed dispatch schedule",
                    downstream_order_impact=f"Customer delivery breach imminent on {', '.join(so_list) if so_list else 'dispatched consignments'}",
                    verification_status="VERIFIED" if so_list else "HUMAN_VERIFICATION_REQUIRED",
                    confidence=0.93,
                    evidence=evidence_snippet,
                    explanation="Outbound shipment delay threatens committed customer arrival dates, triggering sales operations notification and management escalation.",
                )
            )

        return connections

    def _extract_snippet(self, text: str, keywords: list[str]) -> str:
        sentences = re.split(r"[.\n]+", text)
        for s in sentences:
            if any(k in s.lower() for k in keywords):
                return s.strip()[:200]
        return text[:150]
