"""Tests for Pydantic validators on request models."""

import pytest
from pydantic import ValidationError

from app.config import settings


class TestChatRequestValidators:
    """Tests for ChatRequest model validators."""

    def test_valid_message_passes(self):
        """Valid messages should pass validation."""
        from app.routes.chat import ChatRequest

        request = ChatRequest(message="Hello, how are you?")
        assert request.message == "Hello, how are you?"

    def test_message_at_max_length_passes(self):
        """Message exactly at max length should pass."""
        from app.routes.chat import ChatRequest

        message = "x" * settings.max_chat_message_length
        request = ChatRequest(message=message)
        assert len(request.message) == settings.max_chat_message_length

    def test_message_over_max_length_fails(self):
        """Message exceeding max length should fail validation."""
        from app.routes.chat import ChatRequest

        message = "x" * (settings.max_chat_message_length + 1)

        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message=message)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "maximum length" in errors[0]["msg"]

    def test_empty_message_fails(self):
        """Empty message should fail validation."""
        from app.routes.chat import ChatRequest

        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]["msg"]

    def test_whitespace_only_message_fails(self):
        """Whitespace-only message should fail validation."""
        from app.routes.chat import ChatRequest

        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="   \n\t  ")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]["msg"]

    def test_optional_fields_default_correctly(self):
        """Optional fields should have correct defaults."""
        from app.routes.chat import ChatRequest

        request = ChatRequest(message="test")

        assert request.conversation_id is None
        assert request.agent_mode is False
        assert request.max_iterations == 10


class TestConversationUpdateValidators:
    """Tests for ConversationUpdate model validators."""

    def test_valid_title_passes(self):
        """Valid title should pass validation."""
        from app.routes.chat import ConversationUpdate

        update = ConversationUpdate(title="My Conversation")
        assert update.title == "My Conversation"

    def test_title_at_max_length_passes(self):
        """Title exactly at max length should pass."""
        from app.routes.chat import ConversationUpdate

        title = "x" * settings.max_conversation_title_length
        update = ConversationUpdate(title=title)
        assert len(update.title) == settings.max_conversation_title_length

    def test_title_over_max_length_fails(self):
        """Title exceeding max length should fail validation."""
        from app.routes.chat import ConversationUpdate

        title = "x" * (settings.max_conversation_title_length + 1)

        with pytest.raises(ValidationError) as exc_info:
            ConversationUpdate(title=title)

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "maximum length" in errors[0]["msg"]

    def test_empty_title_fails(self):
        """Empty title should fail validation."""
        from app.routes.chat import ConversationUpdate

        with pytest.raises(ValidationError) as exc_info:
            ConversationUpdate(title="")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]["msg"]

    def test_whitespace_only_title_fails(self):
        """Whitespace-only title should fail validation."""
        from app.routes.chat import ConversationUpdate

        with pytest.raises(ValidationError) as exc_info:
            ConversationUpdate(title="   ")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]["msg"]

    def test_title_strips_whitespace(self):
        """Title should be stripped of leading/trailing whitespace."""
        from app.routes.chat import ConversationUpdate

        update = ConversationUpdate(title="  My Title  ")
        assert update.title == "My Title"


class TestConfigSettings:
    """Tests for config settings defaults."""

    def test_max_chat_message_length_default(self):
        """max_chat_message_length should be 32000 by default."""
        assert settings.max_chat_message_length == 32000

    def test_max_conversation_title_length_default(self):
        """max_conversation_title_length should be 255 by default."""
        assert settings.max_conversation_title_length == 255

    def test_max_request_size_bytes_default(self):
        """max_request_size_bytes should be 1MB by default."""
        assert settings.max_request_size_bytes == 1024 * 1024

    def test_rate_limit_settings_defaults(self):
        """Rate limit settings should have correct defaults."""
        assert settings.rate_limit_enabled is False  # Disabled until slowapi issue is fixed
        assert settings.rate_limit_chat_per_minute == 20
        assert settings.rate_limit_folder_create_per_hour == 10
        assert settings.rate_limit_folder_sync_per_minute == 5
        assert settings.rate_limit_general_per_minute == 100
        assert settings.rate_limit_status_per_minute == 500
