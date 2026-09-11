"""UserMgmt service (Python / FastAPI).

Authentication is enforced at the router level, but `authz` only checks the
*general* permission to switch roles - it never validates eligibility for the
*specific* role requested, so any authenticated user can escalate to `admin`.
"""

import json

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

router = APIRouter(dependencies=[Depends(lambda: authz)])


@router.post("/setUserRole")
async def set_user_role(request: Request):
    data = await request.json()
    # PRIVILEGED: modifies the user's role with no per-role eligibility check
    update_role(data.get("username"), data.get("role"))
    return {"message": "Role updated successfully"}


def authz(request: Request):
    try:
        token = request.headers["Authorization"].split()[1]
        user = jwt.decode(token, "secret")["sub"]
        if not can_switch_roles(user):
            raise HTTPException(status_code=403, detail="Not eligible")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")


def can_switch_roles(user):
    return True


def update_role(username, role):
    ...  # writes the new role to the database
