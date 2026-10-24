"""用户注册 / 登录。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..database import create_user, get_user_by_name
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=64)


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterIn):
    if get_user_by_name(body.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    user_id = create_user(body.username, hash_password(body.password))
    return {
        "user_id": user_id,
        "username": body.username,
        "token": create_token(user_id),
    }


@router.post("/login")
def login(body: LoginIn):
    user = get_user_by_name(body.username)
    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "user_id": user["id"],
        "username": user["username"],
        "token": create_token(user["id"]),
    }
