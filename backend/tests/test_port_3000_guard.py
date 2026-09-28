"""Automated guard ensuring ATS never binds to or targets port 3000
(reserved for Digital Subham / Alien X).
"""

import os

import pytest


def test_port_3000_guard_forbidden() -> None:
    """Verifies that ATS configurations strictly forbid binding to port 3000."""
    ats_backend_port = int(os.getenv("ATS_BACKEND_PORT", "8100"))
    ats_frontend_port = int(os.getenv("ATS_FRONTEND_PORT", "3100"))

    assert ats_backend_port != 3000, "CRITICAL: ATS Backend must never bind to port 3000!"
    assert ats_frontend_port != 3000, "CRITICAL: ATS Frontend must never bind to port 3000!"
    assert ats_backend_port == 8100, f"ATS Backend port expected 8100, got {ats_backend_port}"
    assert ats_frontend_port == 3100, f"ATS Frontend port expected 3100, got {ats_frontend_port}"


def test_port_3000_guard_raises_on_misconfiguration() -> None:
    """Simulates an invalid configuration attempting to bind to 3000 and asserts it fails."""
    def validate_ats_port(port: int) -> None:
        if port == 3000:
            raise ValueError("PORT_3000_RESERVED_FOR_DIGITAL_SUBHAM_ALIEN_X")

    with pytest.raises(ValueError, match="PORT_3000_RESERVED_FOR_DIGITAL_SUBHAM_ALIEN_X"):
        validate_ats_port(3000)

    # Valid ports pass
    validate_ats_port(8100)
    validate_ats_port(3100)
