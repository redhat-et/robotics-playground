from __future__ import annotations

import numpy as np
import pytest

from robotics_playground.bridges.protocol import Action, Observation


def test_observation_type_shape():
    obs: Observation = {
        "step": 0,
        "cameras": {"wrist": np.zeros((240, 320, 3), dtype=np.uint8)},
        "joint_positions": [0.0] * 6,
        "joint_velocities": [0.0] * 6,
    }
    assert obs["step"] == 0
    assert "wrist" in obs["cameras"]
    assert obs["cameras"]["wrist"].shape == (240, 320, 3)


def test_action_type_shape():
    act: Action = {"joint_positions": [0.0] * 7}
    assert len(act["joint_positions"]) == 7


@pytest.mark.anyio
async def test_mock_bridge_produces_observations():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()

    count = 0
    async for obs in bridge.observation_stream():
        assert "cameras" in obs
        assert "wrist" in obs["cameras"]
        assert obs["cameras"]["wrist"].shape == (240, 320, 3)
        assert isinstance(obs["joint_positions"], list)
        assert isinstance(obs["joint_velocities"], list)
        assert obs["step"] == count
        count += 1
        if count >= 3:
            break

    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_send_action_is_noop():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    await bridge.send_action({"joint_positions": [0.0] * 7})
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_sim_control_is_noop():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    await bridge.sim_control("play")
    await bridge.sim_control("pause")
    await bridge.sim_control("step")
    await bridge.sim_control("play", speed=2.0)
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_status_is_mock():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    assert bridge.bridge_status == "mock"
    await bridge.start()
    assert bridge.bridge_status == "mock"
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_output_is_deterministic():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()

    observations = []
    async for obs in bridge.observation_stream():
        observations.append(obs["joint_positions"][:])
        if len(observations) >= 3:
            break
    await bridge.close()

    bridge2 = MockBridge()
    await bridge2.start()
    idx = 0
    async for obs in bridge2.observation_stream():
        assert obs["joint_positions"] == observations[idx]
        idx += 1
        if idx >= 3:
            break
    await bridge2.close()


@pytest.mark.anyio
async def test_create_bridge_returns_mock_by_default():
    from robotics_playground.bridges import create_bridge
    from robotics_playground.bridges.mock_bridge import MockBridge
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    bridge = create_bridge(config)
    assert isinstance(bridge, MockBridge)
