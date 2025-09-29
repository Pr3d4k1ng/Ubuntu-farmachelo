# migrate_rename_db.py
import os
from pymongo import MongoClient

OLD_DB = os.environ.get('OLD_DB_NAME', 'farmaweb_database')
NEW_DB = os.environ.get('DB_NAME', 'farmachelo_web_database')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')

def rename_database():
    client = MongoClient(MONGO_URL)
    old_db = client[OLD_DB]
    new_db = client[NEW_DB]

    # Si NEW_DB ya existe, abortar para no pisar datos
    if NEW_DB in client.list_database_names():
        print(f"⚠️ La base de datos destino ya existe: {NEW_DB}. Abortando.")
        return

    collections = old_db.list_collection_names()
    if not collections:
        print(f"⚠️ No hay colecciones en {OLD_DB}. Nada que migrar.")
        return

    print(f"🔄 Migrando {len(collections)} colecciones de '{OLD_DB}' a '{NEW_DB}'...")
    for coll_name in collections:
        src = old_db[coll_name]
        dst = new_db[coll_name]
        docs = list(src.find({}))
        if docs:
            dst.insert_many(docs)
        print(f"  ✅ {coll_name}: {len(docs)} documentos copiados")

    # Borrar BD anterior
    client.drop_database(OLD_DB)
    print(f"✅ Migración completa. '{OLD_DB}' -> '{NEW_DB}'")

if __name__ == "__main__":
    rename_database()


