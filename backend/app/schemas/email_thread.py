from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.email_thread import ThreadStatus, EmailSource


class EmailMessageOut(BaseModel):
    id: int
    sender: Optional[str]
    recipient: Optional[str]
    body_text: Optional[str]
    received_at: Optional[datetime]
    is_draft: bool
    is_outbound: bool

    class Config:
        from_attributes = True


class EmailThreadOut(BaseModel):
    id: int
    company_id: int
    customer_id: Optional[int]
    subject: Optional[str]
    source: Optional[EmailSource]
    mailbox: Optional[str]
    status: ThreadStatus
    last_message_at: Optional[datetime]
    snippet: Optional[str]
    linked_invoice_numbers: Optional[str]
    messages: List[EmailMessageOut] = []

    class Config:
        from_attributes = True


class DraftRequest(BaseModel):
    thread_id: int
    instructions: Optional[str] = None


class DraftOut(BaseModel):
    thread_id: int
    draft_body: str
    subject: str
    external_draft_id: Optional[str] = None
