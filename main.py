
import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

class InvoiceRequest(BaseModel):
    text: str

class InvoiceResponse(BaseModel):
    vendor: str
    amount: float
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

@app.post("/extract", response_model=InvoiceResponse)
def extract(req: InvoiceRequest):
    if not req.text.strip():
        raise HTTPException(422, "Empty invoice text")

    prompt = f"""
Extract vendor, amount, currency and due date from this invoice.
Return only JSON with keys vendor, amount, currency, date.
Amount must be numeric, currency uppercase 3-letter code,
date must be YYYY-MM-DD. Do not guess missing values.
Invoice: {req.text}
"""

    try:
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "gemma3:1b-it-qat",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            },
            timeout=120
        )
        r.raise_for_status()
        data = json.loads(r.json()["response"])
        return InvoiceResponse.model_validate(data)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Invoice extraction failed")
