from __future__ import annotations

import asyncio

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
    act: Action = {
        "joint_positions": [float("nan")] * 7,
        "joint_velocities": [0.0] * 7,
        "gripper_position": 0.5,
    }
    assert len(act["joint_positions"]) == 7
    assert len(act["joint_velocities"]) == 7
    assert isinstance(act["gripper_position"], float)


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
async def test_mock_bridge_get_observation():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    obs = await bridge.get_observation()
    assert "cameras" in obs
    assert "wrist" in obs["cameras"]
    assert isinstance(obs["joint_positions"], list)
    assert obs["step"] == 0
    obs2 = await bridge.get_observation()
    assert obs2["step"] == 1
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_send_action_is_noop():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    await bridge.send_action(
        {
            "joint_positions": [float("nan")] * 7,
            "joint_velocities": [0.0] * 7,
            "gripper_position": 0.5,
        }
    )
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
async def test_mock_bridge_status_lifecycle():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    assert bridge.bridge_status == "mock"
    await bridge.start()
    assert bridge.bridge_status == "connected"
    await bridge.close()
    assert bridge.bridge_status == "disconnected"


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
async def test_mock_bridge_disconnect_blocks_observations():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    assert bridge.bridge_status == "connected"

    obs = await bridge.get_observation()
    assert obs["step"] == 0

    bridge.simulate_disconnect()
    assert bridge.bridge_status == "disconnected"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bridge.get_observation(), timeout=0.1)

    bridge.simulate_reconnect()
    assert bridge.bridge_status == "connected"

    obs = await bridge.get_observation()
    assert obs["step"] == 1
    await bridge.close()


@pytest.mark.anyio
async def test_mock_bridge_tracks_sim_control_calls():
    from robotics_playground.bridges.mock_bridge import MockBridge

    bridge = MockBridge()
    await bridge.start()
    await bridge.sim_control("play")
    await bridge.sim_control("reset")
    await bridge.sim_control("step", speed=2.0)
    assert bridge.sim_control_calls == [("play", None), ("reset", None), ("step", 2.0)]
    await bridge.close()


@pytest.mark.anyio
async def test_create_bridge_returns_mock_by_default():
    from robotics_playground.bridges import create_bridge
    from robotics_playground.bridges.mock_bridge import MockBridge
    from robotics_playground.config import PlaygroundConfig

    config = PlaygroundConfig()
    bridge = create_bridge(config)
    assert isinstance(bridge, MockBridge)
