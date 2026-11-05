"""Bound request bodies before multipart parsing can spool an oversized upload."""
from fastapi.responses import JSONResponse
from app.config import settings


class RequestBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        maximum = (settings.max_upload_bytes + 64 * 1024
                   if scope['path'] == '/api/submissions' else 64 * 1024)
        messages = []
        total = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            total += len(message.get('body', b''))
            if total > maximum:
                return await JSONResponse({'detail': 'Request body exceeds the size limit'},
                                          status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False):
                break
        iterator = iter(messages)

        async def bounded_receive():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        await self.app(scope, bounded_receive, send)
