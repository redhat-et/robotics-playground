from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from robotics_playground.bridges.protocol import Action

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Observation
    from robotics_playground.config import EmbodimentConfig


class EmbodimentAdapter:
    def __init__(self, config: EmbodimentConfig, session_id: str = "default"):
        self._config = config
        self._image_size = tuple(config.image_size)
        self._session_id = session_id

        # Build reorder indices: URDF order → training order
        self._obs_reorder = [config.joint_names.index(n) for n in config.training_order]
        # Inverse: training order → URDF order
        self._act_reorder = [config.training_order.index(n) for n in config.joint_names]

    def _resize_image(self, image: np.ndarray) -> np.ndarray:
        h, w = self._image_size
        pil_img = Image.fromarray(image)
        # Resize maintaining aspect ratio with padding
        pil_img.thumbnail((w, h), Image.LANCZOS)
        padded = Image.new("RGB", (w, h), (0, 0, 0))
        offset = ((w - pil_img.width) // 2, (h - pil_img.height) // 2)
        padded.paste(pil_img, offset)
        return np.array(padded)

    def observation_to_openpi(self, obs: Observation, instruction: str) -> dict:
        result: dict = {}

        # Remap and resize camera images
        for ros_name, openpi_key in self._config.camera_mapping.items():
            if ros_name in obs["cameras"]:
                result[openpi_key] = self._resize_image(obs["cameras"][ros_name])

        # Reorder joint positions (raw radians — server normalizes internally)
        positions = np.array(obs["joint_positions"], dtype=np.float64)
        reordered = positions[self._obs_reorder]
        result["observation/joint_position"] = reordered.astype(np.float32)

        # Gripper — raw value, server normalizes internally
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
            # Server returns absolute joint positions in radians (already
            # denormalized and delta→absolute converted internally)
            pos_physical = row[:n_joints].astype(np.float64)

            # Reorder from training order to URDF order
            pos_urdf = pos_physical[self._act_reorder]

            gripper_physical = float(row[n_joints]) if row.shape[0] > n_joints else 0.0

            result.append(
                Action(
                    joint_positions=pos_urdf.tolist(),
                    joint_velocities=[math.nan] * n_joints,
                    gripper_position=gripper_physical,
                )
            )

        return result
