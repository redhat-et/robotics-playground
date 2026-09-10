# Simulator Deployment

Kustomize base for the Isaac Lab simulator used by Robotics Playground.

At pod start, a git-sync init container clones the environment repository
into an emptyDir volume. The Isaac Lab container then runs the specified
Python module from that checkout.

A Zenoh bridge sidecar exposes ROS 2 topics over Zenoh so the backend
can reach the simulator without requiring DDS on the network.

## Configuration

The following env vars on the `isaac-lab` container control what runs:

| Variable           | Default                                                  | Purpose                        |
|--------------------|----------------------------------------------------------|--------------------------------|
| `ENV_GIT_REPO`     | `https://github.com/redhat-et/ros2_manager_based_env.git`| Environment git repository     |
| `ENV_GIT_REF`      | `main`                                                   | Branch, tag, or commit to clone|
| `SIMULATOR_MODULE` | `ros2_manager_based_env.custom_env_3_3.run_playground`   | Python module to run           |
| `ROS_DOMAIN_ID`    | `0`                                                      | ROS 2 domain ID                |
| `RMW_IMPLEMENTATION`| `rmw_fastrtps_cpp`                                      | ROS 2 middleware               |

Override these via a Kustomize overlay (e.g. `kustomize edit add patch ...`).

## Troubleshooting

### Init container cannot clone the repository

```bash
oc logs deployment/simulator -c clone-env
```

Typical causes: GitHub unreachable from cluster, branch/tag does not
exist, repository is private with no credentials configured.

### Python module not found

The `SIMULATOR_MODULE` must exist in the cloned repository. Check that
`ENV_GIT_REF` points to a revision containing the expected module, and
that `/git/repo` appears first in `PYTHONPATH`:

```bash
oc exec deployment/simulator -c isaac-lab -- printenv PYTHONPATH
```

### Pod remains Pending

```bash
oc describe pod -l app.kubernetes.io/name=simulator
```

Typical causes: no GPU available, NVIDIA device plugin missing,
insufficient CPU/memory, image pull failure.

### Cannot reach Zenoh

```bash
oc get service simulator-zenoh
oc get endpoints simulator-zenoh
oc logs deployment/simulator -c zenoh-bridge
```
