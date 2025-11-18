"""Authentication schemas"""
from pydantic import BaseModel, UUID4


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str
    user_id: str


class TokenData(BaseModel):
    """Token payload data"""
    user_id: UUID4
