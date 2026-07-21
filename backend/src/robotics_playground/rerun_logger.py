from __future__ import annotations

import contextlib
import io
import logging
import queue
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import rerun as rr
import rerun.blueprint as rrb
from PIL import Image

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
_JPEG_QUALITY = 85
_LOG_TIMEOUT = 2.0


def _encode_jpeg(image: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(image).save(buf, format="JPEG", quality=_JPEG_QUALITY)
    return buf.getvalue()


class RerunLogger:
    def __init__(
        self,
        port: int = 9876,
        policy_index: int = 0,
        camera_names: list[str] | None = None,
        cors_allow_origin: list[str] | None = None,
        recording_dir: str = "",
    ):
        self._port = port
        self._cors_allow_origin = cors_allow_origin
        self._recording_dir = recording_dir
        self._prefix = f"session/policy_{policy_index}"
        names = camera_names or ["exterior_1", "exterior_2", "wrist"]
        self._camera_names = sorted(names, key=lambda n: (n == "wrist", n))
        self._initialized = False
        self._step_offset = 0
        self._last_step = 0

        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._worker_thread: threading.Thread | None = None
        self._recording: rr.RecordingStream | None = None
        self._disk_recording: rr.RecordingStream | None = None

    def _worker_loop(self) -> None:
        def _run_with_recording(fn):
            disk_rec = self._disk_recording
            if disk_rec is not None:
                rr.set_thread_local_data_recording(disk_rec)
                try:
                    fn()
                except Exception:
                    logger.exception("Rerun disk log failed")

            viewer_rec = self._recording
            if viewer_rec is not None:
                rr.set_thread_local_data_recording(viewer_rec)
            try:
                fn()
            except Exception:
                logger.exception("Rerun viewer log failed")

        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                break
            t = threading.Thread(target=_run_with_recording, args=(item,), daemon=True)
            t.start()
            t.join(timeout=_LOG_TIMEOUT)
            if t.is_alive():
                logger.debug("Rerun log call exceeded %ss timeout, skipping", _LOG_TIMEOUT)

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
        cors = self._cors_allow_origin
        prefix = self._prefix
        recording_dir = self._recording_dir

        def _init():
            try:
                rr.init("robotics_playground")
                self._recording = rr.get_global_data_recording()
                blueprint = self._build_blueprint()
                rr.serve_grpc(
                    grpc_port=port,
                    default_blueprint=blueprint,
                    server_memory_limit="64MiB",
                    cors_allow_origin=cors,
                )
                if recording_dir:
                    rec_path = Path(recording_dir)
                    rec_path.mkdir(parents=True, exist_ok=True)
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    rrd_file = rec_path / f"session_{ts}.rrd"
                    self._disk_recording = rr.RecordingStream("robotics_playground_disk")
                    self._disk_recording.save(str(rrd_file))
                    logger.info("Disk recording: %s", rrd_file)
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

        cameras_data = {k: _encode_jpeg(v) for k, v in obs["cameras"].items()} if cameras else {}
        joints = list(obs["joint_positions"])
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            for name, jpeg_bytes in cameras_data.items():
                rr.log(
                    f"{prefix}/camera/{name}",
                    rr.EncodedImage(contents=jpeg_bytes, media_type="image/jpeg"),
                )
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
        positions = list(first["joint_positions"])
        gripper = first["gripper_position"]
        prefix = self._prefix

        def _do_log():
            rr.set_time("step", sequence=effective_step)
            for j, pos in enumerate(positions):
                label = PANDA_JOINT_LABELS[j] if j < len(PANDA_JOINT_LABELS) else f"joint_{j}"
                rr.log(
                    f"{prefix}/policy/target/{label}",
                    rr.Scalars(pos),
                    rr.SeriesLines(names=[label]),
                )
            rr.log(f"{prefix}/policy/target/gripper", rr.Scalars(gripper))

        self._submit(_do_log)
