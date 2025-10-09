"""
-------------------------------------------------------------------------------
FastAPI Application Class for Librarian Server.
-------------------------------------------------------------------------------
"""

from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import asyncio
import uvicorn
from typing import Type, Optional

from .db_comm import DatabaseMongo

"""
FastAPI + Beanie + MongoDB
https://medium.com/@gurramakhileshwar333/get-your-beanies-a-beginners-guide-to-beanie-mongodb-odm-for-python-b715c3f59a92
"""
class LibrarianServer(DatabaseMongo):
    """  Establish a Librarian connection though FastAPI """
    def __init__(self,
                 Experiment_document: Type[Document],
                 Ctrl_document: Type[Document],
                 Experiment_condition,
                 database_name: str,
                 mongo_uri: str = "mongodb://127.0.0.1:27017/mydatabase",
                 host: str = "127.0.0.1",
                 port: int = 9000,
                 ):

        super().__init__()

        self.app = FastAPI()
        self.host = host
        self.port = port
        self.mongo_uri = mongo_uri


        # Initialize database & routes
        self.app.add_event_handler("startup", self.init_db)
        self.setup_routes()

    async def init_db(self):
        """Initialize MongoDB connection and Beanie ODM"""
        client = AsyncIOMotorClient(self.mongo_uri)
        db = client.get_database()
        await init_beanie(database=db, document_models=[Item])

    def setup_routes(self):
        """Setup API routes"""

        @self.app.post("/items/", response_model=Item)
        async def create_item(item: Item):
            ...
            # await item.insert()
            # return item

        @self.app.get("/items/", response_model=list[Item])
        async def get_items():
            return await Item.find_all().to_list()

        @self.app.get("/items/{item_id}", response_model=Item)
        async def get_item(item_id: str):
            item = await Item.get(item_id)
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            return item

        @self.app.put("/items/{item_id}", response_model=Item)
        async def update_item(item_id: str, updated_item: Item):
            item = await Item.get(item_id)
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            item.name = updated_item.name
            item.description = updated_item.description
            item.price = updated_item.price
            await item.save()
            return item

        @self.app.delete("/items/{item_id}")
        async def delete_item(item_id: str):
            item = await Item.get(item_id)
            if not item:
                raise HTTPException(status_code=404, detail="Item not found")
            await item.delete()
            return {"message": "Item deleted"}

    def run(self):
        """Start the FastAPI server with Uvicorn"""
        uvicorn.run(self.app, host=self.host, port=self.port)


if __name__ == "__main__":
    # Start the Application
    server = LibrarianServer()
    server.run()
