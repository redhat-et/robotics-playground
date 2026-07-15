from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robotics_playground.policy.protocol import PolicyClient


def create_policy(policy_type: str, endpoint: str) -> PolicyClient:
    if policy_type == "openpi":
        from robotics_playground.policy.openpi_client import OpenPIClient

        return OpenPIClient(endpoint)

    from robotics_playground.policy.mock_client import MockClient

    return MockClient()
