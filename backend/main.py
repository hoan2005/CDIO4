from fastapi import FastAPI,Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from router import chatbot
from config import settings
# Khởi tạo app với thông tin từ file config
from contextlib import asynccontextmanager

app = FastAPI(
    description="Hệ thống Backend sử dụng FastAPI",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)
app.include_router(chatbot.router_chat)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(req, exc):
    errors = []
    for err in exc.errors():
        field = err['loc'][-1]
        msg = err['msg']

        if msg.startswith('Value error'):
            msg = msg.replace('Value error, ', '')

        errors.append({
            'field': field,
            'message': msg
        })
    return JSONResponse(status_code=422, content={'errors': errors})


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run("main:app", host="127.0.0.1", port=settings.PORT, reload=True)