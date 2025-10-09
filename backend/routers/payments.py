
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import secrets
from datetime import datetime, timezone

from .. import models, schemas, auth
from ..database import get_db
from .cart import _get_or_create_cart, _enrich_cart

router = APIRouter()

def validate_card_number(card_number: str) -> bool:
    """Validar número de tarjeta usando el algoritmo de Luhn"""
    card_number = card_number.replace(" ", "")
    if not card_number.isdigit():
        return False
    
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
        
        full_year = 2000 + year
        
        if month < 1 or month > 12:
            return False
        
        current_date = datetime.now(timezone.utc)
        expiry_date_obj = datetime(full_year, month, 1, tzinfo=timezone.utc)
        
        return expiry_date_obj > current_date
    except:
        return False

@router.post("/payments/process", response_model=schemas.PaymentResponse)
async def process_payment(
    payment_request: schemas.PaymentRequest,
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        cart = await _get_or_create_cart(current_user_id, db)
        enriched_cart = await _enrich_cart(cart, db)
        cart_total = sum(item["price"] * item["quantity"] for item in enriched_cart["items"])
        
        if abs(payment_request.amount - cart_total) > 0.01:
            return schemas.PaymentResponse(success=False, error="El monto no coincide con el carrito actual")
        
        if not validate_card_number(payment_request.card.cardNumber):
            return schemas.PaymentResponse(success=False, error="Número de tarjeta inválido")
        
        if not validate_expiry_date(payment_request.card.expiryDate):
            return schemas.PaymentResponse(success=False, error="Fecha de expiración inválida o tarjeta expirada")
        
        cvv = payment_request.card.cvv
        if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
            return schemas.PaymentResponse(success=False, error="CVV inválido")
        
        success = secrets.SystemRandom().random() > 0.3
        
        if success:
            transaction_id = f"TXN_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}"
            
            transaction_data = models.PaymentTransaction(
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
                order = db.query(models.Order).filter(models.Order.id == payment_request.order_id).first()
                if order:
                    order.status = "paid"
                    order.payment_session_id = transaction_id
            
            db.commit()
            
            return schemas.PaymentResponse(success=True, transactionId=transaction_id)
        else:
            return schemas.PaymentResponse(success=False, error="Tarjeta rechazada por el banco emisor")
            
    except Exception as e:
        db.rollback()
        return schemas.PaymentResponse(success=False, error="Error interno del servidor")

@router.post("/payments/validate-card", response_model=schemas.CardValidationResponse)
async def validate_card(card_request: schemas.CardValidationRequest):
    try:
        if not validate_card_number(card_request.cardNumber):
            return schemas.CardValidationResponse(valid=False, error="Número de tarjeta inválido")
        
        if not validate_expiry_date(card_request.expiryDate):
            return schemas.CardValidationResponse(valid=False, error="Fecha de expiración inválida o tarjeta expirada")
        
        cvv = card_request.cvv
        if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
            return schemas.CardValidationResponse(valid=False, error="CVV inválido")
        
        card_type = get_card_type(card_request.cardNumber)
        
        return schemas.CardValidationResponse(valid=True, cardType=card_type)
        
    except Exception as e:
        return schemas.CardValidationResponse(valid=False, error="Error interno del servidor")

@router.post("/payments/checkout")
async def create_checkout_session(
    checkout_data: schemas.CheckoutRequest, 
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        total_amount = 0
        for item in checkout_data.cart_items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if product:
                total_amount += product.price * item.quantity
        
        order = models.Order(
            id=str(uuid.uuid4()),
            user_id=current_user_id,
            total_amount=total_amount,
            status="pending"
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        
        for item in checkout_data.cart_items:
            order_item = models.OrderItem(
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
        db.rollback()
        raise HTTPException(status_code=500, detail="Error al crear sesión de checkout")
