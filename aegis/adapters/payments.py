import time
import secrets
from typing import Dict, Optional
from pydantic import BaseModel


class CreateRequest(BaseModel):
    amount: float
    currency: str
    vendor_id: str
    memo: Optional[str] = None


class CreateResponse(BaseModel):
    payment_id: str
    amount: float
    currency: str
    status: str


class RefundRequest(BaseModel):
    payment_id: str
    reason: Optional[str] = None


class RefundResponse(BaseModel):
    refund_id: str
    payment_id: str
    status: str


class PaymentsAdapter:
    def __init__(self):
        self.payments: Dict[str, CreateResponse] = {}
        self.refunds: Dict[str, RefundResponse] = {}
    
    def create(self, req: CreateRequest) -> CreateResponse:
        if req.amount <= 0:
            raise ValueError("amount must be positive")
        if not req.currency:
            raise ValueError("currency is required")
        if not req.vendor_id:
            raise ValueError("vendor_id is required")
        
        payment = CreateResponse(
            payment_id=secrets.token_hex(16),
            amount=req.amount,
            currency=req.currency,
            status="created"
        )
        
        self.payments[payment.payment_id] = payment
        time.sleep(0.01)
        
        return payment
    
    def refund(self, req: RefundRequest) -> RefundResponse:
        if not req.payment_id:
            raise ValueError("payment_id is required")
        
        if req.payment_id not in self.payments:
            raise ValueError(f"payment '{req.payment_id}' not found")
        
        refund = RefundResponse(
            refund_id=secrets.token_hex(16),
            payment_id=req.payment_id,
            status="refunded"
        )
        
        self.refunds[refund.refund_id] = refund
        time.sleep(0.01)
        
        return refund

