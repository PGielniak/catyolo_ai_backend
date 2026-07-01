from fastapi import Header, HTTPException, status

_service = None


def init_auth(service) -> None:
    global _service
    _service = service


def require_api_key(x_api_key: str = Header(None)) -> None:
    if _service is None or not _service.validate(x_api_key or ''):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or missing API key',
        )
