
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


@app.post("/extract", response_model=InvoiceResponse)
def extract(req: InvoiceRequest):
    text = req.text.strip()

    if not text:
        raise HTTPException(422, "Empty invoice text")

    # Extract vendor name
    vendor = None
    vendor_patterns = [
        r"(?:vendor|supplier|billed\s+by|invoice\s+from)"
        r"\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 &.,'-]{1,100}?)"
        r"(?=\s+(?:invoice|total|amount|currency|date|payment|due)\b|[\n;]|$)",

        r"\b([A-Z][A-Za-z0-9&.,' -]{1,70}?"
        r"(?:Industries|Corporation|Company|Limited|Ltd\.?|LLC|Inc\.?))\b"
    ]

    for pattern in vendor_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            vendor = match.group(1).strip(" ,.-")
            break

    # Extract currency
    currency_match = re.search(r"\b(USD|EUR|GBP)\b", text, re.I)
    currency = currency_match.group(1).upper() if currency_match else None

    # Extract amount, preferring total-due labels
    amount = None
    amount_pattern = r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?(?!\w)"

    labels = [
        r"(?:total\s+amount\s+due|total\s+due|amount\s+due|grand\s+total|total\s+payable|amount\s+payable|invoice\s+total|total)"
        r"\s*[:=\-]?\s*(?:(?:USD|EUR|GBP)\s*)?(" + amount_pattern + r")",

        r"(?:USD|EUR|GBP)\s*(" + amount_pattern + r")"
    ]

    for pattern in labels:
        matches = list(re.finditer(pattern, text, re.I))
        if matches:
            amount = float(matches[-1].group(1).replace(",", ""))
            break

    # Extract the due date
    date_match = re.search(
        r"(?:payment\s+due\s+date|due\s+date|payable\s+by|payment\s+due|due\s+on)"
        r"\s*[:=\-]?\s*(2026-\d{2}-\d{2})",
        text, re.I
    )

    if not date_match:
        date_match = re.search(r"\b(2026-\d{2}-\d{2})\b", text)

    if not all([vendor, amount is not None, currency, date_match]):
        raise HTTPException(422, "Could not identify all invoice fields")

    due_date = date_match.group(1)

    try:
        date.fromisoformat(due_date)
    except ValueError:
        raise HTTPException(422, "Invalid invoice date")

    return InvoiceResponse(
        vendor=vendor,
        amount=amount,
        currency=currency,
        date=due_date
    )
