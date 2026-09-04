"""Phase 3 authentication API tests.

Tests are organised by feature:
  - Password policy enforcement (unit)
  - JWT issuance and validation (unit)
  - API key generation/hashing (unit)
  - POST /auth/register
  - POST /auth/login
  - GET /auth/me
  - POST /auth/api-keys
  - GET /auth/api-keys
  - DELETE /auth/api-keys/{key_id}
  - Role enforcement (require_role dependency)
  - Organization isolation (cross-org access denied)
"""
import uuid
import pytest

from app.security.password import hash_password, verify_password, validate_password_strength
from app.security.jwt import create_access_token, decode_access_token
from app.security.api_key import generate_api_key, hash_api_key

from tests.conftest import register_user, login_user, auth_headers, make_unique_slug


# ===========================================================================
# Unit: password
# ===========================================================================

class TestPasswordSecurity:
    def test_hash_differs_from_plaintext(self):
        h = hash_password("MySecret1!")
        assert h != "MySecret1!"

    def test_verify_correct_password(self):
        h = hash_password("ValidPass9")
        assert verify_password("ValidPass9", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("ValidPass9")
        assert verify_password("BadPass99", h) is False

    def test_same_password_produces_different_hash(self):
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2  # bcrypt salts each hash

    def test_validate_too_short(self):
        with pytest.raises(ValueError, match="8 characters"):
            validate_password_strength("Ab1")

    def test_validate_no_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password_strength("password1")

    def test_validate_no_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_password_strength("PASSWORD1")

    def test_validate_no_digit(self):
        with pytest.raises(ValueError, match="digit"):
            validate_password_strength("NoDigitsHere!")

    def test_validate_valid_password(self):
        validate_password_strength("ValidPass9!")  # should not raise


# ===========================================================================
# Unit: JWT
# ===========================================================================

class TestJWT:
    def test_encode_decode_roundtrip(self):
        data = {"sub": str(uuid.uuid4()), "organization_id": str(uuid.uuid4()), "role": "admin"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded["sub"] == data["sub"]
        assert decoded["organization_id"] == data["organization_id"]
        assert decoded["role"] == data["role"]

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_access_token("this.is.not.a.jwt")

    def test_tampered_token_raises(self):
        token = create_access_token({"sub": "x"})
        bad = token[:-5] + "XXXXX"
        with pytest.raises(Exception):
            decode_access_token(bad)

    def test_token_contains_exp(self):
        token = create_access_token({"sub": "x"})
        decoded = decode_access_token(token)
        assert "exp" in decoded


# ===========================================================================
# Unit: API Key
# ===========================================================================

class TestAPIKey:
    def test_generate_returns_triple(self):
        raw, prefix, key_id = generate_api_key()
        assert raw.startswith(prefix)
        assert len(prefix) > 4

    def test_hash_is_not_raw(self):
        raw, prefix, _ = generate_api_key()
        h = hash_api_key(raw)
        assert h != raw

    def test_same_key_same_hash(self):
        raw, _, _ = generate_api_key()
        assert hash_api_key(raw) == hash_api_key(raw)

    def test_different_keys_different_hashes(self):
        raw1, _, _ = generate_api_key()
        raw2, _, _ = generate_api_key()
        assert hash_api_key(raw1) != hash_api_key(raw2)

    def test_prefix_format(self):
        raw, prefix, _ = generate_api_key(prefix="ag_live")
        assert prefix.startswith("ag_live_")


# ===========================================================================
# Integration: POST /auth/register
# ===========================================================================

class TestRegister:
    def test_successful_registration(self, client):
        slug = make_unique_slug()
        resp = client.post("/api/v1/auth/register", json={
            "email": f"user@{slug}.com",
            "password": "Password1!",
            "organization_slug": slug,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == f"user@{slug}.com"
        assert "id" in data
        assert "hashed_password" not in data  # never expose hashes

    def test_registration_creates_org_when_slug_not_exists(self, client):
        slug = f"brand-new-{uuid.uuid4().hex[:6]}"
        resp, _ = register_user(client, f"admin@{slug}.io", slug=slug)
        assert resp.status_code == 201
        assert resp.json()["organization_id"] is not None

    def test_duplicate_email_in_same_org_rejected(self, client):
        slug = make_unique_slug()
        register_user(client, f"dup@{slug}.io", slug=slug)
        resp, _ = register_user(client, f"dup@{slug}.io", slug=slug)
        assert resp.status_code == 409

    def test_same_email_different_org_allowed(self, client):
        slug1 = make_unique_slug()
        slug2 = make_unique_slug()
        r1, _ = register_user(client, "shared@email.com", slug=slug1)
        r2, _ = register_user(client, "shared@email.com", slug=slug2)
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["organization_id"] != r2.json()["organization_id"]

    def test_weak_password_rejected(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "user@test.com",
            "password": "short",
            "organization_slug": make_unique_slug(),
        })
        assert resp.status_code == 422  # Pydantic validation error

    def test_no_organization_slug_auto_creates_org(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "solo@nobody.io",
            "password": "Password1!",
        })
        assert resp.status_code == 201
        assert resp.json()["organization_id"] is not None


# ===========================================================================
# Integration: POST /auth/login
# ===========================================================================

class TestLogin:
    def test_successful_login_returns_token(self, client):
        slug = make_unique_slug()
        register_user(client, f"login@{slug}.io", slug=slug)
        resp = login_user(client, f"login@{slug}.io", slug=slug)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_wrong_password_returns_401(self, client):
        slug = make_unique_slug()
        register_user(client, f"pw@{slug}.io", slug=slug)
        resp = login_user(client, f"pw@{slug}.io", password="WrongPass1!", slug=slug)
        assert resp.status_code == 401

    def test_nonexistent_user_returns_401(self, client):
        resp = login_user(client, "ghost@nowhere.com", slug="nonexistent-org-xyz")
        assert resp.status_code == 401

    def test_login_with_wrong_org_slug_returns_401(self, client):
        slug = make_unique_slug()
        register_user(client, f"org@{slug}.io", slug=slug)
        resp = login_user(client, f"org@{slug}.io", slug="wrong-slug-yyy")
        assert resp.status_code == 401


# ===========================================================================
# Integration: GET /auth/me
# ===========================================================================

class TestGetMe:
    def test_authenticated_user_sees_own_profile(self, client):
        slug = make_unique_slug()
        register_user(client, f"me@{slug}.io", slug=slug)
        token = login_user(client, f"me@{slug}.io", slug=slug).json()["access_token"]

        resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == f"me@{slug}.io"

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401


# ===========================================================================
# Integration: API key management
# ===========================================================================

class TestAPIKeyManagement:
    def _login_token(self, client, email, slug):
        register_user(client, email, slug=slug)
        return login_user(client, email, slug=slug).json()["access_token"]

    def test_create_api_key_returns_raw_key(self, client):
        slug = make_unique_slug()
        token = self._login_token(client, f"ak@{slug}.io", slug)
        resp = client.post(
            "/api/v1/auth/api-keys",
            json={"name": "my-key"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "api_key" in data
        assert data["api_key"].startswith("ag_live_")

    def test_raw_key_not_returned_on_list(self, client):
        slug = make_unique_slug()
        token = self._login_token(client, f"akl@{slug}.io", slug)
        client.post("/api/v1/auth/api-keys", json={"name": "listed"}, headers=auth_headers(token))
        resp = client.get("/api/v1/auth/api-keys", headers=auth_headers(token))
        assert resp.status_code == 200
        for key in resp.json():
            assert "api_key" not in key  # raw secret never exposed on list

    def test_revoke_api_key(self, client):
        slug = make_unique_slug()
        token = self._login_token(client, f"akr@{slug}.io", slug)
        create_resp = client.post(
            "/api/v1/auth/api-keys",
            json={"name": "to-revoke"},
            headers=auth_headers(token),
        )
        key_id = create_resp.json()["id"]
        revoke_resp = client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=auth_headers(token))
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["is_active"] is False

    def test_cannot_revoke_another_orgs_key(self, client):
        slug1, slug2 = make_unique_slug(), make_unique_slug()
        token1 = self._login_token(client, f"a@{slug1}.io", slug1)
        token2 = self._login_token(client, f"b@{slug2}.io", slug2)

        key_id = client.post(
            "/api/v1/auth/api-keys",
            json={"name": "org1-key"},
            headers=auth_headers(token1),
        ).json()["id"]

        resp = client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=auth_headers(token2))
        assert resp.status_code == 404  # org2 can't see org1's key


# ===========================================================================
# Integration: Role enforcement
# ===========================================================================

class TestRoleEnforcement:
    def test_admin_can_access_admin_only_route(self, client):
        slug = make_unique_slug()
        # First user in a new org becomes ADMIN
        register_user(client, f"adm@{slug}.io", slug=slug)
        token = login_user(client, f"adm@{slug}.io", slug=slug).json()["access_token"]
        resp = client.get("/api/v1/auth/admin-only", headers=auth_headers(token))
        assert resp.status_code == 200

    def test_developer_cannot_access_admin_only_route(self, client):
        slug = make_unique_slug()
        # Admin registers first (creates org)
        register_user(client, f"adm2@{slug}.io", slug=slug)
        # Developer joins existing org with explicit DEVELOPER role
        resp, _ = register_user(client, f"dev@{slug}.io", slug=slug, role="DEVELOPER")
        assert resp.status_code == 201, f"Dev registration failed: {resp.json()}"
        login_resp = login_user(client, f"dev@{slug}.io", slug=slug)
        assert login_resp.status_code == 200, f"Dev login failed: {login_resp.json()}"
        token = login_resp.json()["access_token"]
        resp = client.get("/api/v1/auth/admin-only", headers=auth_headers(token))
        assert resp.status_code == 403


# ===========================================================================
# Integration: Organization isolation
# ===========================================================================

class TestOrgIsolation:
    def test_user_in_org1_cannot_see_org2_profile(self, client):
        slug1, slug2 = make_unique_slug(), make_unique_slug()
        register_user(client, f"a@{slug1}.io", slug=slug1)
        register_user(client, f"b@{slug2}.io", slug=slug2)

        token1 = login_user(client, f"a@{slug1}.io", slug=slug1).json()["access_token"]
        me1 = client.get("/api/v1/auth/me", headers=auth_headers(token1)).json()
        assert me1["email"] == f"a@{slug1}.io"

        token2 = login_user(client, f"b@{slug2}.io", slug=slug2).json()["access_token"]
        me2 = client.get("/api/v1/auth/me", headers=auth_headers(token2)).json()
        assert me2["email"] == f"b@{slug2}.io"

        # org_ids must differ
        assert me1["organization_id"] != me2["organization_id"]
