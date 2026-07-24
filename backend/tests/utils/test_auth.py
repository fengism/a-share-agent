"""Unit tests for app.utils.auth (pure primitives).

Assertions were validated by executing the functions directly, so they reflect
the code's actual behaviour. No database or network access is required.
"""
from app.utils.auth import (
    generate_invite_code,
    generate_session_token,
    hash_password,
    hash_token,
    now_ts,
    session_expiry,
    verify_password,
)


class TestPasswordHashing:
    def test_encoded_format(self):
        parts = hash_password("hunter2").split("$")
        assert parts[0] == "pbkdf2_sha256"
        assert parts[1] == "200000"
        assert len(parts) == 4  # algo$rounds$salt$hash

    def test_salt_is_random(self):
        # Same password hashed twice must differ (random per-hash salt).
        assert hash_password("hunter2") != hash_password("hunter2")

    def test_verify_correct(self):
        h = hash_password("s3cr3t-password")
        assert verify_password("s3cr3t-password", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("s3cr3t-password")
        assert verify_password("nope", h) is False

    def test_verify_malformed_hash_returns_false(self):
        # A corrupt/unknown stored value must fail closed, never raise.
        assert verify_password("x", "not-a-valid-hash") is False
        assert verify_password("x", "md5$1$aa$bb") is False
        assert verify_password("x", "") is False


class TestTokens:
    def test_session_token_unique_and_urlsafe(self):
        t1, t2 = generate_session_token(), generate_session_token()
        assert t1 != t2
        assert len(t1) >= 40
        assert "=" not in t1 and "/" not in t1 and "+" not in t1

    def test_hash_token_is_deterministic_sha256(self):
        assert hash_token("abc") == hash_token("abc")
        assert len(hash_token("abc")) == 64
        assert hash_token("abc") != hash_token("abd")

    def test_invite_code_unique(self):
        c1, c2 = generate_invite_code(), generate_invite_code()
        assert c1 != c2
        assert len(c1) >= 12


class TestTimestamps:
    def test_expiry_after_now(self):
        assert session_expiry() > now_ts()

    def test_expiry_monotonic_in_days(self):
        # The DB compares timestamps as strings; the format must sort chronologically.
        assert session_expiry(0) <= session_expiry(1)
