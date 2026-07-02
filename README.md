# Robotics Playground

An interactive web application for experimenting with robot policy models (VLAs, world-action models) by connecting them to simulated or physical robots.

Part of the [Physical AI Studio](https://github.com/redhat-et/physical-ai-platform-demo).

## Development

```bash
make dev          # Start frontend + backend dev servers
make test         # Run all tests
make lint         # Run all linters
make build        # Build container images
make compose-up   # Start Podman Compose stack
make compose-down # Stop Podman Compose stack
make validate     # Validate Kustomize manifests
```

## License

Apache 2.0
