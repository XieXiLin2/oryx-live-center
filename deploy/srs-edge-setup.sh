#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# SRS Edge one-click installer for srs-live-center.
#
# Usage:
#   sudo ORIGIN_HOST=origin.example.com \
#        ORIGIN_HTTP_BASE=https://origin.example.com \
#        CANDIDATE=203.0.113.10 \
#        ./srs-edge-setup.sh
#
# Env vars:
#   ORIGIN_HOST       (required) host:port of the Origin RTMP (default port 1935)
#   ORIGIN_HTTP_BASE  (optional) http base for on_play hooks, default: http://$ORIGIN_HOST
#   CANDIDATE         (optional) this edge node's public IP (auto-detected if omitted)
#   EDGE_DIR          (optional) deploy dir, default /opt/srs-edge
#   SRS_IMAGE         (optional) docker image, default ossrs/srs:6
# -----------------------------------------------------------------------------
set -euo pipefail

log()  { printf "\033[1;32m[edge]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[edge]\033[0m %s\n" "$*"; }
die()  { printf "\033[1;31m[edge]\033[0m %s\n" "$*" >&2; exit 1; }

# -------- args --------
: "${ORIGIN_HOST:?ORIGIN_HOST is required, e.g. ORIGIN_HOST=origin.example.com}"
ORIGIN_HTTP_BASE="${ORIGIN_HTTP_BASE:-http://${ORIGIN_HOST%:*}}"
EDGE_DIR="${EDGE_DIR:-/opt/srs-edge}"
SRS_IMAGE="${SRS_IMAGE:-ossrs/srs:6}"

# Normalize ORIGIN_HOST - ensure it has a port.
case "$ORIGIN_HOST" in
  *:*) ;;
  *)   ORIGIN_HOST="${ORIGIN_HOST}:1935" ;;
esac

# Auto-detect candidate.
if [ -z "${CANDIDATE:-}" ]; then
  log "Detecting public IP ..."
  CANDIDATE="$(curl -fsSL https://api.ipify.org || true)"
  [ -n "$CANDIDATE" ] || die "Failed to detect public IP; please pass CANDIDATE explicitly."
fi

log "ORIGIN_HOST      = $ORIGIN_HOST"
log "ORIGIN_HTTP_BASE = $ORIGIN_HTTP_BASE"
log "CANDIDATE        = $CANDIDATE"
log "EDGE_DIR         = $EDGE_DIR"

# -------- install docker if missing --------
if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found - installing via get.docker.com ..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

if ! docker compose version >/dev/null 2>&1; then
  die "docker compose plugin not found. Install docker-compose-plugin manually."
fi

# -------- create files --------
mkdir -p "$EDGE_DIR"
cd "$EDGE_DIR"

cat > srs-edge.conf <<EOF
listen              1935;
max_connections     2000;
daemon              off;
srs_log_tank        console;

http_api {
    enabled on;
    listen  1985;
    crossdomain on;
}

http_server {
    enabled on;
    listen  8080;
    crossdomain on;
}

rtc_server {
    enabled on;
    listen  8000;
    candidate \$CANDIDATE;
}

vhost __defaultVhost__ {
    cluster {
        mode    remote;
        origin  ${ORIGIN_HOST};
    }

    http_remux {
        enabled on;
        mount   [vhost]/[app]/[stream].flv;
    }

    rtc {
        enabled on;
        rtmp_to_rtc on;
    }

    http_hooks {
        enabled  on;
        on_play  ${ORIGIN_HTTP_BASE}/api/hooks/on_play;
        on_stop  ${ORIGIN_HTTP_BASE}/api/hooks/on_stop;
    }
}
EOF

cat > docker-compose.yml <<EOF
version: "3.8"
services:
  srs-edge:
    image: ${SRS_IMAGE}
    container_name: srs-edge
    restart: unless-stopped
    command: ["./objs/srs", "-c", "conf/srs.conf"]
    ports:
      - "1935:1935"
      - "1985:1985"
      - "8080:8080"
      - "8000:8000/udp"
    volumes:
      - ./srs-edge.conf:/usr/local/srs/conf/srs.conf:ro
    environment:
      - CANDIDATE=${CANDIDATE}
EOF

log "Pulling image ${SRS_IMAGE} and starting ..."
docker compose pull
docker compose up -d

log "Edge started. Check status:"
echo "  docker logs -f srs-edge"
echo
log "Quick playback test from this Edge:"
echo "  curl -I http://127.0.0.1:8080/live/<stream>.flv"
echo
log "Done."
