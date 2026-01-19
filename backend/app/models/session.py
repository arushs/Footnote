"""Session model with encrypted token storage."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.utils import decrypt_token, encrypt_token, is_encrypted

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
