from fastapi import Request
from fastapi.responses import JSONResponse
import traceback


async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return clean JSON error."""
    print(f"[ERROR] {request.method} {request.url}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )
