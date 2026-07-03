# Spike: Hummingbird + Rerun SDK Compatibility

**Date:** 2026-07-03
**Status:** PASS (with one workaround)

## Rerun SDK on hi/python:3.14

### Import Test

Rerun SDK 0.33.1 imports and runs successfully in `registry.access.redhat.com/hi/python:3.14` after one fix.

**Issue found:** NumPy 2.5.0 (a Rerun SDK dependency) ships precompiled C extensions that link against `libstdc++.so.6`. The `hi/python:3.14` distroless runtime image does not include this library, causing:

```
ImportError: libstdc++.so.6: cannot open shared object file: No such file or directory
```

**Fix applied:** Copy `libstdc++.so.6` from the builder stage in the Containerfile:

```dockerfile
COPY --from=builder /usr/lib64/libstdc++.so.6 /usr/lib64/libstdc++.so.6
```

This is a one-line addition. The library exists in `hi/python:3.14-builder` at `/usr/lib64/libstdc++.so.6`.

### gRPC Server Test

After the libstdc++ fix, Rerun's gRPC server starts successfully in the container:

```
$ podman run --rm robotics-playground:fix-test python -c "
import rerun as rr
rr.init('test')
rr.serve_grpc(grpc_port=9876)
print('Rerun gRPC server started OK')
"
Rerun gRPC server started OK
```

### Verified Package Versions

- Python 3.14
- NumPy 2.5.0
- Rerun SDK 0.33.1
- FastAPI 0.139.0
- Uvicorn 0.35.0

All import and function correctly in `hi/python:3.14` with the libstdc++ workaround.

## ROS 2 Client Options for Phase 2

| Option | Feasibility | Notes |
| -------- | ------------- | ------- |
| rclpy on hi/python:3.14 | No | rclpy requires native ROS 2 libraries (rcl, rmw, DDS implementation). Cannot install RPMs in distroless image. Multi-stage build would need the full ROS 2 SDK in the builder. |
| Pure-Python DDS client (e.g. pyrtps) | Possible but immature | pyrtps provides a pure-Python RTPS implementation. Limited ecosystem, no maintained ROS 2 message type support. Would need custom serialization. |
| Multi-stage build with ROS 2 | Yes | Use a ROS 2 base image (e.g. `ros:jazzy`) as builder, compile rclpy and dependencies, copy native libs to runtime. Increases image size but is well-understood. |
| UBI9 Python base (fallback) | Yes | Always works. Allows dnf install of ROS 2 packages. Loses distroless benefits (larger image, more attack surface). |
| ROS 2 bridge via subprocess/socket | Yes | Run a lightweight ROS 2 bridge as a sidecar container (UBI9-based) that exposes topics over WebSocket/gRPC to the main backend. Keeps backend distroless, isolates ROS 2 dependency. |

## Recommendation

For Phase 2, use the **sidecar bridge approach**: keep the backend in `hi/python:3.14` (distroless) and run a separate ROS 2 bridge container on a UBI9 or ROS 2 base image. The bridge subscribes to ROS 2 topics and forwards observations to the backend over an internal gRPC or WebSocket connection. This:

1. Keeps the main backend lean and distroless
2. Isolates the ROS 2 native dependency to one container
3. Allows independent scaling and updates of the ROS 2 bridge
4. Matches the existing architecture where bridges are separate concerns

If sidecar complexity is too high for the initial implementation, fall back to **multi-stage build** with ROS 2 native libs copied from a ROS 2 builder image.
