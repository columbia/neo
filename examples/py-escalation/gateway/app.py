"""Gateway service: authenticates the caller, then forwards the profile update
(including the attacker-controlled `role`) to the users service. It never checks
*which* role the caller may assign."""
import requests
from fastapi import FastAPI, Request

app = FastAPI()

USERS_SVC = "http://users-svc:9000"


@app.post("/api/profile")
async def update_profile(request: Request):
    body = await request.json()
    role = body.get("role")          # attacker-controlled
    username = body.get("username")

    # forward downstream — the role is passed straight through
    resp = requests.post(
        USERS_SVC + "/internal/setRole",
        json={"username": username, "role": role},
        headers={"Authorization": request.headers.get("Authorization", "")},
    )
    return {"status": resp.status_code}
