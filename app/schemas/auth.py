from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: str
    reviews_count: int = 0
    projects_count: int = 0
    files_analyzed: int = 0
    issues_detected: int = 0

class AuthResponse(BaseModel):
    token: str
    user: UserProfile

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
