import pymongo
import mysql.connector
from datetime import datetime

def migrate_mongo_to_mysql():
    # Conexión a MongoDB
    mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
    mongo_db = mongo_client["farmachele_db"]
    
    # Conexión a MySQL
    mysql_conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Cod1029144695",
        database="farmachele_db"
    )
    mysql_cursor = mysql_conn.cursor()
    
    try:
        # 1. Migrar admin_users
        print("Migrando admin_users...")
        admin_users = mongo_db["admin_users"].find()
        for user in admin_users:
            mysql_cursor.execute("""
                INSERT INTO admin_users (id, email, password, name, is_admin, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                user.get("id"),
                user.get("email"),
                user.get("password"),
                user.get("name"),
                user.get("is_admin", True),
                user.get("created_at")
            ))
        
        # 2. Migrar users
        print("Migrando users...")
        users = mongo_db["users"].find()
        for user in users:
            mysql_cursor.execute("""
                INSERT INTO users (id, email, password, name, phone, address, is_verified, is_admin, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user.get("id"),
                user.get("email"),
                user.get("password"),
                user.get("name"),
                user.get("phone"),
                user.get("address"),
                user.get("is_verified", False),
                user.get("is_admin", False),
                user.get("created_at")
            ))
        
        # 3. Migrar products
        print("Migrando products...")
        products = mongo_db["products"].find()
        for product in products:
            mysql_cursor.execute("""
                INSERT INTO products (id, name, description, price, category, stock, image_url, requires_prescription, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                product.get("id"),
                product.get("name"),
                product.get("description"),
                product.get("price"),
                product.get("category"),
                product.get("stock"),
                product.get("image_url"),
                product.get("requires_prescription", False),
                product.get("active", True),
                product.get("created_at")
            ))
        
        # 4. Migrar carts y cart_items
        print("Migrando carts...")
        carts = mongo_db["corts"].find()  # Nota: en MongoDB se llama "corts"
        for cart in carts:
            # Insertar el carrito
            mysql_cursor.execute("""
                INSERT INTO carts (id, user_id, updated_at)
                VALUES (%s, %s, %s)
            """, (
                cart.get("id"),
                cart.get("user_id"),
                cart.get("updated_at")
            ))
            
            # Insertar items del carrito
            cart_id = cart.get("id")
            items = cart.get("items", [])
            
            for item in items:
                mysql_cursor.execute("""
                    INSERT INTO cart_items (cart_id, product_id, quantity)
                    VALUES (%s, %s, %s)
                """, (
                    cart_id,
                    item.get("product_id"),  # Asumiendo la estructura de items
                    item.get("quantity", 1)
                ))
        
        # Confirmar cambios
        mysql_conn.commit()
        print("¡Migración completada exitosamente!")
        
    except Exception as e:
        print(f"Error durante la migración: {e}")
        mysql_conn.rollback()
    
    finally:
        mysql_cursor.close()
        mysql_conn.close()
        mongo_client.close()

if __name__ == "__main__":
    migrate_mongo_to_mysql()