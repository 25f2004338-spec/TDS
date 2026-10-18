
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import jwt

app = FastAPI()

ISSUER = "https://idp.exam.local"
AUDIENCE = "tds-05qxi7w5.apps.exam.local"

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
PASTE_THE_EXACT_ASSIGNED_PUBLIC_KEY_HERE
-----END PUBLIC KEY-----"""


class VerifyRequest(BaseModel):
    token: str


@app.post("/verify")
def verify_token(request: VerifyRequest):
    try:
        claims = jwt.decode(
            request.token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "require": ["exp", "iss", "aud", "sub"],
            },
        )

        return {
            "valid": True,
            "email": claims.get("email"),
            "sub": claims["sub"],
            "aud": claims["aud"],
        }

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail={"valid": False},
        )
