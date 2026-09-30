"""Pure unit tests for AgentGuard Pydantic schemas (Phases 1-6).

Exercises schema validation, field constraints, normalization, and error handling
with zero database or network dependencies:
  - Auth schemas: UserRegisterRequest password rules, email normalization, RoleEnum
  - Policy schemas: CallerIdentity, DecisionInput, DecisionOutput, CheckStatus, DecisionEnum
  - Budget schemas: BudgetCreate, BudgetUpdate, BudgetResponse
"""
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.unit

from app.schemas.auth import RoleEnum, UserLoginRequest, UserRegisterRequest
from app.schemas.budget import BudgetResponse, BudgetUpdateRequest
from app.schemas.policy import (
    CallerIdentity,
    CheckResult,
    CheckStatus,
    DecisionEnum,
    DecisionInput,
    DecisionOutput,
)


class TestAuthSchemasUnit:
    def test_valid_registration_request(self):
        req = UserRegisterRequest(
            email="TEST@Example.COM",
            password="StrongPassword123!",
            organization_name="Test Org",
        )
        assert req.email == "test@example.com"  # Normalized to lowercase
        assert req.password == "StrongPassword123!"

    def test_invalid_email_format_rejected(self):
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                email="not-an-email",
                password="StrongPassword123!",
            )

    def test_weak_passwords_rejected(self):
        # Too short
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="a@b.com", password="Short1!")
        # No uppercase
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="a@b.com", password="lowercaseonly1!")
        # No lowercase
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="a@b.com", password="UPPERCASEONLY1!")
        # No digit
        with pytest.raises(ValidationError):
            UserRegisterRequest(email="a@b.com", password="NoDigitsHere!")

    def test_login_request_normalizes_email(self):
        login = UserLoginRequest(email="  USER@CORP.IO  ", password="AnyPassword")
        assert login.email == "user@corp.io"

    def test_role_enum_values(self):
        assert set(RoleEnum) == {
            RoleEnum.ADMIN,
            RoleEnum.SECURITY,
            RoleEnum.AUDITOR,
            RoleEnum.MANAGER,
            RoleEnum.DEVELOPER,
        }


class TestPolicySchemasUnit:
    def test_decision_input_defaults(self):
        agent_id = uuid.uuid4()
        inp = DecisionInput(agent_id=agent_id, tool_name="read_file", action="read")
        assert inp.agent_id == agent_id
        assert inp.tool_name == "read_file"
        assert inp.action == "read"
        assert inp.parameters == {}
        assert inp.estimated_tokens == 0
        assert inp.estimated_cost == 0.0

    def test_caller_identity_validation(self):
        caller_id = uuid.uuid4()
        org_id = uuid.uuid4()
        caller = CallerIdentity(
            caller_type="AGENT",
            caller_id=caller_id,
            organization_id=org_id,
            is_authenticated=True,
        )
        assert caller.caller_id == caller_id
        assert caller.is_authenticated is True

    def test_decision_output_structure(self):
        check = CheckResult(
            status=CheckStatus.PASSED,
            message="Caller identity verified",
        )
        output = DecisionOutput(
            decision=DecisionEnum.ALLOW,
            reason="All 11 checks passed",
            checks={"AUTH": check},
        )
        assert output.decision == DecisionEnum.ALLOW
        assert "AUTH" in output.checks
        assert output.checks["AUTH"].status == CheckStatus.PASSED


class TestBudgetSchemasUnit:
    def test_budget_update_request_validation(self):
        b = BudgetUpdateRequest(
            max_budget_per_day=Decimal("150.00"),
            max_requests_per_minute=60,
        )
        assert b.max_budget_per_day == Decimal("150.00")
        assert b.max_requests_per_minute == 60

    def test_budget_negative_value_rejected(self):
        with pytest.raises(ValidationError):
            BudgetUpdateRequest(
                max_budget_per_day=Decimal("-10.00"),
            )
