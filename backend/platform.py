"""Application integration without changing the vision endpoints."""
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from sqlalchemy.exc import SQLAlchemyError
from backend.database import configure
from backend.auth import router as auth_router
from backend.reports import router as report_router
from starlette.middleware.trustedhost import TrustedHostMiddleware
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


class BodyTooLarge(Exception):pass


class BodyLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope['path'].startswith('/api/'):
            return await self.app(scope,receive,send)
        headers=dict(scope['headers']);maximum=(76 if scope['path']=='/api/search' else 46)*1024*1024 if b'multipart/form-data' in headers.get(b'content-type',b'') else 32*1024
        length=headers.get(b'content-length',b'0')
        if not length.isdigit() or int(length)>maximum:
            return await JSONResponse({'detail':'Request exceeds the upload limit.'},status_code=413)(scope,receive,send)
        total=0
        async def bounded_receive():
            nonlocal total
            message=await receive();total+=len(message.get('body',b''))
            if total>maximum:raise BodyTooLarge()
            return message
        try:await self.app(scope,bounded_receive,send)
        except BodyTooLarge:await JSONResponse({'detail':'Request exceeds the upload limit.'},status_code=413)(scope,receive,send)


def install(app,settings=None):
    configure(app,settings);app.add_middleware(BodyLimit)
    if app.state.settings.environment=='production':
        app.add_middleware(TrustedHostMiddleware,allowed_hosts=[urlsplit(app.state.settings.origin).hostname],www_redirect=False)
    app.include_router(auth_router);app.include_router(report_router)
    # Feature routers are imported here so schema/auth remain independently testable.
    from backend.claims import router as claims_router
    from backend.matching import router as matching_router
    from backend.admin import router as admin_router
    app.include_router(claims_router);app.include_router(matching_router);app.include_router(admin_router)
    from backend.operations import router as operations_router,observe
    app.include_router(operations_router)

    def inference_access(request):
        if request.url.path in {'/api/search','/api/compare','/api/suggest-crops'}:
            origin=request.headers.get('origin')
            if origin and origin!=app.state.settings.origin:
                return JSONResponse({'detail':'Request origin is not allowed.'},status_code=403)
            remote=request.client and request.client.host not in {'127.0.0.1','::1','testclient'}
            if remote or app.state.settings.secure_cookie:
                from backend.auth import digest,COOKIE
                from backend.models import Session,User,now
                import secrets
                if not app.state.sessions:return JSONResponse({'detail':'Please log in.'},status_code=401)
                with app.state.sessions() as db:
                    session=db.get(Session,digest(request.cookies.get(COOKIE,'')))
                    user=db.get(User,session.user_id) if session and session.expires_at>now() else None
                    if not user or not user.active:return JSONResponse({'detail':'Please log in.'},status_code=401)
                    if not secrets.compare_digest(request.headers.get('x-csrf-token',''),session.csrf):return JSONResponse({'detail':'Session verification failed.'},status_code=403)
                    if origin!=app.state.settings.origin:return JSONResponse({'detail':'Request origin is not allowed.'},status_code=403)
                    from backend.auth import throttle
                    throttle(request,'inference',user.id,60,600)
        return None

    @app.middleware('http')
    async def security_headers(request,call_next):
        from time import perf_counter
        from starlette.concurrency import run_in_threadpool
        from fastapi import HTTPException
        started=perf_counter()
        try:denied=await run_in_threadpool(inference_access,request) if request.url.path in {'/api/search','/api/compare','/api/suggest-crops'} else None
        except HTTPException as exc:denied=JSONResponse({'detail':exc.detail},status_code=exc.status_code,headers=exc.headers)
        except SQLAlchemyError:denied=JSONResponse({'detail':'Database unavailable. Please try again.'},status_code=503)
        response=denied if denied is not None else await call_next(request)
        observe(request,response.status_code,perf_counter()-started)
        response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        if request.url.path.startswith('/api/v1'):response.headers['Cache-Control']='no-store'
        if request.url.path in {'/','/app'}:
            response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob: data:; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        if app.state.settings.secure_cookie:response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):
        if request.url.path.startswith('/api/v1'):
            return JSONResponse({'detail':'Check the required fields and their lengths.'},status_code=422)
        return await request_validation_exception_handler(request,exc)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request,exc):return JSONResponse({'detail':'Database unavailable. Please try again.'},status_code=503)

    @app.get('/app')
    def application():return FileResponse(ROOT/'frontend'/'app.html')

    @app.get('/api/v1/options')
    def options():
        from backend.settings import campus_today
        return {'retention_days':app.state.settings.retention_days,'today':campus_today().isoformat(),'registration_open':app.state.settings.environment!='production'}

    @app.get('/assets/{name}')
    def asset(name:str):
        if name not in {'app.css','app.js','app-ui.js'}:
            from fastapi import HTTPException
            raise HTTPException(404)
        return FileResponse(ROOT/'frontend'/name)


def create_app(settings):
    app=FastAPI(title='CampusFind');install(app,settings)
    return app
