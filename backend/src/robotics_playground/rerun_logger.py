from __future__ import annotations

from typing import TYPE_CHECKING

import rerun as rr
import rerun.blueprint as rrb

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Action, Observation


class RerunLogger:
    def __init__(
        self,
        port: int = 9876,
        web_port: int = 9090,
        policy_index: int = 0,
        camera_names: list[str] | None = None,
    ):
        self._port = port
        self._web_port = web_port
        self._prefix = f"session/policy_{policy_index}"
        self._camera_names = camera_names or ["exterior_1", "exterior_2", "wrist"]
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
        return rrb.Blueprint(
            rrb.Vertical(
                rrb.Horizontal(*camera_views),
                rrb.TimeSeriesView(
                    origin=f"{self._prefix}/joints",
                    name="Joint Positions",
                    plot_legend=rrb.PlotLegend(visible=False),
                ),
                row_shares=[7, 2],
            ),
            collapse_panels=True,
        )

    def start(self):
        if self._initialized:
            return
        rr.init("robotics_playground")
        server_uri = rr.serve_grpc(grpc_port=self._port)
        rr.serve_web_viewer(
            web_port=self._web_port,
            open_browser=False,
            connect_to=server_uri,
        )
        rr.send_blueprint(self._build_blueprint())
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
            rr.log(f"{self._prefix}/joints/joint_{i}", rr.Scalars(pos))

    def log_action(self, action: Action, step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        for i, val in enumerate(action["joint_positions"]):
            rr.log(f"{self._prefix}/actions/dim_{i}", rr.Scalars(float(val)))

    def log_instruction(self, text: str, step: int):
        rr.set_time("step", sequence=self._step_offset + step)
        rr.log("session/instructions", rr.TextLog(text))
