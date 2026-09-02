import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET, USERS_FILE

security = HTTPBearer(auto_error=False)

ROLES = ("admin", "employee")


@dataclass
class User:
    id: str
    username: str
    role: str
    name: str
    email: str
    person_id: str | None = None

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "name": self.name,
            "email": self.email,
            "person_id": self.person_id,
        }


class UserStore:
    def __init__(self, users_file=USERS_FILE):
        self.users_file = users_file
        self._ensure_seed()

    def _ensure_seed(self) -> None:
        if self.users_file.exists():
            return
        default_password = "Admin@123"
        salt, password_hash = hash_password(default_password)
        payload = {
            "users": [
                {
                    "id": "user-admin",
                    "username": "admin",
                    "password_hash": password_hash,
                    "salt": salt,
                    "role": "admin",
                    "person_id": None,
                    "name": "System Administrator",
                    "email": "admin@company.com",
                }
            ]
        }
        self.users_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read(self) -> list[dict]:
        with self.users_file.open(encoding="utf-8") as handle:
            return json.load(handle).get("users", [])

    def _write(self, users: list[dict]) -> None:
        self.users_file.write_text(json.dumps({"users": users}, indent=2), encoding="utf-8")

    def list_users(self) -> list[User]:
        return [self._to_user(item) for item in self._read()]

    def get_by_id(self, user_id: str) -> User | None:
        for item in self._read():
            if item["id"] == user_id:
                return self._to_user(item)
        return None

    def get_by_username(self, username: str) -> tuple[User, dict] | tuple[None, None]:
        for item in self._read():
            if item["username"].lower() == username.lower():
                return self._to_user(item), item
        return None, None

    def authenticate(self, username: str, password: str) -> User | None:
        user, record = self.get_by_username(username)
        if not user or not record:
            return None
        if not verify_password(password, record["salt"], record["password_hash"]):
            return None
        return user

    def create_employee_user(
        self,
        username: str,
        password: str,
        person_id: str,
        name: str,
        email: str,
    ) -> User:
        if self.get_by_username(username)[0]:
            raise ValueError("Username already exists")

        users = self._read()
        salt, password_hash = hash_password(password)
        user_id = f"user-{person_id}"
        record = {
            "id": user_id,
            "username": username,
            "password_hash": password_hash,
            "salt": salt,
            "role": "employee",
            "person_id": person_id,
            "name": name,
            "email": email,
        }
        users.append(record)
        self._write(users)
        return self._to_user(record)

    def delete_user_by_person_id(self, person_id: str) -> bool:
        users = self._read()
        initial_len = len(users)
        users = [u for u in users if u.get("person_id") != person_id]
        if len(users) < initial_len:
            self._write(users)
            return True
        return False

    @staticmethod
    def _to_user(item: dict) -> User:
        return User(
            id=item["id"],
            username=item["username"],
            role=item["role"],
            name=item.get("name", item["username"]),
            email=item.get("email", ""),
            person_id=item.get("person_id"),
        )


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return salt, digest.hex()


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(digest.hex(), password_hash)


def create_access_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "role": user.role,
        "person_id": user.person_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@lru_cache
def get_user_store() -> UserStore:
    return UserStore()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    store: Annotated[UserStore, Depends(get_user_store)],
    token: str | None = None,
) -> User:
    raw_token = None
    if credentials and credentials.scheme and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(raw_token)
    user = store.get_by_id(payload.get("sub", ""))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: str):
    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(roles)}.",
            )
        return current_user

    return dependency


RequireAdmin = Annotated[User, Depends(require_roles("admin"))]
RequireEmployee = Annotated[User, Depends(require_roles("employee"))]
RequireAuth = Annotated[User, Depends(get_current_user)]
