# verify_admin.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib

async def verify_admin():
    try:
        client = AsyncIOMotorClient('mongodb://localhost:27017')
        db = client['farmachelo_web_database']
        
        # Verificar colecciones
        collections = await db.list_collection_names()
        print("📦 Colecciones en la base de datos:", collections)
        
        # Verificar admin
        admin = await db.admin_users.find_one({"email": "admin@farmachelo.com"})
        
        if admin:
            print("✅ Admin user found!")
            print(f"📧 Email: {admin['email']}")
            print(f"👤 Name: {admin['name']}")
            print(f"🔑 Is admin: {admin.get('is_admin', False)}")
            
            # Verificar contraseña
            test_pass = "admin123"
            hashed_test = hashlib.sha256(test_pass.encode()).hexdigest()
            if hashed_test == admin['password']:
                print("✅ Password verification: SUCCESS")
                return True
            else:
                print("❌ Password verification: FAILED")
                return False
        else:
            print("❌ Admin user not found")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        client.close()

# Ejecutar verificación
result = asyncio.run(verify_admin())
if result:
    print("\n🎉 El admin está listo para usar!")
    print("📧 Email: admin@farmachelo.com")
    print("🔑 Password: admin123")
else:
    print("\n❌ Hay problemas con el admin. Ejecuta create_admin.py")