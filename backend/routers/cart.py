
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter()

async def _get_or_create_cart(user_id: str, db: Session) -> models.Cart:
    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
    if not cart:
        cart = models.Cart(id=str(uuid.uuid4()), user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart

async def _enrich_cart(cart: models.Cart, db: Session) -> Dict[str, Any]:
    cart_items = db.query(models.CartItem).filter(models.CartItem.cart_id == cart.id).all()
    enriched_items = []
    
    for item in cart_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
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

@router.get("/cart", response_model=schemas.CartResponse)
async def get_cart(
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    cart = await _get_or_create_cart(current_user_id, db)
    return await _enrich_cart(cart, db)

@router.post("/cart/items")
async def add_cart_item(
    cart_item: schemas.CartItemModel,
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == cart_item.product_id, models.Product.active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = await _get_or_create_cart(current_user_id, db)
    
    existing_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == cart_item.product_id
    ).first()
    
    if existing_item:
        existing_item.quantity += max(1, cart_item.quantity)
    else:
        new_item = models.CartItem(
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

@router.put("/cart/items/{product_id}")
async def update_cart_item(
    product_id: str, 
    payload: Dict[str, int], 
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    quantity = int(payload.get("quantity", 1))
    if quantity < 0:
        quantity = 0
    
    cart = await _get_or_create_cart(current_user_id, db)
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == product_id
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

@router.delete("/cart/items/{product_id}")
async def delete_cart_item(
    product_id: str, 
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    cart = await _get_or_create_cart(current_user_id, db)
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.cart_id == cart.id,
        models.CartItem.product_id == product_id
    ).first()
    
    if cart_item:
        db.delete(cart_item)
        cart.updated_at = datetime.now(timezone.utc)
        db.commit()
    
    return await _enrich_cart(cart, db)
