"""Bound streamed upload bytes before multipart parsing spools unbounded data."""
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from .config import settings


class UploadLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").rstrip("/") != "/api/repos/upload":
            return await self.app(scope, receive, send)
        limit = settings.MAX_ARCHIVE_BYTES + 1024**2
        total, exceeded = 0, False

        async def bounded_receive():
            nonlocal total, exceeded
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > limit:
                    exceeded = True
                    # Starlette closes partial uploads on this exception type.
                    raise MultiPartException("Upload exceeds the configured size limit.")
            return message

        async def bounded_send(message):
            if not exceeded:
                await send(message)

        await self.app(scope, bounded_receive, bounded_send)
        if exceeded:
            await JSONResponse({"detail": "Archive exceeds the configured upload size limit."}, status_code=413)(scope, receive, send)
