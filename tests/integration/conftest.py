"""Fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a sample project directory with Python and TypeScript files."""
    # Python files
    src = tmp_path / "src"
    src.mkdir()
    (src / "models.py").write_text(
        '''
class User:
    """User model for authentication."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def validate_email(self) -> bool:
        """Validate email format."""
        return "@" in self.email
'''
    )

    (src / "auth.py").write_text(
        '''
from typing import Optional

def authenticate(username: str, password: str) -> Optional[dict]:
    """Authenticate user with credentials."""
    if not username or not password:
        return None
    return {"token": "abc123", "user": username}

def logout(token: str) -> bool:
    """Invalidate a session token."""
    return True
'''
    )

    (src / "utils.py").write_text(
        '''
import hashlib

def hash_password(password: str) -> str:
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def format_name(first: str, last: str) -> str:
    """Format a full name."""
    return f"{first} {last}".strip()
'''
    )

    # TypeScript file
    (src / "api.ts").write_text(
        """
interface ApiResponse {
    data: any;
    status: number;
}

export async function fetchUser(id: string): Promise<ApiResponse> {
    const response = await fetch(`/api/users/${id}`);
    return { data: await response.json(), status: response.status };
}
"""
    )

    # Markdown docs
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text(
        """
# Sample Project

This is a sample project for testing code search.

## Authentication

The auth module handles user authentication and session management.
"""
    )

    return tmp_path
