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