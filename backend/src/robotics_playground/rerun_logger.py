from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Action, Observation


PANDA_JOINT_LABELS = [
    "shoulder_rot",
    "shoulder_lift",
    "elbow_rot",
    "elbow_flex",
    "wrist_rot",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]


class RerunLogger:
    def __init__(
        self,
        port: int = 9876,
        web_port: int = 9090,
        policy_index: int = 0,
        camera_names: list[str] | None = None,
        cors_allow_origin: list[str] | None = None,
    ):
        self._port = port
        self._web_port = web_port
        self._cors_allow_origin = cors_allow_origin
        self._prefix = f"session/policy_{policy_index}"
        names = camera_names or ["exterior_1", "exterior_2", "wrist"]
        self._camera_names = sorted(names, key=lambda n: (n == "wrist", n))
        self._initialized = False
        self._step_offset = 0
        self._last_step = 0

    def _build_blueprint(self) -> rrb.Blueprint:
        camera_views = [
            rrb.Spatial2DView(
                origin=f"{self._prefix}/camera/{name}",
                name=name,
            )
            for name in self._camera_names
        ]
        step_range = rrb.VisibleTimeRanges(
            timeline="step",
            start=rrb.TimeRangeBoundary.absolute(seq=0),
            end=rrb.TimeRangeBoundary.infinite(),
        )
        return rrb.Blueprint(
            rrb.Vertical(
                rrb.Horizontal(*camera_views),
                rrb.Horizontal(
                    rrb.TimeSeriesView(
                        origin=f"{self._prefix}/joints",
                        name="Joint States",
                        plot_legend=rrb.PlotLegend(visible=False),
                        time_ranges=step_range,
                    ),
                    rrb.TimeSeriesView(
                        origin=f"{self._prefix}/policy",
                        name="Policy Output",
                        plot_legend=rrb.PlotLegend(visible=False),
                        axis_y=rrb.ScalarAxis(range=(-3.2, 3.8), zoom_lock=True),
                        time_ranges=step_range,
                    ),
                ),
                row_shares=[7, 2],
            ),
            auto_layout=False,
            auto_views=False,
            collapse_panels=True,
        )

    def start(self):
        if self._initialized:
            return
        rr.init("robotics_playground")
        blueprint = self._build_blueprint()
        rr.serve_grpc(
            grpc_port=self._port,
            default_blueprint=blueprint,
            server_memory_limit="512MiB",
            cors_allow_origin=self._cors_allow_origin,
        )
        rr.serve_web_viewer(
            web_port=self._web_port,
            open_browser=False,
        )
        rr.send_blueprint(blueprint)
        rr.set_time("step", sequence=0)
        rr.log(self._prefix, rr.Clear(recursive=True))
        self._initialized = True

    def clear(self):
        if self._initialized:
            clear_step = self._step_offset + self._last_step + 1
            rr.set_time("step", sequence=clear_step)
            rr.log(self._prefix, rr.Clear(recursive=True))
            rr.log("session/instructions", rr.Clear(recursive=True))
            self._step_offset = clear_step + 1
            self._last_step = 0

    def log_observation(self, obs: Observation, step: int):
        effective_step = self._step_offset + step
        self._last_step = step
        rr.set_time("step", sequence=effective_step)
        for name, image in obs["cameras"].items():
            rr.log(f"{self._prefix}/camera/{name}", rr.Image(image))
        for i, pos in enumerate(obs["joint_positions"]):
            label = PANDA_JOINT_LABELS[i] if i < len(PANDA_JOINT_LABELS) else f"joint_{i}"
            rr.log(
                f"{self._prefix}/joints/{label}",
                rr.Scalars(pos),
                rr.SeriesLines(names=[label]),
            )

    def log_action(self, action: Action, step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        for i, val in enumerate(action["joint_positions"]):
            rr.log(f"{self._prefix}/actions/dim_{i}", rr.Scalars(float(val)))

    def log_instruction(self, text: str, step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        rr.log("session/instructions", rr.TextLog(text))

    def log_raw_action_tensor(self, actions: np.ndarray, step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        rr.log(f"{self._prefix}/policy/raw_output", rr.Tensor(actions))
        for dim in range(actions.shape[1]):
            label = PANDA_JOINT_LABELS[dim] if dim < len(PANDA_JOINT_LABELS) else f"dim_{dim}"
            rr.log(
                f"{self._prefix}/policy/raw_output/{label}",
                rr.Scalars(float(actions[0, dim])),
                rr.SeriesLines(names=[label]),
            )

    def log_inference_latency(self, latency_ms: float, step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        rr.log(f"{self._prefix}/policy/inference_ms", rr.Scalars(latency_ms))

    def log_action_trajectory(self, action_chunk: list[Action], step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        if not action_chunk:
            return
        n_joints = len(action_chunk[0]["joint_velocities"])
        for j in range(n_joints):
            rr.log(
                f"{self._prefix}/intent/joint_{j}_velocity",
                rr.Scalars(action_chunk[0]["joint_velocities"][j]),
            )
        rr.log(
            f"{self._prefix}/intent/gripper",
            rr.Scalars(action_chunk[0]["gripper_position"]),
        )
