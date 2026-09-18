#!/usr/bin/env bash
# Smoke test for Robotics Playground on OpenShift.
#
# Checks that the simulator, backend, and UI pods are healthy and that
# data is flowing through the ROS 2 / Zenoh pipeline.
#
# Usage:
#   ./tools/smoke-test.sh              # run all checks
#   ./tools/smoke-test.sh --wait 300   # wait up to 300s for pods to be ready first
#
# Exit codes:
#   0  all checks passed
#   1  one or more checks failed

set -euo pipefail

NS_SIM="physical-ai"
NS_UI="redhat-ods-applications"
DEPLOY_SIM="simulator"
DEPLOY_BACKEND="robotics-playground"
DEPLOY_UI="robotics-playground-ui"
WAIT_TIMEOUT=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wait) WAIT_TIMEOUT="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

passed=0
failed=0
skipped=0

check() {
    local name="$1"
    shift
    printf "  %-50s " "$name"
    if output=$("$@" 2>&1); then
        echo "PASS"
        passed=$((passed + 1))
    else
        echo "FAIL"
        echo "    $output" | head -5
        failed=$((failed + 1))
    fi
    return 0
}

skip() {
    local name="$1"
    local reason="$2"
    printf "  %-50s SKIP (%s)\n" "$name" "$reason"
    skipped=$((skipped + 1))
}

# --- Wait for rollout if requested ---

if [[ "$WAIT_TIMEOUT" -gt 0 ]]; then
    echo "Waiting up to ${WAIT_TIMEOUT}s for deployments to roll out..."
    oc rollout status "deployment/$DEPLOY_SIM" -n "$NS_SIM" --timeout="${WAIT_TIMEOUT}s" 2>/dev/null || true
    oc rollout status "deployment/$DEPLOY_BACKEND" -n "$NS_SIM" --timeout="${WAIT_TIMEOUT}s" 2>/dev/null || true
    echo
fi

# --- Collect state ---

sim_replicas=$(oc get deployment "$DEPLOY_SIM" -n "$NS_SIM" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
sim_ready=$(oc get deployment "$DEPLOY_SIM" -n "$NS_SIM" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
sim_image=$(oc get deployment "$DEPLOY_SIM" -n "$NS_SIM" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || echo "unknown")

backend_ready=$(oc get deployment "$DEPLOY_BACKEND" -n "$NS_SIM" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")

echo "=== Cluster State ==="
echo "  Simulator:  replicas=${sim_replicas} ready=${sim_ready:-0} image=${sim_image}"
echo "  Backend:    ready=${backend_ready:-0}"
echo

# --- Simulator checks ---

echo "=== Simulator (${DEPLOY_SIM}) ==="

if [[ "${sim_replicas}" == "0" ]]; then
    skip "Simulator deployment scaled up" "replicas=0"
    skip "Isaac Lab container running" "sim not running"
    skip "Isaac Lab container logs healthy" "sim not running"
    skip "Zenoh bridge container running" "sim not running"
    skip "Zenoh bridge listening" "sim not running"
    sim_running=false
else
    sim_running=true
    check "Simulator deployment scaled up" \
        test "${sim_replicas}" -gt 0

    check "Isaac Lab container running" \
        oc wait pod -l app.kubernetes.io/name=simulator -n "$NS_SIM" \
            --for=condition=Ready --timeout=10s

    check "Isaac Lab container logs healthy" bash -c "
        logs=\$(oc logs deployment/$DEPLOY_SIM -c isaac-lab -n $NS_SIM --tail=100 2>&1)
        if echo \"\$logs\" | grep -qiE 'Scene ready|bridge active|IsaacLab.*Logging|Starting.*environment|rclpy import OK|environment ready|topics active|Creating ROS2'; then
            exit 0
        elif echo \"\$logs\" | grep -qiE 'Error|Traceback|CrashLoop'; then
            echo 'Error found in logs'
            exit 1
        else
            echo 'No health indicator found in recent logs'
            exit 1
        fi
    "

    check "Zenoh bridge container running" bash -c "
        oc get pod -l app.kubernetes.io/name=simulator -n $NS_SIM \
            -o jsonpath='{.items[0].status.containerStatuses[?(@.name==\"zenoh-bridge\")].ready}' \
            | grep -q 'true'
    "

    check "Zenoh bridge listening" bash -c "
        oc logs deployment/$DEPLOY_SIM -c zenoh-bridge -n $NS_SIM --tail=50 2>&1 \
            | grep -qiE 'listen|7447|started|Route Publisher|Route Service'
    "
fi
echo

# --- Backend checks ---

echo "=== Backend (${DEPLOY_BACKEND}) ==="

check "Backend pod running" bash -c "
    test '${backend_ready:-0}' -gt 0
"

if [[ "${backend_ready:-0}" -gt 0 ]]; then
    check "Backend /api/health responds" bash -c "
        oc exec deployment/$DEPLOY_BACKEND -n $NS_SIM -c api -- \
            curl -sf http://localhost:8000/api/health | grep -q 'status'
    "

    if [[ "$sim_running" == true ]]; then
        check "Backend bridge connected" bash -c "
            health=\$(oc exec deployment/$DEPLOY_BACKEND -n $NS_SIM -c api -- \
                curl -sf http://localhost:8000/api/health 2>&1)
            if echo \"\$health\" | grep -q '\"degraded\"'; then
                echo \"Bridge not connected: \$health\"
                exit 1
            fi
        "

        check "Backend receiving observations" bash -c "
            oc logs deployment/$DEPLOY_BACKEND -n $NS_SIM -c api --tail=50 2>&1 \
                | grep -qiE 'observation|camera|joint'
        "
    else
        skip "Backend bridge connected" "sim not running"
        skip "Backend receiving observations" "sim not running"
    fi

    check "Backend /api/config responds" bash -c "
        oc exec deployment/$DEPLOY_BACKEND -n $NS_SIM -c api -- \
            curl -sf http://localhost:8000/api/config | grep -q 'wsUrl\|policy\|rerun'
    "

    check "Backend /api/models responds" bash -c "
        oc exec deployment/$DEPLOY_BACKEND -n $NS_SIM -c api -- \
            curl -sf http://localhost:8000/api/models | grep -q 'models\|dreamzero'
    "

    check "Backend uses CycloneDDS" bash -c "
        oc exec deployment/$DEPLOY_BACKEND -n $NS_SIM -c api -- \
            printenv RMW_IMPLEMENTATION | grep -q 'rmw_cyclonedds_cpp'
    "

    if [[ "$sim_running" == true ]]; then
        check "Zenoh bridge routes sim services" bash -c "
            oc logs deployment/$DEPLOY_BACKEND -n $NS_SIM -c zenoh-bridge --tail=100 2>&1 \
                | grep -qE 'set_simulation_state|get_simulation_state'
        "

        check "Zenoh bridge no invalid-request errors" bash -c "
            if oc logs deployment/$DEPLOY_BACKEND -n $NS_SIM -c zenoh-bridge --tail=100 2>&1 \
                | grep -q 'invalid request'; then
                echo 'Found invalid request warnings — DDS/Zenoh service mismatch'
                exit 1
            fi
        "
    else
        skip "Zenoh bridge routes sim services" "sim not running"
        skip "Zenoh bridge no invalid-request errors" "sim not running"
    fi
else
    skip "Backend /api/health responds" "pod not ready"
    skip "Backend bridge connected" "pod not ready"
    skip "Backend receiving observations" "pod not ready"
    skip "Backend /api/config responds" "pod not ready"
    skip "Backend /api/models responds" "pod not ready"
fi
echo

# --- UI checks ---

echo "=== UI (${DEPLOY_UI}) ==="

check "UI pod running" bash -c "
    ready=\$(oc get deployment $DEPLOY_UI -n $NS_UI -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
    test \"\${ready:-0}\" -gt 0
"
echo

# --- Summary ---

total=$((passed + failed + skipped))
echo "=== Summary ==="
echo "  Passed:  $passed"
echo "  Failed:  $failed"
echo "  Skipped: $skipped"
echo "  Total:   $total"
echo

if [[ $failed -gt 0 ]]; then
    echo "RESULT: FAIL ($failed check(s) failed)"
    exit 1
else
    echo "RESULT: PASS (${passed} passed, ${skipped} skipped)"
    exit 0
fi
