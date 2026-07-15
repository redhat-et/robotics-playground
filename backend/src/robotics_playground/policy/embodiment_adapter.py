from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from robotics_playground.bridges.protocol import Action

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Observation
    from robotics_playground.config import EmbodimentConfig


_JOINT_LIMIT_MARGIN = 0.05


class EmbodimentAdapter:
    def __init__(
        self,
        config: EmbodimentConfig,
        camera_mapping_override: dict[str, str] | None = None,
        session_id: str = "default",
    ):
        self._config = config
        if camera_mapping_override is not None:
            self._camera_mapping = camera_mapping_override
        else:
            self._camera_mapping = config.camera_mapping
        self._session_id = session_id

        # Build reorder indices: URDF order → training order
        self._obs_reorder = [config.joint_names.index(n) for n in config.training_order]
        # Inverse: training order → URDF order
        self._act_reorder = [config.training_order.index(n) for n in config.joint_names]

        # Pre-compute clamping arrays in URDF order
        if config.joint_limits:
            self._lower = np.array(
                [config.joint_limits[n][0] + _JOINT_LIMIT_MARGIN for n in config.joint_names]
            )
            self._upper = np.array(
                [config.joint_limits[n][1] - _JOINT_LIMIT_MARGIN for n in config.joint_names]
            )
        else:
            self._lower = None
            self._upper = None

    @property
    def camera_names(self) -> list[str]:
        return list(self._camera_mapping.keys())

    def observation_to_openpi(self, obs: Observation, instruction: str) -> dict:
        result: dict = {}

        for ros_name, openpi_key in self._camera_mapping.items():
            if ros_name in obs["cameras"]:
                result[openpi_key] = obs["cameras"][ros_name]

        positions = np.array(obs["joint_positions"], dtype=np.float64)
        reordered = positions[self._obs_reorder]
        result["observation/joint_position"] = reordered.astype(np.float32)

        gripper_val = 0.0
        if len(obs["joint_positions"]) > len(self._config.joint_names):
            gripper_val = obs["joint_positions"][len(self._config.joint_names)]
        result["observation/gripper_position"] = np.array([gripper_val], dtype=np.float32)

        result["prompt"] = instruction
        result["session_id"] = self._session_id
        return result

    def action_chunk_from_openpi(self, actions_array: np.ndarray) -> list[Action]:
        n_joints = len(self._config.joint_names)
        chunk_size = actions_array.shape[0]

        result = []
        for i in range(chunk_size):
            row = actions_array[i]
            pos_physical = row[:n_joints].astype(np.float64)
            pos_urdf = pos_physical[self._act_reorder]

            if self._lower is not None:
                pos_urdf = np.clip(pos_urdf, self._lower, self._upper)

            gripper_physical = float(row[n_joints]) if row.shape[0] > n_joints else 0.0
            g_lo, g_hi = self._config.gripper_limits
            gripper_physical = max(g_lo, min(g_hi, gripper_physical))

            result.append(
                Action(
                    joint_positions=pos_urdf.tolist(),
                    joint_velocities=[math.nan] * n_joints,
                    gripper_position=gripper_physical,
                )
            )

        return result
