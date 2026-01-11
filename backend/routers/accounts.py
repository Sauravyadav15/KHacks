# accounts.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import sqlite3

#THIS NEEDS TO REMAIN PRIVATE, fine for now since we have no user data to secure
SECRET_KEY = "07491e256c50c40b71a9ddc14d90e0dd438d8863fe00ae90abc3b72878bb0741"
ALGORITHM = "HS256"
# CHANGED: Increased expiry from 30 minutes to ~10 years (5,256,000 minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 5256000

# Initialize router
router = APIRouter(prefix="/accounts", tags=["Accounts"])

def init_db():
    conn = sqlite3.connect('account_info.db')
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            account_active INTEGER NOT NULL DEFAULT 1
        );
        """
    )

    conn.commit()
    conn.close()

init_db()

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    account_active: bool | None = None

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    password: str

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def username_exists(username: str) -> bool:
    conn = sqlite3.connect("account_info.db")
    c = conn.cursor()
    c.execute(
        "SELECT 1 FROM accounts WHERE username = ? LIMIT 1;",
        (username,),
    )
    row = c.fetchone()
    conn.close()
    return row is not None

def get_user_by_email(email: str) -> UserInDB | None:
    conn = sqlite3.connect("account_info.db")  # Fix: use account_info.db
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, username, full_name, email, hashed_password, account_active FROM accounts WHERE email = ? LIMIT 1;", (email,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    return UserInDB(**dict(row))

def get_user(username:str):
    conn = sqlite3.connect("account_info.db")
    conn.row_factory = sqlite3.Row  # allows name-based access
    c = conn.cursor()
    c.execute(
        """
        SELECT id, username, full_name, email, hashed_password, account_active
        FROM accounts
        WHERE username = ?
        LIMIT 1;
        """,
        (username,),
    )
    row = c.fetchone()
    conn.close()
    if row is None:
        return None
    
    return UserInDB(**dict(row))

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credential_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception
        
        token_data = TokenData(username=username)
    except JWTError:
        raise credential_exception
    
    user = get_user(username=token_data.username)
    if user is None:
        raise credential_exception
    
    return user

@router.post("/signin/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect Username or Password", headers={"WWW-Authenticate": "Bearer"})
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta= access_token_expires)
    return {"access_token" : access_token, "token_type" : "bearer"}

@router.post("/register")
async def register_user(user: UserCreate):
    if username_exists(user.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    conn = sqlite3.connect("account_info.db")
    c = conn.cursor()
    hashed_password = get_password_hash(user.password)
    c.execute(
        "INSERT INTO accounts (username, full_name, email, hashed_password, account_active) VALUES (?, ?, ?, ?, 1)",
        (user.username, user.full_name, user.email, hashed_password)
    )
    conn.commit()
    conn.close()
    return {"message": "User created successfully"}

