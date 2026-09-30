"""Tests for Google OAuth 2.0 and Global Email Uniqueness."""
import uuid
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import RoleEnum
from app.services.oauth import (
    generate_oauth_state,
    validate_oauth_state,
)
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Clean up any leftover test users
        db.query(User).filter(User.email.like("%@oauth-test.local")).delete()
        db.query(User).filter(User.email.like("%@unique-test.local")).delete()
        db.commit()
        yield db
    finally:
        db.query(User).filter(User.email.like("%@oauth-test.local")).delete()
        db.query(User).filter(User.email.like("%@unique-test.local")).delete()
        db.commit()
        db.close()


# ===========================================================================
# 1. Global Email Uniqueness Tests
# ===========================================================================

def test_global_email_uniqueness_enforced_across_organizations(setup_db):
    """Registering the same email in two different organizations must return 409 Conflict."""
    email = f"user_{uuid.uuid4().hex[:6]}@unique-test.local"

    # First registration in Org A -> SUCCESS
    r1 = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "First Instance",
            "organization_slug": f"org-a-{uuid.uuid4().hex[:6]}",
        },
    )
    assert r1.status_code == 201, r1.text

    # Second registration with same email in Org B -> 409 CONFLICT
    r2 = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password456!",
            "full_name": "Second Instance",
            "organization_slug": f"org-b-{uuid.uuid4().hex[:6]}",
        },
    )
    assert r2.status_code == 409, r2.text
    assert "Email already registered" in r2.json()["detail"]


def test_login_directly_resolves_user_by_unique_email(setup_db):
    """Login directly queries by email and authenticates without organization disambiguation."""
    email = f"login_test_{uuid.uuid4().hex[:6]}@unique-test.local"
    password = "SecurePassword123!"

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Direct Login User",
            "organization_slug": f"direct-org-{uuid.uuid4().hex[:6]}",
        },
    )
    assert reg.status_code == 201

    # Login without providing organization_slug
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_password_login_rejected_for_oauth_only_users(setup_db):
    """Users created via Google OAuth (without a password) cannot use password login."""
    db = setup_db
    email = f"oauth_only_{uuid.uuid4().hex[:6]}@oauth-test.local"

    org = Organization(name="OAuth Org", slug=f"oauth-org-{uuid.uuid4().hex[:6]}")
    db.add(org)
    db.flush()
    role = Role(organization_id=org.id, name=RoleEnum.ADMIN.value)
    db.add(role)
    db.flush()
    user = User(
        organization_id=org.id,
        email=email,
        full_name="OAuth User",
        role_id=role.id,
        hashed_password=None,  # No password set
        is_active=True,
    )
    db.add(user)
    db.commit()

    # Attempting password login must be rejected cleanly
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "AnyPassword123!"},
    )
    assert res.status_code == 400
    assert "Google sign-in" in res.json()["detail"]


# ===========================================================================
# 2. Google OAuth Security & State Tests
# ===========================================================================

def test_google_login_initiation_redirects_with_signed_state():
    """GET /auth/google/login must redirect to Google with valid CSRF state and client parameters."""
    res = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert res.status_code == 307
    location = res.headers["location"]

    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert f"client_id={settings.GOOGLE_CLIENT_ID}" in location
    assert "response_type=code" in location
    assert "scope=openid+email+profile" in location or "scope=openid%20email%20profile" in location
    assert "state=" in location


def test_oauth_state_generation_and_validation():
    """State generation produces a valid, tamper-evident token with redirect payload."""
    custom_target = "http://localhost:8080/dashboard?view=audit"
    state = generate_oauth_state(redirect_target=custom_target)
    assert isinstance(state, str)

    payload = validate_oauth_state(state)
    assert payload is not None
    assert payload["redirect_target"] == custom_target
    assert "nonce" in payload
    assert "exp" in payload


def test_oauth_state_tampering_rejected():
    """Tampered state tokens fail validation."""
    valid_state = generate_oauth_state()
    tampered_state = valid_state[:-4] + "abcd"

    assert validate_oauth_state(tampered_state) is None
    assert validate_oauth_state("") is None
    assert validate_oauth_state("invalid.jwt.token") is None


# ===========================================================================
# 3. Google OAuth Callback & Account Resolution Tests
# ===========================================================================

@patch("app.api.auth.verify_google_id_token")
@patch("app.api.auth.exchange_google_code")
def test_google_callback_provisions_new_user_and_organization(
    mock_exchange, mock_verify, setup_db
):
    """When a new Google user logs in, automatically provision org with ADMIN role and issue JWT."""
    new_email = f"alice_{uuid.uuid4().hex[:6]}@oauth-test.local"
    mock_exchange.return_value = {"id_token": "mock-valid-id-token", "access_token": "ya29.mock"}
    mock_verify.return_value = {
        "email": new_email,
        "email_verified": True,
        "name": "Alice Innovator",
        "sub": "google-user-id-12345",
    }

    state = generate_oauth_state(redirect_target="http://localhost:8080/login")

    res = client.get(
        f"/api/v1/auth/google/callback?code=mock-auth-code&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 307
    location = res.headers["location"]
    # Security verification: JWT must NEVER appear in URL parameters
    assert "token=" not in location
    assert "code=" in location
    assert "http://localhost:8080/login" in location

    # Extract one-time opaque exchange code from redirect query params
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    exchange_code = params["code"][0]
    assert exchange_code

    # Exchange code for JWT access token via POST body (never in URLs)
    exchange_resp = client.post(
        "/api/v1/auth/google/exchange",
        json={"code": exchange_code},
    )
    assert exchange_resp.status_code == 200
    token_payload = exchange_resp.json()
    assert "access_token" in token_payload
    assert token_payload["token_type"] == "bearer"

    # Single-use security guarantee: attempting to reuse the same code must be rejected
    reuse_resp = client.post(
        "/api/v1/auth/google/exchange",
        json={"code": exchange_code},
    )
    assert reuse_resp.status_code == 400
    assert "Invalid, expired, or already used" in reuse_resp.json()["detail"]

    # Verify user and organization were created in DB
    db = setup_db
    created_user = db.query(User).filter(User.email == new_email).first()
    assert created_user is not None
    assert created_user.full_name == "Alice Innovator"
    assert created_user.hashed_password is None
    assert created_user.organization is not None
    assert "Alice Innovator's Organization" in created_user.organization.name
    assert created_user.role.name == RoleEnum.ADMIN.value


@patch("app.api.auth.verify_google_id_token")
@patch("app.api.auth.exchange_google_code")
def test_google_callback_existing_user_login(
    mock_exchange, mock_verify, setup_db
):
    """When an existing user logs in with Google, issue token matching their existing account."""
    db = setup_db
    existing_email = f"bob_{uuid.uuid4().hex[:6]}@oauth-test.local"

    org = Organization(name="Bob Enterprise", slug=f"bob-org-{uuid.uuid4().hex[:6]}")
    db.add(org)
    db.flush()
    role = Role(organization_id=org.id, name=RoleEnum.DEVELOPER.value)
    db.add(role)
    db.flush()
    existing_user = User(
        organization_id=org.id,
        email=existing_email,
        full_name="Bob Existing",
        role_id=role.id,
        hashed_password=None,
        is_active=True,
    )
    db.add(existing_user)
    db.commit()

    mock_exchange.return_value = {"id_token": "mock-valid-id-token"}
    mock_verify.return_value = {
        "email": existing_email,
        "email_verified": True,
        "name": "Bob Existing",
    }

    state = generate_oauth_state()

    res = client.get(
        f"/api/v1/auth/google/callback?code=mock-auth-code&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 307
    location = res.headers["location"]
    # Security verification: JWT must NEVER appear in URL parameters
    assert "token=" not in location
    assert "code=" in location

    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    exchange_code = params["code"][0]

    # Exchange one-time code for token
    exchange_resp = client.post(
        "/api/v1/auth/google/exchange",
        json={"code": exchange_code},
    )
    assert exchange_resp.status_code == 200
    assert "access_token" in exchange_resp.json()

    # Ensure no duplicate user was created
    users = db.query(User).filter(User.email == existing_email).all()
    assert len(users) == 1
    assert users[0].id == existing_user.id


def test_google_exchange_rejects_invalid_or_expired_code():
    """POST /auth/google/exchange rejects invalid or non-existent code with 400 Bad Request."""
    res = client.post(
        "/api/v1/auth/google/exchange",
        json={"code": "completely-invalid-opaque-code"},
    )
    assert res.status_code == 400
    assert "Invalid, expired, or already used" in res.json()["detail"]


def test_google_callback_rejects_invalid_state():
    """Callback with invalid/tampered state redirects to login with error parameter."""
    res = client.get(
        "/api/v1/auth/google/callback?code=some-code&state=tampered-state-token",
        follow_redirects=False,
    )
    assert res.status_code == 307
    location = res.headers["location"]
    assert "error=invalid_or_expired_state" in location


@patch("app.api.auth.exchange_google_code")
def test_google_callback_handles_exchange_failure(mock_exchange):
    """Callback handles token exchange failure gracefully."""
    mock_exchange.side_effect = ValueError("Google token exchange error")
    state = generate_oauth_state()

    res = client.get(
        f"/api/v1/auth/google/callback?code=bad-code&state={state}",
        follow_redirects=False,
    )
    assert res.status_code == 307
    location = res.headers["location"]
    assert "error=token_verification_failed" in location
