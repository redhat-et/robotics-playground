from __future__ import annotations

import numpy as np
import rerun as rr


class RerunLogger:
    def __init__(self, port: int = 9876, policy_index: int = 0):
        self._port = port
        self._prefix = f"session/policy_{policy_index}"
        self._initialized = False

    def start(self):
        if self._initialized:
            return
        rr.init("robotics_playground")
        rr.serve_grpc(port=self._port)
        self._initialized = True

    def log_observation(self, image: np.ndarray, joint_positions: list[float], step: int):
        rr.set_time_sequence("step", step)
        rr.log(f"{self._prefix}/camera/wrist", rr.Image(image))
        for i, pos in enumerate(joint_positions):
            rr.log(f"{self._prefix}/joints/joint_{i}", rr.Scalar(pos))

    def log_action(self, action: np.ndarray, step: int):
        rr.set_time_sequence("step", step)
        for i, val in enumerate(action):
            rr.log(f"{self._prefix}/actions/dim_{i}", rr.Scalar(float(val)))

    def log_instruction(self, text: str, step: int):
        rr.set_time_sequence("step", step)
        rr.log("session/instructions", rr.TextLog(text))
