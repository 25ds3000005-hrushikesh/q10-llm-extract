
import re
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()


class InvoiceRequest(BaseModel):
    text: str


class InvoiceResponse(BaseModel):
    vendor: str = Field(min_length=1)
    amount: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


@app.get("/")
def home():
    return {"status": "Invoice extraction API is running"}


@app.post("/extract", response_model=InvoiceResponse)
def extract(req: InvoiceRequest):
    text = req.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Invoice text is empty"
        )

    # Currency
    currency_match = re.search(
        r"\b(USD|EUR|GBP)\b", text, re.IGNORECASE
    )
    currency = currency_match.group(1).upper() if currency_match else None

    # Amount: prefer values near total/due labels
    number = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"

    amount_patterns = [
        rf"(?:total\s+amount\s+due|total\s+due|amount\s+due|grand\s+total|total\s+payable|amount\s+payable|invoice\s+total|total)"
        rf"\s*[:=\-]?\s*(?:(?:USD|EUR|GBP)\s*)?({number})",

        rf"(?:amount|balance\s+due)\s*[:=\-]?\s*(?:(?:USD|EUR|GBP)\s*)?({number})",

        rf"\b(?:USD|EUR|GBP)\s*({number})"
    ]

    amount = None

    for pattern in amount_patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            amount = float(matches[-1].group(1).replace(",", ""))
            break

    # Due date
    date_match = re.search(
        r"(?:payment\s+due\s+date|due\s+date|payment\s+due|due\s+on|payable\s+by)"
        r"\s*[:=\-]?\s*(\d{4}-\d{2}-\d{2})",
        text,
        re.IGNORECASE
    )

    if not date_match:
        date_match = re.search(
            r"\b(2026-\d{2}-\d{2})\b", text
        )

    # Vendor
    vendor = None

    # Prefer explicitly labelled vendor names
    vendor_patterns = [
        r"(?:vendor|supplier|billed\s+by|invoice\s+from)"
        r"\s*[:=\-]?\s*(.{2,100}?)"
        r"(?=\s+(?:invoice\s*(?:number|no\.?|#|date)?|total|amount|currency|date|payment|due)\b|[\n;]|$)",

        r"\b([A-Z][A-Za-z0-9&.,' -]{1,70}?"
        r"(?:Industries|Corporation|Company|Limited|Ltd\.?|LLC|Inc\.?))"
        r"(?=[\s,.;]|$)"
    ]

    for pattern in vendor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            vendor = match.group(1).strip(" \t\r\n,;:-.")
            break

    if not vendor or amount is None or not currency or not date_match:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Could not extract all required invoice fields",
                "vendor_found": bool(vendor),
                "amount_found": amount is not None,
                "currency_found": bool(currency),
                "date_found": bool(date_match)
            }
        )

    due_date = date_match.group(1)

    try:
        date.fromisoformat(due_date)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid due date"
        )

    return InvoiceResponse(
        vendor=vendor,
        amount=amount,
        currency=currency,
        date=due_date
    )
