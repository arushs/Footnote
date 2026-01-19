"""Session model with encrypted token storage."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto import decrypt_token, encrypt_token, is_encrypted
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Session(Base):
    """User session with encrypted OAuth tokens.

    Tokens are encrypted at rest using Fernet symmetric encryption.
    The encryption is transparent - use the access_token and refresh_token
    properties which handle encryption/decryption automatically.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    _access_token: Mapped[str] = mapped_column("access_token", Text, nullable=False)
    _refresh_token: Mapped[str] = mapped_column("refresh_token", Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="sessions")

    @property
    def access_token(self) -> str:
        """Get decrypted access token."""
        if is_encrypted(self._access_token):
            return decrypt_token(self._access_token)
        # Handle legacy unencrypted tokens
        return self._access_token

    @access_token.setter
    def access_token(self, value: str) -> None:
        """Set and encrypt access token."""
        self._access_token = encrypt_token(value) if value else ""

    @property
    def refresh_token(self) -> str:
        """Get decrypted refresh token."""
        if is_encrypted(self._refresh_token):
            return decrypt_token(self._refresh_token)
        # Handle legacy unencrypted tokens
        return self._refresh_token

    @refresh_token.setter
    def refresh_token(self, value: str) -> None:
        """Set and encrypt refresh token."""
        self._refresh_token = encrypt_token(value) if value else ""

    @classmethod
    def from_db_row(
        cls,
        id: uuid.UUID,
        user_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> "Session":
        """Create a Session from raw database values (already encrypted).

        Use this when constructing a Session from raw SQL results where
        tokens are already encrypted in the database.
        """
        session = cls.__new__(cls)
        session.id = id
        session.user_id = user_id
        session._access_token = access_token  # Already encrypted, don't re-encrypt
        session._refresh_token = refresh_token  # Already encrypted, don't re-encrypt
        session.expires_at = expires_at
        return session
