# create_admin.py
import mysql.connector
import hashlib
import uuid
from datetime import datetime, timezone

def ensure_admin_exists():
    # Configuración de conexión a MySQL
    connection = mysql.connector.connect(
        host='localhost',
        user='root',  # Cambia por tu usuario de MySQL
        password='',  # Cambia por tu contraseña de MySQL
        database='farmachelo_web_database'
    )
    
    admin_email = "admin@farmachelo.com"
    admin_password = "admin123"
    
    try:
        cursor = connection.cursor()
        
        # Verificar si ya existe
        cursor.execute("SELECT id FROM admin_users WHERE email = %s", (admin_email,))
        existing_admin = cursor.fetchone()
        
        if not existing_admin:
            admin_id = str(uuid.uuid4())
            hashed_password = hashlib.sha256(admin_password.encode()).hexdigest()
            created_at = datetime.now(timezone.utc)
            
            # Insertar nuevo admin
            cursor.execute("""
                INSERT INTO admin_users (id, email, password, name, is_admin, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (admin_id, admin_email, hashed_password, "Administrador Principal", True, created_at))
            
            connection.commit()
            print("✅ Admin creado exitosamente!")
            print(f"📧 Email: {admin_email}")
            print(f"🔑 Password: {admin_password}")
        else:
            print("✅ Admin ya existe en la base de datos")
            
    except mysql.connector.Error as error:
        print(f"❌ Error de MySQL: {error}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Ejecutar
if __name__ == "__main__":
    ensure_admin_exists()