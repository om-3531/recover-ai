"""
Razorpay Webhook REST API route.
"""

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.razorpay.exceptions import RazorpaySignatureVerificationError
from app.schemas.webhooks import WebhookResponse
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/razorpay",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest Razorpay webhook event",
)
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(None, alias="X-Razorpay-Event-Id"),
    db: Session = Depends(get_db),
) -> WebhookResponse:
    """
    Receive, cryptographically verify, and process a Razorpay webhook event idempotently.
    """
    if not x_razorpay_signature:
        raise RazorpaySignatureVerificationError("Missing X-Razorpay-Signature header")

    raw_body = await request.body()

    result = WebhookService.process_razorpay_webhook(
        db=db,
        raw_body=raw_body,
        signature=x_razorpay_signature,
        event_id_header=x_razorpay_event_id,
    )
    return WebhookResponse(
        status=result["status"],
        event_id=result["event_id"],
        event_type=result.get("event_type"),
        message=result["message"],
    )
