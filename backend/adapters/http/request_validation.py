import json

from fastapi import HTTPException, Request


async def require_empty_action_body(request: Request) -> None:
    """Las salidas solo aceptan ausencia de cuerpo o un objeto JSON vacío."""
    raw_body = await request.body()
    if not raw_body:
        return
    try:
        body = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=422, detail="El cuerpo debe ser {} o estar ausente"
        ) from error
    if not isinstance(body, dict) or body:
        raise HTTPException(
            status_code=422, detail="El cuerpo debe ser {} o estar ausente"
        )
