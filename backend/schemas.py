
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

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
