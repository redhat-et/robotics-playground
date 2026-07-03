from __future__ import annotations

import numpy as np
import rerun as rr


class RerunLogger:
    def __init__(self, port: int = 9876):
        self._port = port
        self._initialized = False

    def start(self):
        if self._initialized:
            return
        rr.init("robotics_playground")
        rr.serve_grpc(port=self._port)
        self._initialized = True

    def log_observation(self, image: np.ndarray, joint_positions: list[float], step: int):
        rr.set_time_sequence("step", step)
        rr.log("robot/camera/rgb", rr.Image(image))
        for i, pos in enumerate(joint_positions):
            rr.log(f"robot/joints/joint_{i}", rr.Scalar(pos))

    def log_action(self, action: np.ndarray, step: int):
        rr.set_time_sequence("step", step)
        for i, val in enumerate(action):
            rr.log(f"policy/action/dim_{i}", rr.Scalar(float(val)))

    def log_instruction(self, text: str, step: int):
        rr.set_time_sequence("step", step)
        rr.log("session/instruction", rr.TextLog(text))
