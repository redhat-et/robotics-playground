from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robotics_playground.config import PlaygroundConfig
    from robotics_playground.policy.protocol import PolicyClient


def create_policy(config: PlaygroundConfig) -> PolicyClient:
    if config.policy.type == "openpi":
        from robotics_playground.policy.openpi_client import OpenPIClient

        return OpenPIClient(config.policy.endpoint)

    from robotics_playground.policy.mock_client import MockClient

    return MockClient()
