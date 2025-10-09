# verify-admin.py
import asyncio
import hashlib
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno (igual que en server.py)
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MySQL connection (igual que en server.py)
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'Cod1029144695')
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DB = os.environ.get('MYSQL_DB', 'farmachelo_db')

# Crear engine de SQLAlchemy (igual que en server.py)
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

async def verify_admin():
    db = SessionLocal()
    try:
        # Verificar que podemos conectar a la base de datos
        print("🔌 Conectando a la base de datos MySQL...")
        
        # Verificar tablas (podemos hacer una consulta simple)
        from sqlalchemy import text
        result = db.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result]
        print("📦 Tablas en la base de datos:", tables)
        
        # Verificar admin en la tabla admin_users
        from sqlalchemy import text
        admin_query = text("SELECT * FROM admin_users WHERE email = :email")
        result = db.execute(admin_query, {"email": "admin@farmachelo.com"})
        admin = result.fetchone()
        
        if admin:
            print("✅ Admin user found!")
            print(f"📧 Email: {admin[1]}")  # email está en la posición 1
            print(f"👤 Name: {admin[2]}")   # name está en la posición 2
            print(f"🔑 Is admin: {admin[4]}")  # is_admin está en la posición 4
            
            # Verificar contraseña
            test_pass = "admin123"
            hashed_test = hash_password(test_pass)
            if hashed_test == admin[3]:  # password está en la posición 3
                print("✅ Password verification: SUCCESS")
                return True
            else:
                print("❌ Password verification: FAILED")
                print(f"Expected: {hashed_test}")
                print(f"Found: {admin[3]}")
                return False
        else:
            print("❌ Admin user not found")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

# Ejecutar verificación
result = asyncio.run(verify_admin())
if result:
    print("\n🎉 El admin está listo para usar!")
    print("📧 Email: admin@farmachelo.com")
    print("🔑 Password: admin123")
else:
    print("\n❌ Hay problemas con el admin. Ejecuta create_admin.py")