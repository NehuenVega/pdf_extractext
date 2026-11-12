from motor.motor_asyncio import AsyncIOMotorClient
from App.domain.interfaces import IDocumentCache, IDocumentRepository
from typing import Optional, List
from bson.objectid import ObjectId

class MongoDocumentRepository(IDocumentCache, IDocumentRepository):
    def __init__(self, mongo_uri: str, db_name: str):
        # Un solo cliente por aplicación: Motor maneja su propio pool de conexiones.
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db["documents"]

    def close(self) -> None:
        self.client.close()

    async def save_document(self, document_data: dict) -> str:
        result = await self.collection.insert_one(document_data)
        return str(result.inserted_id)

    async def get_by_checksum(self, checksum: str) -> Optional[dict]:
        document = await self.collection.find_one({"checksum": checksum})
        return document

    async def get_all(self) -> List[dict]:
        cursor = self.collection.find({})
        documents = await cursor.to_list(length=100)
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        return documents

    async def get_by_id(self, doc_id: str) -> Optional[dict]:
        try:
            doc = await self.collection.find_one({"_id": ObjectId(doc_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
            return doc
        except Exception:
            return None # Si el ID tiene un formato inválido, devolvemos None

    async def update(self, doc_id: str, update_data: dict) -> bool:
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_data}
            )
            # matched_count y no modified_count: guardar el mismo nombre que
            # ya tenía no es un error, el documento existe.
            return result.matched_count > 0
        except Exception:
            return False

    async def delete(self, doc_id: str) -> bool:
        try:
            result = await self.collection.delete_one({"_id": ObjectId(doc_id)})
            return result.deleted_count > 0
        except Exception:
            return False
