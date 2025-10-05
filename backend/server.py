from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from bson import ObjectId
from fastapi import File, UploadFile, Form
from jose import jwt
import base64
import secrets
import os
import logging
import uuid
import hashlib
import json
import shutil
import secrets
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection (usar valores por defecto si no hay .env)
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'farmachelo_web_database')]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'farmachelo-secret-key-2025')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Stripe Configuration
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')

# Security - Modificamos HTTPBearer para excluir OPTIONS
class OptionalHTTPBearer(HTTPBearer):
    async def __call__(self, request: Request):
        if request.method == "OPTIONS":
            return None
        return await super().__call__(request)

security = OptionalHTTPBearer()

# ==================== MODELS ====================

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    is_verified: bool = False
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    price: float
    category: str  # "prescription" or "over_counter"
    stock: int
    image_url: Optional[str] = None
    requires_prescription: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category: str
    stock: int
    image_url: Optional[str] = None
    requires_prescription: bool = False

class CartItem(BaseModel):
    product_id: str
    quantity: int
    prescription_file: Optional[str] = None

class Cart(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    items: List[CartItem] = []
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    items: List[CartItem]
    total_amount: float
    status: str = "pending"  # pending, paid, processing, shipped, delivered, cancelled
    payment_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    user_id: Optional[str] = None
    amount: float
    currency: str = "usd"
    status: str = "pending"  # pending, completed, failed, expired
    payment_status: str = "unpaid"  # unpaid, paid
    order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CheckoutRequest(BaseModel):
    cart_items: List[CartItem]
    origin_url: str

# ==================== PAYMENT MODELS ====================

class PaymentCard(BaseModel):
    cardNumber: str
    expiryDate: str
    cvv: str
    cardholderName: str
    country: str

class PaymentRequest(BaseModel):
    email: EmailStr
    card: PaymentCard
    amount: float
    currency: str = "COP"  # Cambiar de "$" a "COP"
    order_id: Optional[str] = None

class PaymentResponse(BaseModel):
    success: bool
    transactionId: Optional[str] = None
    error: Optional[str] = None

class CardValidationRequest(BaseModel):
    cardNumber: str
    expiryDate: str
    cvv: str

class CardValidationResponse(BaseModel):
    valid: bool
    cardType: Optional[str] = None
    error: Optional[str] = None

# ==================== PAYMENT HELPER FUNCTIONS ====================

def validate_card_number(card_number: str) -> bool:
    """Validar número de tarjeta usando el algoritmo de Luhn"""
    card_number = card_number.replace(" ", "")
    if not card_number.isdigit():
        return False
    
    # Algoritmo de Luhn
    total = 0
    reverse_digits = card_number[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    
    return total % 10 == 0

def get_card_type(card_number: str) -> str:
    """Determinar el tipo de tarjeta basado en el número"""
    card_number = card_number.replace(" ", "")
    
    if card_number.startswith("4"):
        return "Visa"
    elif card_number.startswith(("51", "52", "53", "54", "55")):
        return "Mastercard"
    elif card_number.startswith(("34", "37")):
        return "Amex"
    elif card_number.startswith(("300", "301", "302", "303", "304", "305", "36", "38")):
        return "Diners Club"
    elif card_number.startswith(("6011", "65")):
        return "Discover"
    else:
        return "Unknown"

def validate_expiry_date(expiry_date: str) -> bool:
    """Validar fecha de expiración MM/AA"""
    try:
        month, year = expiry_date.split("/")
        month = int(month.strip())
        year = int(year.strip())
        
        # Añadir el siglo (asumimos tarjetas del siglo 21)
        full_year = 2000 + year
        
        # Validar mes
        if month < 1 or month > 12:
            return False
        
        # Validar que no esté expirada
        current_date = datetime.now(timezone.utc)
        expiry_date_obj = datetime(full_year, month, 1, tzinfo=timezone.utc)
        
        return expiry_date_obj > current_date
    except:
        return False

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)

async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar en usuarios normales que sean admin
        user_data = await db.users.find_one({"id": user_id})
        if user_data and user_data.get("is_admin", False):
            return user_data
        
        # Buscar en la colección de admin_users
        admin_user = await db.admin_users.find_one({"id": user_id})
        if admin_user:
            return admin_user
            
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== PAYMENT ROUTES ====================

api_router = APIRouter(prefix="/api")

@api_router.post("/payments/process", response_model=PaymentResponse)
async def process_payment(
    payment_request: PaymentRequest,
    current_user_id: str = Depends(get_current_user)
):
    try:
        # Validar que el monto coincida con el carrito actual
        cart = await _get_or_create_cart(current_user_id)
        enriched_cart = await _enrich_cart(cart)
        cart_total = sum(item["price"] * item["quantity"] for item in enriched_cart["items"])
        
        if abs(payment_request.amount - cart_total) > 0.01:  # Permitir pequeñas diferencias por redondeo
            return PaymentResponse(success=False, error="El monto no coincide con el carrito actual")
        
        # Resto de la lógica original de procesamiento de pago
        if not validate_card_number(payment_request.card.cardNumber):
            return PaymentResponse(success=False, error="Número de tarjeta inválido")
        
        if not validate_expiry_date(payment_request.card.expiryDate):
            return PaymentResponse(success=False, error="Fecha de expiración inválida o tarjeta expirada")
        
        # Validar CVV (3-4 dígitos)
        cvv = payment_request.card.cvv
        if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
            return PaymentResponse(success=False, error="CVV inválido")
        
        # Simular procesamiento de pago
        success = secrets.SystemRandom().random() > 0.3
        
        if success:
            transaction_id = f"TXN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
            
            transaction_data = {
                "id": str(uuid.uuid4()),
                "transaction_id": transaction_id,
                "email": payment_request.email,
                "user_id": current_user_id,
                "amount": payment_request.amount,
                "currency": payment_request.currency,
                "card_last_four": payment_request.card.cardNumber[-4:],
                "card_type": get_card_type(payment_request.card.cardNumber),
                "status": "completed",
                "order_id": payment_request.order_id,
                "created_at": datetime.now(timezone.utc)
            }
            
            await db.payment_transactions.insert_one(transaction_data)
            
            if payment_request.order_id:
                await db.orders.update_one(
                    {"id": payment_request.order_id},
                    {"$set": {"status": "paid", "payment_session_id": transaction_id}}
                )
            
            return PaymentResponse(success=True, transactionId=transaction_id)
        else:
            return PaymentResponse(success=False, error="Tarjeta rechazada por el banco emisor")
            
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        return PaymentResponse(success=False, error="Error interno del servidor")
    

@api_router.post("/payments/validate-card", response_model=CardValidationResponse)
async def validate_card(card_request: CardValidationRequest):
    """
    Validar los datos de una tarjeta de crédito/débito
    """
    try:
        # Validar número de tarjeta
        if not validate_card_number(card_request.cardNumber):
            return CardValidationResponse(valid=False, error="Número de tarjeta inválido")
        
        # Validar fecha de expiración
        if not validate_expiry_date(card_request.expiryDate):
            return CardValidationResponse(valid=False, error="Fecha de expiración inválida o tarjeta expirada")
        
        # Validar CVV
        cvv = card_request.cvv
        if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
            return CardValidationResponse(valid=False, error="CVV inválido")
        
        # Determinar tipo de tarjeta
        card_type = get_card_type(card_request.cardNumber)
        
        return CardValidationResponse(valid=True, cardType=card_type)
        
    except Exception as e:
        logger.error(f"Error validating card: {str(e)}")
        return CardValidationResponse(valid=False, error="Error interno del servidor")

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)

async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar en usuarios normales que sean admin
        user_data = await db.users.find_one({"id": user_id})
        if user_data and user_data.get("is_admin", False):
            return user_data
        
        # Buscar en la colección de admin_users
        admin_user = await db.admin_users.find_one({"id": user_id})
        if admin_user:
            return admin_user
            
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== PAYMENT ROUTES ====================

api_router = APIRouter(prefix="/api")

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)

async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar en usuarios normales que sean admin
        user_data = await db.users.find_one({"id": user_id})
        if user_data and user_data.get("is_admin", False):
            return user_data
        
        # Buscar en la colección de admin_users
        admin_user = await db.admin_users.find_one({"id": user_id})
        if admin_user:
            return admin_user
            
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== PAYMENT ROUTES ====================

api_router = APIRouter(prefix="/api")

@api_router.post("/payments/validate-card", response_model=CardValidationResponse)
async def validate_card(card_request: CardValidationRequest):
    """
    Validar los datos de una tarjeta de crédito/débito
    """
    try:
        # Validar número de tarjeta
        if not validate_card_number(card_request.cardNumber):
            return CardValidationResponse(valid=False, error="Número de tarjeta inválido")
        
        # Validar fecha de expiración
        if not validate_expiry_date(card_request.expiryDate):
            return CardValidationResponse(valid=False, error="Fecha de expiración inválida o tarjeta expirada")
        
        # Validar CVV
        cvv = card_request.cvv
        if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
            return CardValidationResponse(valid=False, error="CVV inválido")
        
        # Determinar tipo de tarjeta
        card_type = get_card_type(card_request.cardNumber)
        
        return CardValidationResponse(valid=True, cardType=card_type)
        
    except Exception as e:
        logger.error(f"Error validating card: {str(e)}")
        return CardValidationResponse(valid=False, error="Error interno del servidor")

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)

async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar en usuarios normales que sean admin
        user_data = await db.users.find_one({"id": user_id})
        if user_data and user_data.get("is_admin", False):
            return user_data
        
        # Buscar en la colección de admin_users
        admin_user = await db.admin_users.find_one({"id": user_id})
        if admin_user:
            return admin_user
            
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== ORDERS ROUTES ====================

@api_router.get("/orders/summary/{order_id}")
async def get_order_summary(order_id: str, current_user_id: str = Depends(get_current_user)):
    """
    Obtener resumen de un pedido para procesar pago
    """
    try:
        # Buscar el pedido
        order = await db.orders.find_one({"id": order_id, "user_id": current_user_id})
        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        
        # Enriquecer los items del pedido con información del producto
        enriched_items = []
        total_amount = 0
        
        for item in order.get("items", []):
            product = await db.products.find_one({"id": item["product_id"]})
            if product:
                item_total = product["price"] * item["quantity"]
                total_amount += item_total
                
                enriched_items.append({
                    "id": item["product_id"],
                    "name": product["name"],
                    "description": product["description"],
                    "quantity": item["quantity"],
                    "price": product["price"],
                    "total": item_total,
                    "image_url": product.get("image_url")
                })
        
        return {
    "order_id": order_id,
    "items": enriched_items,
    "total_amount": total_amount,
    "currency": "COP",  # Cambiar de "$" a "COP"
    "status": order.get("status", "pending")
}
        
    except Exception as e:
        logger.error(f"Error getting order summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener resumen del pedido")
    
#===================== ADMIN ====================

class AdminUser(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    name: str
    is_admin: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    requires_prescription: Optional[bool] = None
    active: Optional[bool] = None

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_jwt_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def generate_admin_token() -> str:
    return secrets.token_urlsafe(32)

async def get_current_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar en usuarios normales que sean admin
        user_data = await db.users.find_one({"id": user_id})
        if user_data and user_data.get("is_admin", False):
            return user_data
        
        # Buscar en la colección de admin_users
        admin_user = await db.admin_users.find_one({"id": user_id})
        if admin_user:
            return admin_user
            
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== PRODUCTS DATA ====================

PHARMACY_PRODUCTS = [
    {
        "name": "Paracetamol 500mg",
        "description": "Analgésico y antipirético para alivio del dolor y fiebre",
        "price": 8500,  # Cambiar de 8.50 a 8500 (pesos colombianos)
        "category": "over_counter",
        "stock": 100,
        "image_url": "https://images.unsplash.com/photo-1631549916768-4119b2e5f926?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHw0fHxwaGFybWFjeXxlbnwwfHx8fDE3NTYyNTEyMjd8MA&ixlib=rb-4.1.0&q=85",
        "requires_prescription": False
    },
    {
        "name": "Ibuprofeno 400mg",
        "description": "Antiinflamatorio no esteroideo para dolor e inflamación",
        "price": 12000,  # Cambiar de 12.00 a 12000
        "category": "over_counter",
        "stock": 85,
        "image_url": "https://images.pexels.com/photos/139398/thermometer-headache-pain-pills-139398.jpeg",
        "requires_prescription": False
    },
    # ... actualizar todos los precios de manera similar
]

# ==================== LIFESPAN HANDLER ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    
    # Initialize database with sample products
    existing_products = await db.products.count_documents({})
    if existing_products == 0:
        logger.info("Initializing database with sample products...")
        for product_data in PHARMACY_PRODUCTS:
            product = Product(**product_data)
            await db.products.insert_one(product.dict())
        logger.info("Sample products added successfully!")
    
    # Crear administrador por defecto si no existe
    admin_email = "admin@farmachelo.com"
    existing_admin = await db.admin_users.find_one({"email": admin_email})
    if not existing_admin:
        logger.info("Creating default admin user...")
        admin_data = {
            "email": admin_email,
            "password": hash_password("admin123"),
            "name": "Administrador Principal",
            "is_admin": True,
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc)
        }
        await db.admin_users.insert_one(admin_data)
        logger.info("Default admin user created! Email: admin@farmachelo.com, Password: admin123")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    client.close()

# FastAPI app with lifespan
app = FastAPI(
    title="Farmachelo API", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Farmachelo API - Farmacia Online"}

# Authentication Routes
@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_dict = user_data.dict()
    user_dict["password"] = hash_password(user_data.password)
    user = User(**{k: v for k, v in user_dict.items() if k != "password"}, is_admin=False)
    
    await db.users.insert_one({**user.dict(), "password": user_dict["password"]})
    
    # Create JWT token
    token = create_jwt_token(user.id)
    
    return {"user": user, "token": token}

@api_router.post("/auth/login")
async def login(login_data: UserLogin):
    # Buscar usuario normal
    user_data = await db.users.find_one({"email": login_data.email})
    if user_data and verify_password(login_data.password, user_data["password"]):
        user = User(**{k: v for k, v in user_data.items() if k != "password"})
        token = create_jwt_token(user.id)
        return {"user": user, "token": token}
    # Si no existe, permitir login de admin heredado con el mismo flujo
    admin_data = await db.admin_users.find_one({"email": login_data.email})
    if admin_data and verify_password(login_data.password, admin_data.get("password", "")):
        admin_user = User(
            id=admin_data["id"],
            email=admin_data["email"],
            name=admin_data.get("name", "Administrador"),
            phone=None,
            address=None,
            is_verified=True,
            is_admin=True,
            created_at=admin_data.get("created_at", datetime.now(timezone.utc))
        )
        token = create_jwt_token(admin_user.id)
        return {"user": admin_user, "token": token}
    raise HTTPException(status_code=401, detail="Invalid email or password")

@api_router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    user_data = await db.users.find_one({"id": current_user_id})
    if user_data:
        return User(**{k: v for k, v in user_data.items() if k != "password"})
    admin_data = await db.admin_users.find_one({"id": current_user_id})
    if admin_data:
        return User(
            id=admin_data["id"],
            email=admin_data["email"],
            name=admin_data.get("name", "Administrador"),
            phone=None,
            address=None,
            is_verified=True,
            is_admin=True,
            created_at=admin_data.get("created_at", datetime.now(timezone.utc))
        )
    raise HTTPException(status_code=404, detail="User not found")

# Products Routes
@api_router.get("/products", response_model=List[Product])
async def get_products(category: Optional[str] = None, search: Optional[str] = None):
    query = {"active": True}
    if category:
        query["category"] = category
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    products = await db.products.find(query).to_list(100)
    return [Product(**product) for product in products]

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    product_data = await db.products.find_one({"id": product_id, "active": True})
    if not product_data:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product_data)

# Cart helpers
async def _get_or_create_cart(user_id: str) -> Cart:
    cart_data = await db.carts.find_one({"user_id": user_id})
    if not cart_data:
        cart = Cart(user_id=user_id)
        await db.carts.insert_one(cart.dict())
        return cart
    return Cart(**cart_data)

async def _enrich_cart(cart: Cart) -> Dict[str, Any]:
    # Adjuntar datos de producto a cada item
    enriched_items: List[Dict[str, Any]] = []
    for item in cart.items:
        product = await db.products.find_one({"id": item.product_id})
        enriched_items.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "prescription_file": item.prescription_file,
            "name": product.get("name") if product else "Producto",
            "price": float(product.get("price", 0)),
            "image_url": product.get("image_url") if product else None,
            "requires_prescription": bool(product.get("requires_prescription", False)) if product else False,
            "id": item.product_id
        })
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": enriched_items,
        "updated_at": cart.updated_at,
    }

# Cart Routes (alineados con el frontend)
@api_router.get("/cart")
async def get_cart(current_user_id: str = Depends(get_current_user)):
    cart = await _get_or_create_cart(current_user_id)
    return await _enrich_cart(cart)

@api_router.post("/cart/items")
async def add_cart_item(cart_item: CartItem, current_user_id: str = Depends(get_current_user)):
    # Verificar producto
    product = await db.products.find_one({"id": cart_item.product_id, "active": True})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = await _get_or_create_cart(current_user_id)
    # Buscar item existente
    index = next((i for i, it in enumerate(cart.items) if it.product_id == cart_item.product_id), None)
    if index is not None:
        cart.items[index].quantity += max(1, cart_item.quantity)
    else:
        if cart_item.quantity <= 0:
            cart_item.quantity = 1
        cart.items.append(cart_item)
    cart.updated_at = datetime.now(timezone.utc)
    await db.carts.update_one({"user_id": current_user_id}, {"$set": cart.dict()}, upsert=True)
    return await _enrich_cart(cart)

@api_router.put("/cart/items/{product_id}")
async def update_cart_item(product_id: str, payload: Dict[str, int], current_user_id: str = Depends(get_current_user)):
    quantity = int(payload.get("quantity", 1))
    if quantity < 0:
        quantity = 0
    cart = await _get_or_create_cart(current_user_id)
    index = next((i for i, it in enumerate(cart.items) if it.product_id == product_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    if quantity == 0:
        cart.items = [it for it in cart.items if it.product_id != product_id]
    else:
        cart.items[index].quantity = quantity
    cart.updated_at = datetime.now(timezone.utc)
    await db.carts.update_one({"user_id": current_user_id}, {"$set": cart.dict()})
    return await _enrich_cart(cart)

@api_router.delete("/cart/items/{product_id}")
async def delete_cart_item(product_id: str, current_user_id: str = Depends(get_current_user)):
    cart = await _get_or_create_cart(current_user_id)
    original_len = len(cart.items)
    cart.items = [it for it in cart.items if it.product_id != product_id]
    if original_len == len(cart.items):
        # No existe el item, pero devolvemos el carrito igualmente
        return await _enrich_cart(cart)
    cart.updated_at = datetime.now(timezone.utc)
    await db.carts.update_one({"user_id": current_user_id}, {"$set": cart.dict()})
    return await _enrich_cart(cart)

# Payment Routes
@api_router.post("/payments/checkout")
async def create_checkout_session(
    checkout_data: CheckoutRequest, 
    current_user_id: str = Depends(get_current_user),
    request: Request = None
):
    # Implementar integración con Stripe u otro procesador de pagos
    return {"message": "Checkout functionality to be implemented with your payment processor"}

# Orders Routes
@api_router.get("/orders", response_model=List[Order])
async def get_user_orders(current_user_id: str = Depends(get_current_user)):
    orders = await db.orders.find({"user_id": current_user_id}).sort("created_at", -1).to_list(50)
    return [Order(**order) for order in orders]

# Admin Authentication Routes
@api_router.post("/admin/register")
async def admin_register(admin_data: AdminUserCreate):
    # Verificar si el administrador ya existe
    existing_admin = await db.admin_users.find_one({"email": admin_data.email})
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin already registered")
    
    # Crear administrador
    admin_dict = admin_data.dict()
    admin_dict["password"] = hash_password(admin_data.password)
    admin = AdminUser(**{k: v for k, v in admin_dict.items() if k != "password"})
    
    await db.admin_users.insert_one({**admin.dict(), "password": admin_dict["password"]})
    
    # Crear token de administrador (válido por 24 horas)
    admin_token = generate_admin_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    await db.admin_tokens.insert_one({
        "token": admin_token,
        "admin_id": admin.id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at
    })
    
    return {"admin": admin, "token": admin_token}

@api_router.post("/admin/login")
async def admin_login(login_data: AdminLogin):
    # Emitir JWT estándar cuando el admin es válido
    admin_data = await db.admin_users.find_one({"email": login_data.email})
    if not admin_data or not verify_password(login_data.password, admin_data["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    admin = AdminUser(**{k: v for k, v in admin_data.items() if k != "password"})
    token = create_jwt_token(admin.id)
    return {"admin": admin, "token": token}

@api_router.post("/admin/logout")
async def admin_logout(current_admin: dict = Depends(get_current_admin)):
    # Con JWT stateless no hay que eliminar nada del servidor
    return {"message": "Logged out successfully"}

# Admin Product Management Routes
@api_router.post("/admin/products", response_model=Product)
async def create_product(
    product_data: ProductCreate, 
    current_admin: dict = Depends(get_current_admin)
):
    # Crear producto
    product = Product(**product_data.dict())
    await db.products.insert_one(product.dict())
    return product

@api_router.put("/admin/products/{product_id}", response_model=Product)
async def update_product(
    product_id: str, 
    product_data: ProductUpdate, 
    current_admin: dict = Depends(get_current_admin)
):
    # Verificar si el producto existe
    existing_product = await db.products.find_one({"id": product_id})
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Actualizar solo los campos proporcionados
    update_data = {k: v for k, v in product_data.dict() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.products.update_one(
        {"id": product_id}, 
        {"$set": update_data}
    )
    
    # Obtener el producto actualizado
    updated_product = await db.products.find_one({"id": product_id})
    return Product(**updated_product)

@api_router.delete("/admin/products/{product_id}")
async def delete_product(
    product_id: str, 
    current_admin: dict = Depends(get_current_admin)
):
    # Verificar si el producto existe
    existing_product = await db.products.find_one({"id": product_id})
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Eliminar producto
    await db.products.delete_one({"id": product_id})
    
    return {"message": "Product deleted successfully"}

# Endpoint para subir imágenes (opcional)
@api_router.post("/admin/upload-image")
async def upload_image(
    file: UploadFile = File(...), 
    current_admin: dict = Depends(get_current_admin)
):
    # Crear directorio de uploads si no existe
    upload_dir = ROOT_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)
    
    # Generar nombre único para el archivo
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{secrets.token_urlsafe(8)}.{file_extension}"
    file_path = upload_dir / unique_filename
    
    # Guardar el archivo
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Devolver la URL relativa del archivo
    return {"image_url": f"/uploads/{unique_filename}"}

def FileResponse(file_path):
    from fastapi.responses import FileResponse as FastAPIFileResponse
    return FastAPIFileResponse(file_path)

# Servir archivos estáticos (para las imágenes subidas)
@app.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    file_path = ROOT_DIR / "uploads" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# Include router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)