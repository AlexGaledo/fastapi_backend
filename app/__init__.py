from fastapi import FastAPI
from pydantic import BaseModel
from .routers import users, events
from fastapi.middleware.cors import CORSMiddleware




def create_app() -> FastAPI:
    app = FastAPI(title="HackConnect Backend")


    origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
        "*",  # allow all (only in development)
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,          # which domains can access
        allow_credentials=True,
        allow_methods=["*"],            # allow all HTTP methods
        allow_headers=["*"],            # allow all headers
    )

    @app.get("/")
    async def read_root():
        return {"message": "Welcome to the HackConnect Backend!"}

    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(events.router, prefix="/events", tags=["events"])

    return app