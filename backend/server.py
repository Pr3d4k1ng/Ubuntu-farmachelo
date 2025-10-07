from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
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
from contextlib import asynccontextmanager

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MySQL connection
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'Cod1029144695')
MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DB = os.environ.get('MYSQL_DB', 'farmachelo_db')

# Crear engine de SQLAlchemy
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

# ==================== DATABASE MODELS ====================

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    password = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(String(36), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    stock = Column(Integer, nullable=False)
    image_url = Column(Text, nullable=True)
    requires_prescription = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Cart(Base):
    __tablename__ = "carts"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CartItem(Base):
    __tablename__ = "cart_items"
    
    id = Column(String(36), primary_key=True, index=True)
    cart_id = Column(String(36), ForeignKey('carts.id'), nullable=False)
    product_id = Column(String(36), ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    prescription_file = Column(Text, nullable=True)

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(50), default="pending")
    payment_session_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(String(36), primary_key=True, index=True)
    order_id = Column(String(36), ForeignKey('orders.id'), nullable=False)
    product_id = Column(String(36), ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    prescription_file = Column(Text, nullable=True)

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(String(36), primary_key=True, index=True)
    transaction_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="COP")
    card_last_four = Column(String(4), nullable=True)
    card_type = Column(String(50), nullable=True)
    status = Column(String(50), default="pending")
    order_id = Column(String(36), ForeignKey('orders.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ==================== PYDANTIC MODELS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    is_verified: bool = False
    is_admin: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category: str
    stock: int
    image_url: Optional[str] = None
    requires_prescription: bool = False

class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    stock: int
    image_url: Optional[str] = None
    requires_prescription: bool = False
    active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

class CartItemModel(BaseModel):
    product_id: str
    quantity: int
    prescription_file: Optional[str] = None

class CartResponse(BaseModel):
    id: str
    user_id: str
    items: List[Dict[str, Any]]
    updated_at: datetime

class OrderResponse(BaseModel):
    id: str
    user_id: str
    items: List[Dict[str, Any]]
    total_amount: float
    status: str = "pending"
    payment_session_id: Optional[str] = None
    created_at: datetime

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
    currency: str = "COP"
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

class CheckoutRequest(BaseModel):
    cart_items: List[CartItemModel]
    origin_url: str

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

# ==================== DATABASE DEPENDENCY ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> str:
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

async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Buscar en usuarios normales que sean admin
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.is_admin:
            return user
        
        # Buscar en la colección de admin_users
        admin_user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
        if admin_user:
            return User(
                id=admin_user.id,
                email=admin_user.email,
                name=admin_user.name,
                is_verified=True,
                is_admin=True,
                created_at=admin_user.created_at
            )
            
        raise HTTPException(status_code=403, detail="Admin privileges required")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== LIFESPAN HANDLER ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - Crear tablas
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Inicializar datos de ejemplo
    db = SessionLocal()
    try:
        # Verificar si ya existen productos
        existing_products = db.query(Product).count()
        if existing_products == 0:
            logger.info("Initializing database with sample products...")
            
            sample_products = [
                Product(
                    id=str(uuid.uuid4()),
                    name="Paracetamol 500mg",
                    description="Analgésico y antipirético para alivio del dolor y fiebre",
                    price=8500.0,
                    category="over_counter",
                    stock=100,
                    image_url="https://images.unsplash.com/photo-1631549916768-4119b2e5f926?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2Mzl8MHwxfHNlYXJjaHw0fHxwaGFybWFjeXxlbnwwfHx8fDE3NTYyNTEyMjd8MA&ixlib=rb-4.1.0&q=85",
                    requires_prescription=False
                ),
                Product(
                    id=str(uuid.uuid4()),
                    name="Ibuprofeno 400mg",
                    description="Antiinflamatorio no esteroideo para dolor e inflamación",
                    price=12000.0,
                    category="over_counter",
                    stock=85,
                    image_url="https://images.pexels.com/photos/139398/thermometer-headache-pain-pills-139398.jpeg",
                    requires_prescription=False
                )
            ]
            
            for product in sample_products:
                db.add(product)
            db.commit()
            logger.info("Sample products added successfully!")
        
        # Crear administrador por defecto si no existe
        admin_email = "admin@farmachelo.com"
        existing_admin = db.query(AdminUser).filter(AdminUser.email == admin_email).first()
        if not existing_admin:
            logger.info("Creating default admin user...")
            admin_user = AdminUser(
                id=str(uuid.uuid4()),
                email=admin_email,
                name="Administrador Principal",
                password=hash_password("admin123")
            )
            db.add(admin_user)
            db.commit()
            logger.info("Default admin user created! Email: admin@farmachelo.com, Password: admin123")
            
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        db.rollback()
    finally:
        db.close()
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

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

api_router = APIRouter(prefix="/api")

# ==================== ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Farmachelo API - Farmacia Online"}

# Authentication Routes
@api_router.post("/auth/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        id=str(uuid.uuid4()),
        email=user_data.email,
        name=user_data.name,
        phone=user_data.phone,
        address=user_data.address,
        password=hash_password(user_data.password),
        is_admin=False
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create JWT token
    token = create_jwt_token(user.id)
    
    return {"user": UserResponse.from_orm(user), "token": token}

@api_router.post("/auth/login")
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    # Buscar usuario normal
    user = db.query(User).filter(User.email == login_data.email).first()
    if user and verify_password(login_data.password, user.password):
        token = create_jwt_token(user.id)
        return {"user": UserResponse.from_orm(user), "token": token}
    
    # Buscar admin user
    admin_user = db.query(AdminUser).filter(AdminUser.email == login_data.email).first()
    if admin_user and verify_password(login_data.password, admin_user.password):
        user_response = UserResponse(
            id=admin_user.id,
            email=admin_user.email,
            name=admin_user.name,
            phone=None,
            address=None,
            is_verified=True,
            is_admin=True,
            created_at=admin_user.created_at
        )
        token = create_jwt_token(admin_user.id)
        return {"user": user_response, "token": token}
    
    raise HTTPException(status_code=401, detail="Invalid email or password")

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user_id).first()
    if user:
        return UserResponse.from_orm(user)
    
    admin_user = db.query(AdminUser).filter(AdminUser.id == current_user_id).first()
    if admin_user:
        return UserResponse(
            id=admin_user.id,
            email=admin_user.email,
            name=admin_user.name,
            phone=None,
            address=None,
            is_verified=True,
            is_admin=True,
            created_at=admin_user.created_at
        )
    
    raise HTTPException(status_code=404, detail="User not found")

# Products Routes
@api_router.get("/products", response_model=List[ProductResponse])
async def get_products(
    category: Optional[str] = None, 
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Product).filter(Product.active == True)
    
    if category:
        query = query.filter(Product.category == category)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    products = query.all()
    return [ProductResponse.from_orm(product) for product in products]

@api_router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.from_orm(product)

# Cart helpers
async def _get_or_create_cart(user_id: str, db: Session) -> Cart:
    cart = db.query(Cart).filter(Cart.user_id == user_id).first()
    if not cart:
        cart = Cart(id=str(uuid.uuid4()), user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

async def _enrich_cart(cart: Cart, db: Session) -> Dict[str, Any]:
    cart_items = db.query(CartItem).filter(CartItem.cart_id == cart.id).all()
    enriched_items = []
    
    for item in cart_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            enriched_items.append({
                "product_id": item.product_id,
                "quantity": item.quantity,
                "prescription_file": item.prescription_file,
                "name": product.name,
                "price": float(product.price),
                "image_url": product.image_url,
                "requires_prescription": product.requires_prescription,
                "id": item.product_id
            })
    
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": enriched_items,
        "updated_at": cart.updated_at,
    }

# Cart Routes
@api_router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cart = await _get_or_create_cart(current_user_id, db)
    return await _enrich_cart(cart, db)

@api_router.post("/cart/items")
async def add_cart_item(
    cart_item: CartItemModel,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verificar producto
    product = db.query(Product).filter(Product.id == cart_item.product_id, Product.active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = await _get_or_create_cart(current_user_id, db)
    
    # Buscar item existente
    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == cart_item.product_id
    ).first()
    
    if existing_item:
        existing_item.quantity += max(1, cart_item.quantity)
    else:
        new_item = CartItem(
            id=str(uuid.uuid4()),
            cart_id=cart.id,
            product_id=cart_item.product_id,
            quantity=max(1, cart_item.quantity),
            prescription_file=cart_item.prescription_file
        )
        db.add(new_item)
    
    cart.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return await _enrich_cart(cart, db)

@api_router.put("/cart/items/{product_id}")
async def update_cart_item(
    product_id: str, 
    payload: Dict[str, int], 
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    quantity = int(payload.get("quantity", 1))
    if quantity < 0:
        quantity = 0
    
    cart = await _get_or_create_cart(current_user_id, db)
    cart_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    if quantity == 0:
        db.delete(cart_item)
    else:
        cart_item.quantity = quantity
    
    cart.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return await _enrich_cart(cart, db)

@api_router.delete("/cart/items/{product_id}")
async def delete_cart_item(
    product_id: str, 
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cart = await _get_or_create_cart(current_user_id, db)
    cart_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == product_id
    ).first()
    
    if cart_item:
        db.delete(cart_item)
        cart.updated_at = datetime.now(timezone.utc)
        db.commit()
    
    return await _enrich_cart(cart, db)

# Payment Routes
@api_router.post("/payments/process", response_model=PaymentResponse)
async def process_payment(
    payment_request: PaymentRequest,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Validar que el monto coincida con el carrito actual
        cart = await _get_or_create_cart(current_user_id, db)
        enriched_cart = await _enrich_cart(cart, db)
        cart_total = sum(item["price"] * item["quantity"] for item in enriched_cart["items"])
        
        if abs(payment_request.amount - cart_total) > 0.01:
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
            
            transaction_data = PaymentTransaction(
                id=str(uuid.uuid4()),
                transaction_id=transaction_id,
                email=payment_request.email,
                user_id=current_user_id,
                amount=payment_request.amount,
                currency=payment_request.currency,
                card_last_four=payment_request.card.cardNumber[-4:],
                card_type=get_card_type(payment_request.card.cardNumber),
                status="completed",
                order_id=payment_request.order_id
            )
            
            db.add(transaction_data)
            
            if payment_request.order_id:
                order = db.query(Order).filter(Order.id == payment_request.order_id).first()
                if order:
                    order.status = "paid"
                    order.payment_session_id = transaction_id
            
            db.commit()
            
            return PaymentResponse(success=True, transactionId=transaction_id)
        else:
            return PaymentResponse(success=False, error="Tarjeta rechazada por el banco emisor")
            
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        db.rollback()
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

@api_router.post("/payments/checkout")
async def create_checkout_session(
    checkout_data: CheckoutRequest, 
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Calcular el total del carrito
        total_amount = 0
        for item in checkout_data.cart_items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                total_amount += product.price * item.quantity
        
        # Crear orden
        order = Order(
            id=str(uuid.uuid4()),
            user_id=current_user_id,
            total_amount=total_amount,
            status="pending"
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        
        # Crear items de la orden
        for item in checkout_data.cart_items:
            order_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                prescription_file=item.prescription_file
            )
            db.add(order_item)
        
        db.commit()
        
        return {
            "order_id": order.id,
            "total_amount": total_amount,
            "currency": "COP",
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear sesión de checkout")

# Orders Routes
@api_router.get("/orders", response_model=List[OrderResponse])
async def get_user_orders(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    orders = db.query(Order).filter(Order.user_id == current_user_id).order_by(Order.created_at.desc()).all()
    
    orders_response = []
    for order in orders:
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        items = []
        for item in order_items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                items.append({
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "prescription_file": item.prescription_file,
                    "name": product.name,
                    "price": product.price
                })
        
        orders_response.append(OrderResponse(
            id=order.id,
            user_id=order.user_id,
            items=items,
            total_amount=order.total_amount,
            status=order.status,
            payment_session_id=order.payment_session_id,
            created_at=order.created_at
        ))
    
    return orders_response

@api_router.get("/orders/summary/{order_id}")
async def get_order_summary(
    order_id: str, 
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener resumen de un pedido para procesar pago
    """
    try:
        # Buscar el pedido
        order = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        
        # Obtener items del pedido
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
        enriched_items = []
        total_amount = 0
        
        for item in order_items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if product:
                item_total = product.price * item.quantity
                total_amount += item_total
                
                enriched_items.append({
                    "id": item.product_id,
                    "name": product.name,
                    "description": product.description,
                    "quantity": item.quantity,
                    "price": product.price,
                    "total": item_total,
                    "image_url": product.image_url
                })
        
        return {
            "order_id": order_id,
            "items": enriched_items,
            "total_amount": total_amount,
            "currency": "COP",
            "status": order.status
        }
        
    except Exception as e:
        logger.error(f"Error getting order summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener resumen del pedido")

# Admin Authentication Routes
@api_router.post("/admin/register")
async def admin_register(admin_data: AdminUserCreate, db: Session = Depends(get_db)):
    # Verificar si el administrador ya existe
    existing_admin = db.query(AdminUser).filter(AdminUser.email == admin_data.email).first()
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin already registered")
    
    # Crear administrador
    admin_user = AdminUser(
        id=str(uuid.uuid4()),
        email=admin_data.email,
        name=admin_data.name,
        password=hash_password(admin_data.password)
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    # Crear token JWT
    token = create_jwt_token(admin_user.id)
    
    return {"admin": admin_user, "token": token}

@api_router.post("/admin/login")
async def admin_login(login_data: AdminLogin, db: Session = Depends(get_db)):
    # Buscar admin user
    admin_user = db.query(AdminUser).