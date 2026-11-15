"""Attachment Storage and Meaningful Data Extraction Service.

Saves email attachments to persistent storage and extracts structured line items
from CSV, Excel (.xlsx), and text PDF files for task creation and order linking.
Strictly excludes OCR and image processing.
"""
from __future__ import annotations

import csv
import io
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class AttachmentService:
    def __init__(self, base_storage_dir: str | Path = "data/attachments") -> None:
        self.storage_dir = Path(base_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_attachment(
        self,
        message_id: str | UUID,
        filename: str,
        payload: bytes,
        content_type: str | None = None,
    ) -> Path:
        """Saves an attachment binary payload to the system storage."""
        dest_dir = self.storage_dir / str(message_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename
        dest_path.write_bytes(payload)
        logger.info("Saved attachment file to storage", path=str(dest_path), size=len(payload))
        return dest_path

    def parse_and_extract_line_items(
        self,
        file_path_or_bytes: str | Path | bytes,
        filename: str,
    ) -> dict[str, Any]:
        """
        Parses CSV, XLSX, and text PDF files and extracts structured line items,
        part numbers, quantities, customer delivery dates, and specifications.
        """
        fn = filename.lower()
        if isinstance(file_path_or_bytes, (str, Path)):
            p = Path(file_path_or_bytes)
            if not p.exists():
                return {"error": f"File not found: {p}", "filename": filename}
            payload = p.read_bytes()
        else:
            payload = file_path_or_bytes

        if fn.endswith((".csv", ".tsv")):
            return self._parse_csv(payload, filename)
        elif fn.endswith((".xlsx", ".xls")):
            return self._parse_excel(payload, filename)
        elif fn.endswith(".pdf"):
            return self._parse_pdf(payload, filename)
        elif fn.endswith((".txt", ".log")):
            return self._parse_text(payload, filename)
        elif fn.endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
            return {
                "type": "IMAGE",
                "filename": filename,
                "size_bytes": len(payload),
                "ocr_status": "EXCLUDED",
                "note": "Image document. OCR and image processing are strictly excluded per system requirements.",
                "line_items": [],
            }
        return {"type": "UNKNOWN", "filename": filename, "line_items": []}

    def _parse_csv(self, payload: bytes, filename: str) -> dict[str, Any]:
        try:
            text = payload.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text))
            rows = [r for r in reader if any(cell.strip() for cell in r)]
            if not rows:
                return {"type": "CSV", "filename": filename, "line_items": []}

            headers = [h.strip().lstrip("\ufeff") for h in rows[0]]
            data_rows = rows[1:]
            line_items = []

            for idx, r in enumerate(data_rows, start=1):
                row_dict = {headers[i]: r[i].strip() for i in range(min(len(headers), len(r)))}
                # Detect standard columns
                part = (
                    row_dict.get("Part")
                    or row_dict.get("Part Number")
                    or row_dict.get("Item")
                    or row_dict.get("Customer Code")
                    or row_dict.get("OEM Reference")
                    or ""
                )
                qty = (
                    row_dict.get("Qty")
                    or row_dict.get("Open_Qty")
                    or row_dict.get("Required_Qty")
                    or row_dict.get("Physical_Qty")
                    or row_dict.get("Quantity")
                    or ""
                )
                desc = row_dict.get("Description") or row_dict.get("Description Supplied") or ""
                so = row_dict.get("SO") or row_dict.get("SO_Impact") or ""
                target_date = row_dict.get("Customer_Target") or row_dict.get("Latest_Date") or ""

                line_items.append({
                    "line_number": idx,
                    "part_number": part,
                    "description": desc,
                    "quantity": qty,
                    "so_number": so,
                    "target_deadline": target_date,
                    "raw_row": row_dict,
                })

            return {
                "type": "CSV",
                "filename": filename,
                "headers": headers,
                "row_count": len(line_items),
                "line_items": line_items,
            }
        except Exception as e:
            logger.warning("Failed to parse CSV attachment", filename=filename, error=str(e))
            return {"type": "CSV", "filename": filename, "error": str(e), "line_items": []}

    def _parse_excel(self, payload: bytes, filename: str) -> dict[str, Any]:
        try:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(payload), data_only=True)
            all_line_items = []
            sheet_names = wb.sheetnames

            for sheet_name in sheet_names[:3]:
                ws = wb[sheet_name]
                raw_rows = list(ws.iter_rows(values_only=True))
                if not raw_rows:
                    continue

                # Locate header row (skip title / banner row if present)
                header_idx = 0
                for i, r in enumerate(raw_rows[:5]):
                    non_empty = [c for c in r if c is not None and str(c).strip()]
                    if len(non_empty) >= 3:
                        header_idx = i
                        break

                headers = [str(c).strip() if c is not None else f"col_{j}" for j, c in enumerate(raw_rows[header_idx])]
                data_rows = raw_rows[header_idx + 1:]

                for idx, r in enumerate(data_rows, start=1):
                    if not any(c for c in r if c is not None and str(c).strip()):
                        continue
                    row_dict = {
                        headers[j]: str(r[j]).strip() if j < len(r) and r[j] is not None else ""
                        for j in range(len(headers))
                    }

                    part = (
                        row_dict.get("Customer Item")
                        or row_dict.get("Part")
                        or row_dict.get("MM NUMBER")
                        or row_dict.get("Item Code")
                        or row_dict.get("Item")
                        or ""
                    )
                    desc = (
                        row_dict.get("Assembly Description")
                        or row_dict.get("Description")
                        or row_dict.get("DESCRIPTION")
                        or ""
                    )
                    qty = (
                        row_dict.get("Qty")
                        or row_dict.get("QTY")
                        or row_dict.get("Quantity")
                        or row_dict.get("Req Qty")
                        or ""
                    )
                    uom = row_dict.get("UOM") or row_dict.get("Unit") or ""
                    required_at = row_dict.get("Required At") or row_dict.get("Delivery Destination") or ""

                    all_line_items.append({
                        "sheet": sheet_name,
                        "line_number": idx,
                        "part_number": part,
                        "description": desc,
                        "quantity": qty,
                        "uom": uom,
                        "destination": required_at,
                        "raw_row": row_dict,
                    })

            return {
                "type": "EXCEL",
                "filename": filename,
                "sheets": sheet_names,
                "row_count": len(all_line_items),
                "line_items": all_line_items,
            }
        except Exception as e:
            logger.warning("Failed to parse Excel attachment", filename=filename, error=str(e))
            return {"type": "EXCEL", "filename": filename, "error": str(e), "line_items": []}

    def _parse_pdf(self, payload: bytes, filename: str) -> dict[str, Any]:
        try:
            import pdfplumber

            pages_text = []
            extracted_tables = []
            line_items = []

            with pdfplumber.open(io.BytesIO(payload)) as pdf:
                for page_num, page in enumerate(pdf.pages[:10], start=1):
                    txt = page.extract_text()
                    if txt:
                        pages_text.append(txt)

                    tables = page.extract_tables() or []
                    for t in tables:
                        if t and len(t) >= 2:
                            headers = [str(c or "").strip() for c in t[0]]
                            extracted_tables.append({"page": page_num, "headers": headers, "rows": t[1:]})
                            for line_idx, r in enumerate(t[1:], start=1):
                                if any(c for c in r if c and str(c).strip()):
                                    line_items.append({
                                        "page": page_num,
                                        "line_number": line_idx,
                                        "part_number": str(r[0] or "").strip(),
                                        "description": str(r[1] or "").strip() if len(r) > 1 else "",
                                        "quantity": str(r[2] or "").strip() if len(r) > 2 else "",
                                        "uom": str(r[3] or "").strip() if len(r) > 3 else "",
                                    })

            full_text = "\n".join(pages_text).strip()
            if not full_text and not line_items:
                return {
                    "type": "PDF",
                    "filename": filename,
                    "is_scanned_unsupported": True,
                    "text": "Scanned document. OCR is strictly excluded per system requirements.",
                    "line_items": [],
                }

            return {
                "type": "PDF",
                "filename": filename,
                "extracted_text": full_text[:4000],
                "tables": extracted_tables,
                "line_items": line_items,
            }
        except Exception as e:
            logger.warning("Failed to parse PDF attachment", filename=filename, error=str(e))
            return {"type": "PDF", "filename": filename, "error": str(e), "line_items": []}

    def _parse_text(self, payload: bytes, filename: str) -> dict[str, Any]:
        text = payload.decode("utf-8", errors="replace")
        return {
            "type": "TEXT",
            "filename": filename,
            "content": text[:3000],
            "line_items": [],
        }
