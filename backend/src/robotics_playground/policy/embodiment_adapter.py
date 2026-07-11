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
    def __init__(self, config: EmbodimentConfig):
        self._config = config
        self._image_size = tuple(config.image_size)

        # Build reorder indices: URDF order → training order
        self._obs_reorder = [config.joint_names.index(n) for n in config.training_order]
        # Inverse: training order → URDF order
        self._act_reorder = [config.training_order.index(n) for n in config.joint_names]

        # Joint limits as arrays in training order
        n_joints = len(config.training_order)
        self._joint_lower = np.zeros(n_joints, dtype=np.float64)
        self._joint_upper = np.zeros(n_joints, dtype=np.float64)
        for i, name in enumerate(config.training_order):
            limits = config.joint_limits[name]
            self._joint_lower[i] = limits[0]
            self._joint_upper[i] = limits[1]

        self._gripper_lower = config.gripper_limits[0]
        self._gripper_upper = config.gripper_limits[1]

    def _normalize(self, value: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
        return 2.0 * (value - lower) / (upper - lower) - 1.0

    def _denormalize(self, value: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
        return (value + 1.0) * (upper - lower) / 2.0 + lower

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

        # Reorder and normalize joint positions
        positions = np.array(obs["joint_positions"], dtype=np.float64)
        reordered = positions[self._obs_reorder]
        result["observation/joint_position"] = self._normalize(
            reordered, self._joint_lower, self._joint_upper
        ).astype(np.float32)

        # Gripper — use last position if available, else 0
        gripper_val = 0.0
        if len(obs["joint_positions"]) > len(self._config.joint_names):
            gripper_val = obs["joint_positions"][len(self._config.joint_names)]
        gripper_norm = self._normalize(
            np.array([gripper_val]),
            np.array([self._gripper_lower]),
            np.array([self._gripper_upper]),
        )
        result["observation/gripper_position"] = gripper_norm.astype(np.float32)

        result["prompt"] = instruction
        return result

    def action_chunk_from_openpi(self, actions_array: np.ndarray) -> list[Action]:
        n_joints = len(self._config.joint_names)
        chunk_size = actions_array.shape[0]

        result = []
        for i in range(chunk_size):
            row = actions_array[i]
            # Split: first n_joints are arm velocities, last is gripper
            vel_normalized = row[:n_joints].astype(np.float64)
            gripper_normalized = float(row[n_joints]) if row.shape[0] > n_joints else 0.0

            # Denormalize velocities
            vel_physical = self._denormalize(vel_normalized, self._joint_lower, self._joint_upper)

            # Reorder from training order to URDF order
            vel_urdf = vel_physical[self._act_reorder]

            # Denormalize gripper
            gripper_physical = self._denormalize(
                np.array([gripper_normalized]),
                np.array([self._gripper_lower]),
                np.array([self._gripper_upper]),
            )[0]

            # Build Action with NaN dispatch
            result.append(
                Action(
                    joint_positions=[math.nan] * n_joints,
                    joint_velocities=vel_urdf.tolist(),
                    gripper_position=float(gripper_physical),
                )
            )

        return result
