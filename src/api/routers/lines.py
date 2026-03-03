from fastapi import APIRouter
from api.services.queries import get_lines_df, get_machines_by_line_df

router = APIRouter(prefix="/api/lines", tags=["lines"])

@router.get("")
def get_lines():
    df = get_lines_df()
    return df.to_dict(orient="records")

@router.get("/{line_id}/machines")
def get_machines_by_line(line_id: int):
    df = get_machines_by_line_df(line_id)
    return df.to_dict(orient="records")