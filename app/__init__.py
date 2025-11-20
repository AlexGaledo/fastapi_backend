from fastapi import FastAPI
from pydantic import BaseModel



def create_app() -> FastAPI:
    app = FastAPI(title="HackConnect Backend")

    class Item(BaseModel):
        name: str
        description: str | None = None
        price: float
        tax: float | None = None

    @app.get("/")
    async def read_root():
        return {"message": "Welcome to the HackConnect Backend!"}

    @app.post("/items/", response_model=Item)
    async def create_item(item: Item):
        return item

    return app