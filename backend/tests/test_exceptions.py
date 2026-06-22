"""Tests for custom exception classes."""

import pytest
from app.utils.exceptions import AppException, NotFoundError, ValidationError, AgentError


class TestAppException:
    def test_default_code(self):
        exc = AppException("test error")
        assert exc.message == "test error"
        assert exc.code == 400

    def test_custom_code(self):
        exc = AppException("server error", code=500)
        assert exc.code == 500

    def test_is_exception(self):
        exc = AppException("test")
        assert isinstance(exc, Exception)


class TestNotFoundError:
    def test_default_message(self):
        exc = NotFoundError()
        assert exc.message == "Resource not found"
        assert exc.code == 404

    def test_custom_message(self):
        exc = NotFoundError("School 99 not found")
        assert exc.message == "School 99 not found"
        assert exc.code == 404

    def test_inherits_app_exception(self):
        exc = NotFoundError()
        assert isinstance(exc, AppException)


class TestValidationError:
    def test_default_message(self):
        exc = ValidationError()
        assert exc.message == "Validation failed"
        assert exc.code == 422

    def test_custom_message(self):
        exc = ValidationError("Name is required")
        assert exc.message == "Name is required"


class TestAgentError:
    def test_default_message(self):
        exc = AgentError()
        assert exc.message == "Agent execution failed"
        assert exc.code == 500
