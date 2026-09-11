"""Users service. `/internal/setRole` is meant to be internal-only, but it
performs no authorization on the requested role and writes it straight to the DB."""
import sqlite3

from fastapi import APIRouter, Request

router = APIRouter()
_conn = sqlite3.connect("users.db")


@router.post("/internal/setRole")
async def set_role(request: Request):
    data = await request.json()
    username = data.get("username")
    role = data.get("role")

    # PRIVILEGED: no check that the caller may grant `role` (could be "admin")
    _conn.execute("UPDATE users SET role = '" + role + "' WHERE name = '" + username + "'")
    _conn.commit()
    return {"ok": True}
