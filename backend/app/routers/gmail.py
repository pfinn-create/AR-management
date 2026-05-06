from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.routers.deps import current_user, assert_company_access
from app.config import settings

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/authorize")
def authorize(
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Return the Google OAuth URL for the user to visit."""
    assert_company_access(user, company_id)
    if not settings.gmail_client_id:
        raise HTTPException(status_code=503, detail="Gmail OAuth not configured — add GMAIL_CLIENT_ID to .env")

    from app.services.gmail_service import get_authorize_url
    url = get_authorize_url(company_id)
    return {"authorize_url": url}


@router.get("/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Google redirects here after the user approves access.
    Stores the token and redirects to the frontend Emails page.
    No auth token required — this is the OAuth callback endpoint.
    """
    try:
        from app.services.gmail_service import exchange_code
        mailbox, company_id = exchange_code(code, state, db)
        redirect_url = f"{settings.frontend_url}/emails?gmail_connected=1&mailbox={mailbox}&company_id={company_id}"
    except Exception as e:
        redirect_url = f"{settings.frontend_url}/emails?gmail_error=1&detail={str(e)[:100]}"

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/mailboxes")
def list_mailboxes(
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """List connected Gmail mailboxes for a company."""
    assert_company_access(user, company_id)
    from app.services.gmail_service import list_connected_mailboxes
    return list_connected_mailboxes(company_id, db)


@router.delete("/mailboxes/{token_id}")
def disconnect_mailbox(
    token_id: int,
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Disconnect (delete stored token for) a Gmail mailbox."""
    assert_company_access(user, company_id)
    from app.services.gmail_service import disconnect_mailbox as _disconnect
    ok = _disconnect(token_id, company_id, db)
    if not ok:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    return {"detail": "Disconnected"}
