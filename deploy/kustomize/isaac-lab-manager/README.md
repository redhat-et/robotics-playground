# Isaac Lab Manager-Based Environment Deployment

This Kustomize package runs the
[`redhat-et/ros2_manager_based_env`](https://github.com/redhat-et/ros2_manager_based_env)
Manager-Based Isaac Lab environment as the simulator used by Robotics Playground.

It is an alternative to the existing `deploy/kustomize/isaac-lab` deployment,
which runs the legacy standalone scene from `launch_ros2_scene.py`.

## Directory layout

Place this directory in the Robotics Playground repository:

```text
robotics-playground/
└── deploy/
    └── kustomize/
        ├── isaac-lab/              # Existing legacy simulator
        └── isaac-lab-manager/      # Manager-Based simulator
            ├── deployment.yaml
            ├── service-zenoh.yaml
            ├── zenoh-config.json5
            ├── kustomization.yaml
            └── README.md
```

## Architecture

```text
Robotics Playground backend
          │
          │ Zenoh TCP: isaac-lab-zenoh:7447
          ▼
┌──────────────────── isaac-lab Pod ────────────────────┐
│                                                       │
│  Isaac Lab container             Zenoh bridge sidecar │
│  ┌───────────────────────┐       ┌─────────────────┐  │
│  │ ManagerBasedRLEnv     │ ROS 2 │ zenoh-bridge-  │  │
│  │ ActionManager         │◄─────►│ ros2dds        │  │
│  │ ObservationManager    │       └────────┬────────┘  │
│  │ ROS 2 VLA bridge      │                │           │
│  └───────────────────────┘                │ TCP 7447  │
│                                           │           │
└───────────────────────────────────────────┼───────────┘
                                            │
                                            ▼
                              Robotics Playground network
```

The Manager-Based environment remains a separate Python package. Robotics
Playground does not copy or import the environment into its backend. The two
components communicate through ROS 2, with the Zenoh sidecar transporting ROS 2
data between the simulator Pod and the Robotics Playground backend.

## Startup sequence

1. Kubernetes creates the `isaac-lab` Pod.
2. The `clone-manager-based-env` init container starts first.
3. `git-sync` clones
   `https://github.com/redhat-et/ros2_manager_based_env.git` into an `emptyDir`
   volume.
4. The checkout is exposed inside the Pod as:

   ```text
   /git/repo
   ```

5. After the clone completes, Kubernetes starts the Isaac Lab container.
6. The repository root is added to `PYTHONPATH`, so the package can be imported
   directly without running `pip install`.
7. Isaac Lab starts this Python module:

   ```text
   ros2_manager_based_env.custom_env_3_3.run_playground
   ```

8. `run_playground.py` creates the `ManagerBasedRLEnv`, starts the ROS 2 bridge,
   publishes observations, and receives task-space VLA actions.
9. The Zenoh sidecar discovers the ROS 2 topics inside the same Pod.
10. The `isaac-lab-zenoh` Service exposes the Zenoh bridge on TCP port `7447` to
    Robotics Playground.

## Why the environment repository is cloned

Kubernetes cannot mount a GitHub repository directly as a volume. For this
development deployment, an init container performs a one-time clone into a
shared `emptyDir`:

```text
git-sync init container
        │ writes
        ▼
manager-env-source emptyDir
        │ mounted read-only
        ▼
Isaac Lab container
```

This keeps the environment source in its own repository while allowing
Robotics Playground to launch it.

This approach is intended for development and integration testing. A
production deployment should use a versioned simulator image with the
environment package already installed.

## Files

### `deployment.yaml`

Defines the `isaac-lab` Deployment.

It contains:

- a `git-sync` init container that clones `ros2_manager_based_env`;
- the NVIDIA Isaac Lab container;
- the Zenoh ROS 2 DDS bridge sidecar;
- the shared source volume;
- GPU, CPU, and memory requirements;
- the command that launches the Manager-Based environment.

The Deployment intentionally keeps the resource name `isaac-lab`, making it a
drop-in replacement for the legacy simulator.

### `service-zenoh.yaml`

Creates the Service:

```text
isaac-lab-zenoh:7447
```

The name is kept compatible with the existing Robotics Playground backend
configuration.

### `zenoh-config.json5`

Runs Zenoh in router mode and listens on:

```text
tcp/0.0.0.0:7447
```

The Isaac Lab and Zenoh containers share the same Pod network namespace.
Therefore `ROS_LOCALHOST_ONLY=1` in Isaac Lab and
`ros_localhost_only: true` in Zenoh allow DDS communication between the two
containers while avoiding DDS discovery outside the Pod.

### `kustomization.yaml`

Builds the Deployment and Service and generates the
`zenoh-isaac-lab-config` ConfigMap from `zenoh-config.json5`.

## Prerequisites

The target cluster must provide:

- an NVIDIA GPU node;
- the NVIDIA Kubernetes device plugin;
- access to `nvcr.io/nvidia/isaac-lab:2.3.2`;
- access to `registry.k8s.io` for `git-sync`;
- access to GitHub from the Pod network;
- enough resources for the requested CPU, memory, and GPU;
- the Robotics Playground backend configured to connect to
  `isaac-lab-zenoh:7447`.

The environment repository must contain:

```text
pyproject.toml
ros2_manager_based_env/
└── custom_env_3_3/
    └── run_playground.py
```

The Deployment checks for both files before starting Isaac Lab. If either file
is missing, the container exits immediately.

## Select a branch, tag, or commit

By default, the init container clones `main`:

```yaml
- name: MANAGER_ENV_GIT_REF
  value: main
```

For development, replace `main` with a feature branch:

```yaml
- name: MANAGER_ENV_GIT_REF
  value: feat/playground-integration
```

For reproducible deployments, use a tag or immutable commit SHA:

```yaml
- name: MANAGER_ENV_GIT_REF
  value: 0123456789abcdef0123456789abcdef01234567
```

Using a fixed commit prevents a Pod restart from unexpectedly loading newer
environment code.

## Deploy

From the root of `robotics-playground`:

```bash
oc apply -k deploy/kustomize/isaac-lab-manager
```

Equivalent Kubernetes command:

```bash
kubectl apply -k deploy/kustomize/isaac-lab-manager
```

Because this package uses the same Deployment and Service names as the legacy
variant, applying it updates the existing simulator instead of creating a
second simulator.

Do not apply the legacy and Manager-Based variants concurrently as independent
simulators unless their resource names, labels, Service names, ROS domains, and
GPU allocation are separated.

## Verify the deployment

Watch the rollout:

```bash
oc rollout status deployment/isaac-lab
```

Inspect the init container logs:

```bash
oc logs deployment/isaac-lab \
  -c clone-manager-based-env
```

Inspect the Isaac Lab logs:

```bash
oc logs -f deployment/isaac-lab \
  -c isaac-lab
```

Inspect the Zenoh bridge logs:

```bash
oc logs -f deployment/isaac-lab \
  -c zenoh-bridge
```

Confirm that the repository was cloned:

```bash
oc exec deployment/isaac-lab \
  -c isaac-lab \
  -- ls -la /git/repo
```

Confirm that the launcher exists:

```bash
oc exec deployment/isaac-lab \
  -c isaac-lab \
  -- test -f \
  /git/repo/ros2_manager_based_env/custom_env_3_3/run_playground.py
```

Inspect the generated manifests without applying them:

```bash
oc kustomize deploy/kustomize/isaac-lab-manager
```

## Switch back to the legacy simulator

Apply the original Kustomize directory:

```bash
oc apply -k deploy/kustomize/isaac-lab
```

This replaces the Manager-Based Pod specification with the existing
`launch_ros2_scene.py` deployment while retaining the same simulator and Zenoh
Service names.

## Environment update workflow

For the current development setup:

```text
1. Push changes to ros2_manager_based_env.
2. Update MANAGER_ENV_GIT_REF when using a new branch, tag, or commit.
3. Restart the isaac-lab Deployment.
4. git-sync clones the selected revision.
5. Isaac Lab starts the updated Manager-Based environment.
```

Restart the Deployment:

```bash
oc rollout restart deployment/isaac-lab
```

A running Pod does not continuously synchronize the repository because
`git-sync` is configured with `--one-time`.

## ROS 2 integration boundary

The environment package owns:

- scene creation;
- robot and camera configuration;
- Isaac Lab managers;
- physics and control timing;
- task-space action execution;
- simulator-side ROS 2 publishers and subscribers.

Robotics Playground owns:

- the user interface;
- session orchestration;
- the OpenPI connection;
- policy observation mapping;
- policy action validation;
- communication with the simulator through Zenoh and ROS 2.

The expected VLA contract is implemented by the environment launcher and its
ROS 2 bridge. In the current design, the environment publishes camera and robot
state observations and accepts relative task-space action chunks. The
Kubernetes manifests only launch and connect the components; they do not define
the observation or action semantics.

## Troubleshooting

### The init container cannot clone the repository

Check:

```bash
oc logs deployment/isaac-lab \
  -c clone-manager-based-env
```

Typical causes:

- GitHub is not reachable from the cluster;
- the selected branch, tag, or commit does not exist;
- the repository is private and no Git credentials are configured.

### `run_playground.py` is reported as missing

The selected Git revision does not contain:

```text
ros2_manager_based_env/custom_env_3_3/run_playground.py
```

Push the file or change `MANAGER_ENV_GIT_REF` to the correct revision.

### Python cannot import `ros2_manager_based_env`

Confirm:

```bash
oc exec deployment/isaac-lab \
  -c isaac-lab \
  -- printenv PYTHONPATH
```

The first entry must be:

```text
/git/repo
```

Also confirm that the repository contains:

```text
/git/repo/ros2_manager_based_env/__init__.py
```

### A Python dependency is missing

This development deployment imports the package from `PYTHONPATH`; it does not
install dependencies from `pyproject.toml`.

Dependencies not already present in the Isaac Lab image must be installed in a
custom image. Do not install them on every Pod start for a production
deployment.

### The Pod remains Pending

Check:

```bash
oc describe pod \
  -l app.kubernetes.io/name=isaac-lab
```

Typical causes:

- no GPU is available;
- the NVIDIA device plugin is missing;
- the node cannot satisfy the memory or CPU request;
- the Isaac Lab image cannot be pulled.

### Robotics Playground cannot reach Zenoh

Check the Service and endpoints:

```bash
oc get service isaac-lab-zenoh
oc get endpoints isaac-lab-zenoh
```

Then inspect the sidecar:

```bash
oc logs deployment/isaac-lab \
  -c zenoh-bridge
```

## Production packaging

After the integration is stable, replace runtime Git cloning with a versioned
container image:

```text
nvcr.io/nvidia/isaac-lab:2.3.2
            +
ros2_manager_based_env package
            =
quay.io/redhat-et/ros2-manager-based-env:<version-or-sha>
```

At that point:

- remove the `git-sync` init container;
- remove the `manager-env-source` volume;
- run the installed `run_playground` module from the custom image;
- pin the image by tag or digest;
- build and test the image in CI.

This makes startup independent of GitHub and guarantees that every Pod runs the
same environment version.
