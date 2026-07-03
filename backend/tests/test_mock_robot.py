from __future__ import annotations

import numpy as np
import pytest

from robotics_playground.mock_robot import observation_stream


@pytest.mark.anyio
async def test_observation_has_expected_keys_and_types():
    async for obs in observation_stream():
        assert isinstance(obs["image"], np.ndarray)
        assert obs["image"].shape == (240, 320, 3)
        assert obs["image"].dtype == np.uint8
        assert isinstance(obs["joint_positions"], list)
        assert len(obs["joint_positions"]) == 6
        assert all(isinstance(v, float) for v in obs["joint_positions"])
        break  # one iteration is enough


@pytest.mark.anyio
async def test_observation_stream_yields_multiple():
    count = 0
    async for _obs in observation_stream():
        count += 1
        if count >= 3:
            break
    assert count == 3
