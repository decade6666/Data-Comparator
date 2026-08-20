"""共享 FastAPI 依赖：从 JWT 解析当前用户并校验身份。"""

import jwt
from fastapi import Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..backend.application.auth_service import create_access_token, decode_token
from ..backend.infrastructure.database import read_session
from ..backend.infrastructure.models.user import User

_REFRESHED_TOKEN_HEADER = "X-Refreshed-Token"
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    response: Response,
    token: str = Depends(_oauth2_scheme),
    session: Session = Depends(read_session),
) -> User:
    """从 Bearer token 解码并返回当前用户；无效/停用/版本不符返回 401。"""
    if not token:
        raise HTTPException(status_code=401, detail="未授权")
    try:
        identity = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="未授权")

    user = session.get(User, identity.user_id)
    if user is None or user.username != identity.username:
        raise HTTPException(status_code=401, detail="未授权")
    if user.auth_version != identity.auth_version:
        raise HTTPException(status_code=401, detail="未授权")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="账号已停用")
    response.headers[_REFRESHED_TOKEN_HEADER] = create_access_token(
        user.id, user.username, user.auth_version
    )
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """校验当前用户为管理员，不满足返回 403。"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user
