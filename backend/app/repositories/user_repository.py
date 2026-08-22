import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


def normalize_email(email: str) -> str:
    return email.strip().casefold()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == normalize_email(email))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def create(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        password_hash: str,
        role: UserRole,
    ) -> User:
        user = User(
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=normalize_email(email),
            password_hash=password_hash,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()
        return user

