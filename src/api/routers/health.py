from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"ok": True, "now": datetime.now().isoformat()}