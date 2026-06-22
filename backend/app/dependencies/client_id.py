from fastapi import Header, HTTPException


async def get_client_id(x_client_id: str = Header(default="", alias="X-Client-ID")) -> str:
    if not x_client_id or len(x_client_id) < 8:
        raise HTTPException(status_code=400, detail="Missing or invalid X-Client-ID header")
    return x_client_id
