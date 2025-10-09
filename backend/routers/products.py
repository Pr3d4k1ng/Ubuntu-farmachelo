
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.get("/products", response_model=List[schemas.ProductResponse])
async def get_products(
    category: Optional[str] = None, 
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Product).filter(models.Product.active == True)
    
    if category:
        query = query.filter(models.Product.category == category)
    if search:
        query = query.filter(models.Product.name.ilike(f"%{search}%"))
    
    products = query.all()
    return [schemas.ProductResponse.from_orm(product) for product in products]

@router.get("/products/{product_id}", response_model=schemas.ProductResponse)
async def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return schemas.ProductResponse.from_orm(product)
