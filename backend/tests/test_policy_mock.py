from __future__ import annotations

import numpy as np
import pytest

from robotics_playground.policy.mock_client import MockClient


@pytest.mark.anyio
async def test_mock_client_connect_is_noop():
    client = MockClient()
    await client.connect()
    await client.close()


@pytest.mark.anyio
async def test_mock_client_infer_returns_action_chunk():
    client = MockClient()
    await client.connect()
    obs = {
        "observation/wrist_image_left": np.zeros((224, 224, 3), dtype=np.uint8),
        "observation/joint_position": np.zeros(7),
        "observation/gripper_position": np.zeros(1),
        "prompt": "pick up the block",
    }
    result = await client.infer(obs)
    assert "actions" in result
    assert isinstance(result["actions"], np.ndarray)
    assert result["actions"].shape == (10, 8)
    assert result["actions"].min() >= -1.0
    assert result["actions"].max() <= 1.0
    await client.close()


@pytest.mark.anyio
async def test_mock_client_reset_is_noop():
    client = MockClient()
    await client.connect()
    await client.reset()
    await client.close()
