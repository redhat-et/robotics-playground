from __future__ import annotations

import contextlib
import logging
import queue
import threading
from typing import TYPE_CHECKING

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

if TYPE_CHECKING:
    from robotics_playground.bridges.protocol import Action, Observation

logger = logging.getLogger(__name__)

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

_QUEUE_MAXSIZE = 64
_SENTINEL = None


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

        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._worker_thread: threading.Thread | None = None

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            try:
                item()
            except Exception:
                logger.exception("Rerun worker: error processing log item")

    def _submit(self, fn) -> None:
        try:
            self._queue.put_nowait(fn)
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait(fn)

    def flush(self) -> None:
        if self._worker_thread is None or not self._worker_thread.is_alive():
            return
        done = threading.Event()
        self._submit(done.set)
        done.wait(timeout=10.0)

    def shutdown(self) -> None:
        if self._worker_thread is None:
            return
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                self._queue.get_nowait()
            with contextlib.suppress(queue.Full):
                self._queue.put_nowait(_SENTINEL)
        self._worker_thread.join(timeout=5.0)
        if not self._worker_thread.is_alive():
            self._worker_thread = None
        else:
            logger.warning("Rerun worker thread did not terminate within timeout")

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

        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="rerun-logger"
        )
        self._worker_thread.start()

        ready = threading.Event()
        init_error: list[BaseException] = []
        port = self._port
        web_port = self._web_port
        cors = self._cors_allow_origin
        prefix = self._prefix

        def _init():
            try:
                rr.init("robotics_playground")
                blueprint = self._build_blueprint()
                rr.serve_grpc(
                    grpc_port=port,
                    default_blueprint=blueprint,
                    server_memory_limit="512MiB",
                    cors_allow_origin=cors,
                )
                rr.serve_web_viewer(
                    web_port=web_port,
                    open_browser=False,
                )
                rr.send_blueprint(blueprint)
                rr.set_time("step", sequence=0)
                rr.log(prefix, rr.Clear(recursive=True))
            except Exception as exc:
                init_error.append(exc)
            finally:
                ready.set()

        self._submit(_init)
        if not ready.wait(timeout=30.0):
            self.shutdown()
            raise RuntimeError("Rerun initialization timed out")
        if init_error:
            self.shutdown()
            raise RuntimeError("Rerun initialization failed") from init_error[0]
        self._initialized = True

    def clear(self):
        if not self._initialized:
            return
        clear_step = self._step_offset + self._last_step + 1
        self._step_offset = clear_step + 1
        self._last_step = 0

        prefix = self._prefix

        def _do_clear():
            rr.set_time("step", sequence=clear_step)
            rr.log(prefix, rr.Clear(recursive=True))
            rr.log("session/instructions", rr.Clear(recursive=True))

        self._submit(_do_clear)

    def log_observation(self, obs: Observation, step: int, *, cameras: bool = True):
        effective_step = self._step_offset + step
        self._last_step = step

        cameras_data = {k: v.copy() for k, v in obs["cameras"].items()} if cameras else {}
        joints = list(obs["joint_positions"])
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            for name, image in cameras_data.items():
                rr.log(f"{prefix}/camera/{name}", rr.Image(image))
            for i, pos in enumerate(joints):
                label = PANDA_JOINT_LABELS[i] if i < len(PANDA_JOINT_LABELS) else f"joint_{i}"
                rr.log(
                    f"{prefix}/joints/{label}",
                    rr.Scalars(pos),
                    rr.SeriesLines(names=[label]),
                )

        self._submit(_do_log)

    def log_action(self, action: Action, step: int):
        effective_step = self._step_offset + step
        positions = list(action["joint_positions"])
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            for i, val in enumerate(positions):
                rr.log(f"{prefix}/actions/dim_{i}", rr.Scalars(float(val)))

        self._submit(_do_log)

    def log_instruction(self, text: str, step: int):
        effective_step = self._step_offset + step

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            rr.log("session/instructions", rr.TextLog(text))

        self._submit(_do_log)

    def log_raw_action_tensor(self, actions: np.ndarray, step: int):
        effective_step = self._step_offset + step
        first_row = actions[0].copy()
        n_dims = actions.shape[1]
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            for dim in range(n_dims):
                label = PANDA_JOINT_LABELS[dim] if dim < len(PANDA_JOINT_LABELS) else f"dim_{dim}"
                rr.log(
                    f"{prefix}/policy/raw_output/{label}",
                    rr.Scalars(float(first_row[dim])),
                    rr.SeriesLines(names=[label]),
                )

        self._submit(_do_log)

    def log_inference_latency(self, latency_ms: float, step: int):
        effective_step = self._step_offset + step
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            rr.log(f"{prefix}/policy/inference_ms", rr.Scalars(latency_ms))

        self._submit(_do_log)

    def log_action_trajectory(self, action_chunk: list[Action], step: int):
        effective_step = self._step_offset + step
        if not action_chunk:
            return
        first = action_chunk[0]
        velocities = list(first["joint_velocities"])
        gripper = first["gripper_position"]
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            for j, vel in enumerate(velocities):
                rr.log(f"{prefix}/intent/joint_{j}_velocity", rr.Scalars(vel))
            rr.log(f"{prefix}/intent/gripper", rr.Scalars(gripper))

        self._submit(_do_log)
