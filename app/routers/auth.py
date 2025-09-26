from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorClient
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId

from app.dependencies.auth import get_mongo_client
from app.models.schemas import User, Token, Message
from config import SECRET_KEY, ALGORITHM

router = APIRouter()

# Placeholder for a simple password verification function.
# In a real app, you would use a secure hashing algorithm like bcrypt.
async def verify_password(plain_password, hashed_password):
    return plain_password == hashed_password

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=Message)
async def register_user(
    email: str = Form(...),
    password: str = Form(...),
    is_teacher: bool = Form(False),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    db = mongo_client["plagiarism_detector"]  # Specify database name
    users_col = db["users"]
    
    # Check if user already exists
    existing_user = await users_col.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # In a real app, hash the password here
    user_doc = {
        "email": email,
        "password": password,  # Store hashed password in real app
        "is_active": True,
        "is_teacher": is_teacher,
    }
    result = await users_col.insert_one(user_doc)
    
    return {"message": "User registered successfully"}

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client)
):
    db = mongo_client["plagiarism_detector"]  # Specify database name
    users_col = db["users"]
    
    user_doc = await users_col.find_one({"email": form_data.username})
    if not user_doc or not await verify_password(form_data.password, user_doc["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fix the user instantiation
    user_doc["id"] = str(user_doc["_id"])
    user = User(**user_doc)
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": str(user_doc["_id"])}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}