# create_admin.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib
import uuid
from datetime import datetime, timezone

async def ensure_admin_exists():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['farmachelo_web_database']
    
    admin_email = "admin@farmachelo.com"
    admin_password = "admin123"
    
    # Verificar si ya existe
    existing_admin = await db.admin_users.find_one({"email": admin_email})
    
    if not existing_admin:
        admin_data = {
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password": hashlib.sha256(admin_password.encode()).hexdigest(),
            "name": "Administrador Principal",
            "is_admin": True,
            "created_at": datetime.now(timezone.utc)
        }
        await db.admin_users.insert_one(admin_data)
        print("✅ Admin creado exitosamente!")
        print(f"📧 Email: {admin_email}")
        print(f"🔑 Password: {admin_password}")
    else:
        print("✅ Admin ya existe en la base de datos")
    
    client.close()

# Ejecutar
asyncio.run(ensure_admin_exists())