#!/usr/bin/env bash
# fusion-smallbusiness lifecycle manager (start|stop|restart|status|doctor)
# REST API on port 11490 (registered in architecture/port-registry.yaml, boot tier T1).
# Callers: fusion-supervisor (orchestrates via this script), fusion-studio, manual ops.
# Affected API: start.sh start|stop|restart|status|doctor; status exits 0 if running, 1 if not.
# Data schemas: PID file .fusion-smallbusiness.pid; logs/stdout.log + logs/stderr.log.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Optional persistent env (secrets like FSB_SECRET_KEY / FUSION_CLIENT_KEY).
ENV_FILE="${FUSION_SMALLBUSINESS_ENV_FILE:-$HOME/.fusion-smallbusiness/env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

PID_FILE="${SCRIPT_DIR}/.fusion-smallbusiness.pid"
LOG_DIR="${SCRIPT_DIR}/logs"
STDOUT_LOG="${LOG_DIR}/stdout.log"
STDERR_LOG="${LOG_DIR}/stderr.log"
PORT="${FSB_SERVER_PORT:-11490}"
HOST="${FSB_SERVER_HOST:-127.0.0.1}"

mkdir -p "$LOG_DIR"

log_info()  { printf "\033[0;32m[INFO]\033[0m  %s\n" "$*"; }
log_error() { printf "\033[0;31m[ERROR]\033[0m %s\n" "$*"; }
log_warn()  { printf "\033[0;33m[WARN]\033[0m  %s\n" "$*"; }

is_running() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

resolve_venv() {
    # Resolution order: FUSION_SMALLBUSINESS_VENV > shared monorepo venv.
    # A repo-local .venv is intentionally NOT used (workspace policy: one shared
    # Python 3.12 venv at the monorepo root — see README "Environment Setup").
    if [[ -n "${FUSION_SMALLBUSINESS_VENV:-}" ]]; then
        echo "${FUSION_SMALLBUSINESS_VENV}"
        return 0
    fi
    if [[ -f "/Users/dahai/fusion/.venv/bin/activate" ]]; then
        echo "/Users/dahai/fusion/.venv"
        return 0
    fi
    return 1
}

ensure_venv() {
    local venv
    if ! venv="$(resolve_venv)"; then
        log_error "no venv found — activate the shared monorepo venv or set FUSION_SMALLBUSINESS_VENV"
        return 1
    fi
    if [[ -f "${venv}/bin/activate" ]]; then
        # shellcheck disable=SC1091
        source "${venv}/bin/activate"
    else
        log_error "venv not found at ${venv} (set FUSION_SMALLBUSINESS_VENV)"
        return 1
    fi
}

port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
    elif command -v nc >/dev/null 2>&1; then
        nc -z 127.0.0.1 "$PORT" >/dev/null 2>&1
    else
        return 1
    fi
}

check_port_registry() {
    local service="fusion-smallbusiness"
    local registry="${FUSION_REGISTRY:-$HOME/fusion/architecture/port-registry.yaml}"
    if [ ! -f "$registry" ]; then
        log_warn "port-registry.yaml not found at $registry — registry self-check skipped"
        return 0
    fi
    if grep -A3 "^  ${service}:" "$registry" 2>/dev/null | grep -q "port: $PORT$"; then
        return 0
    fi
    if [ "${FUSION_SKIP_REGISTRY_CHECK:-}" != "1" ]; then
        log_error "port $PORT for ${service} not registered in $registry — refusing to start"
        return 1
    fi
    log_warn "registry check bypassed (FUSION_SKIP_REGISTRY_CHECK=1)"
    return 0
}

do_start() {
    if is_running; then
        log_info "fusion-smallbusiness already running (pid $(cat "$PID_FILE"))"
        return 0
    fi
    ensure_venv
    if port_in_use; then
        log_error "port ${PORT} already in use — refusing to start (set FSB_SERVER_PORT to change)"
        return 1
    fi
    check_port_registry
    log_info "starting fusion-smallbusiness API on ${HOST}:${PORT} ..."
    FSB_SERVER_HOST="$HOST" FSB_SERVER_PORT="$PORT" nohup python -m fsb \
        >> "$STDOUT_LOG" 2>> "$STDERR_LOG" &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    sleep 2
    if is_running; then
        log_info "fusion-smallbusiness started (pid $pid, port $PORT)"
    else
        log_error "fusion-smallbusiness failed to start, see $STDERR_LOG"
        rm -f "$PID_FILE"
        return 1
    fi
}

do_stop() {
    if ! is_running; then
        log_info "fusion-smallbusiness not running"
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    log_info "stopping fusion-smallbusiness (pid $pid)"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        log_error "force kill (pid $pid)"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    log_info "fusion-smallbusiness stopped"
}

do_status() {
    if is_running; then
        echo "running (pid $(cat "$PID_FILE"), port $PORT)"
        return 0
    fi
    echo "stopped"
    return 1
}

do_doctor() {
    local ok=0
    if is_running; then
        log_info "process: running (pid $(cat "$PID_FILE"), port $PORT)"
    else
        log_error "process: not running"
        ok=1
    fi
    if port_in_use; then
        if is_running; then
            log_info "port ${PORT}: listening"
        else
            log_error "port ${PORT}: in use by another process"
            ok=1
        fi
    else
        if is_running; then
            log_error "port ${PORT}: not listening (process alive but port closed)"
            ok=1
        else
            log_info "port ${PORT}: free"
        fi
    fi
    local venv
    if venv="$(resolve_venv)"; then
        if [[ -f "${venv}/bin/activate" ]]; then
            log_info "venv: ${venv} (ok)"
        else
            log_error "venv: ${venv} not found"
            ok=1
        fi
    else
        log_error "venv: shared monorepo venv not found (set FUSION_SMALLBUSINESS_VENV)"
        ok=1
    fi
    return "$ok"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    ACTION="${1:-start}"
    case "$ACTION" in
        start)  do_start ;;
        stop)   do_stop ;;
        status) do_status ;;
        doctor) do_doctor ;;
        restart) do_stop || true; do_start ;;
        log)    exec tail -n 50 -f "$STDERR_LOG" "$STDOUT_LOG" ;;
        *) echo "usage: $0 {start|stop|status|restart|doctor|log}" >&2; exit 1 ;;
    esac
fi
