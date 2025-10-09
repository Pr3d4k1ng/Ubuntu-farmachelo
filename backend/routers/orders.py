
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter()

@router.get("/orders", response_model=List[schemas.OrderResponse])
async def get_user_orders(
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    orders = db.query(models.Order).filter(models.Order.user_id == current_user_id).order_by(models.Order.created_at.desc()).all()
    
    orders_response = []
    for order in orders:
        order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        items = []
        for item in order_items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if product:
                items.append({
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "prescription_file": item.prescription_file,
                    "name": product.name,
                    "price": product.price
                })
        
        orders_response.append(schemas.OrderResponse(
            id=order.id,
            user_id=order.user_id,
            items=items,
            total_amount=order.total_amount,
            status=order.status,
            payment_session_id=order.payment_session_id,
            created_at=order.created_at
        ))
    
    return orders_response

@router.get("/orders/summary/{order_id}")
async def get_order_summary(
    order_id: str, 
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtener resumen de un pedido para procesar pago
    """
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id, models.Order.user_id == current_user_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        
        order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).all()
        enriched_items = []
        total_amount = 0
        
        for item in order_items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
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
        raise HTTPException(status_code=500, detail="Error al obtener resumen del pedido")
