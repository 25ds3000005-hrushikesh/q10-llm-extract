
import re
from datetime import date
from fastapi import FastAPI
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
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Empty text")

    vendor_match = re.search(
        r"(?:invoice\s+from|vendor\s*[:\-])\s*"
        r"([A-Za-z0-9][A-Za-z0-9 &.,'-]*?)"
        r"(?=\s+(?:total|amount|currency|invoice\s+date|due\s+date|payment\s+due)\b|[,;\n]|$)",
        text, re.I
    )

    amount_match = re.search(
        r"(?:total\s+due|amount\s+due|grand\s+total|total|amount)"
        r"\s*[:\-]?\s*(?:(USD|EUR|GBP)\s*)?"
        r"([0-9,]+(?:\.[0-9]{1,2})?)",
        text, re.I
    )

    if amount_match:
        amount = float(amount_match.group(2).replace(",", ""))
        currency = amount_match.group(1)
        if not currency:
            currency_match = re.search(r"\b(USD|EUR|GBP)\b", text, re.I)
            currency = currency_match.group(1) if currency_match else None
    else:
        currency_amount = re.search(
            r"\b(USD|EUR|GBP)\s*([0-9,]+(?:\.[0-9]{1,2})?)\b",
            text, re.I
        )
        if not currency_amount:
            from fastapi import HTTPException
            raise HTTPException(422, detail="Amount not found")
        currency = currency_amount.group(1)
        amount = float(currency_amount.group(2).replace(",", ""))

    due_date_match = re.search(
        r"(?:payment\s+due\s+date|due\s+date|payable\s+by|payment\s+due)"
        r"\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        text, re.I
    )

    if not due_date_match:
        due_date_match = re.search(r"\b(2026-\d{2}-\d{2})\b", text)

    if not vendor_match or not due_date_match or not currency:
        from fastapi import HTTPException
        raise HTTPException(422, detail="Required invoice field not found")

    vendor = vendor_match.group(1).strip(" ,.-")
    due_date = due_date_match.group(1)

    try:
        date.fromisoformat(due_date)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(422, detail="Invalid date")

    return InvoiceResponse(
        vendor=vendor,
        amount=amount,
        currency=currency.upper(),
        date=due_date
    )
