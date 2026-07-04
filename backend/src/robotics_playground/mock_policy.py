from __future__ import annotations

import asyncio

import numpy as np

from robotics_playground.bridges.protocol import Action


async def predict_action(observation: dict) -> Action:
    """Mock policy: random actions with simulated inference latency."""
    await asyncio.sleep(0.05)
    positions = np.random.uniform(-1.0, 1.0, size=(6,)).tolist()
    return Action(joint_positions=positions)
