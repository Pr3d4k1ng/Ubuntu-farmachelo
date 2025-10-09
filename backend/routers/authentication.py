
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter()

@router.post("/auth/register")
async def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = models.User(
        id=str(uuid.uuid4()),
        email=user_data.email,
        name=user_data.name,
        phone=user_data.phone,
        address=user_data.address,
        password=auth.hash_password(user_data.password),
        is_admin=False
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    token = auth.create_jwt_token(user.id)
    
    return {"user": schemas.UserResponse.from_orm(user), "token": token}

@router.post("/auth/login")
async def login(login_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == login_data.email).first()
    if user and auth.verify_password(login_data.password, user.password):
        token = auth.create_jwt_token(user.id)
        return {"user": schemas.UserResponse.from_orm(user), "token": token}
    
    admin_user = db.query(models.AdminUser).filter(models.AdminUser.email == login_data.email).first()
    if admin_user and auth.verify_password(login_data.password, admin_user.password):
        user_response = schemas.UserResponse(
            id=admin_user.id,
            email=admin_user.email,
            name=admin_user.name,
            phone=None,
            address=None,
            is_verified=True,
            is_admin=True,
            created_at=admin_user.created_at
        )
        token = auth.create_jwt_token(admin_user.id)
        return {"user": user_response, "token": token}
    
    raise HTTPException(status_code=401, detail="Invalid email or password")

@router.get("/auth/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if user:
        return schemas.UserResponse.from_orm(user)
    
    admin_user = db.query(models.AdminUser).filter(models.AdminUser.id == current_user_id).first()
    if admin_user:
        return schemas.UserResponse(
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
