# Shared by setup.sh and manage.sh. Requires Bash 3.2+ (included with macOS).
fail() { echo "BetterTube: $*" >&2; exit 1; }
require_docker() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || fail 'Install Docker Desktop (Windows/macOS) or Docker Engine with the Compose plugin (Linux), then run again.'
  docker info >/dev/null 2>&1 || fail 'Start Docker Desktop, or check that your Linux user has access to Docker, then run again.'
  docker compose up --help | grep -q -- '--wait-timeout' || fail 'Update Docker Compose: this setup needs version 2.20 or newer.'
}
compose_check() { docker compose config --quiet || fail 'Check the paths and values in .env. Docker could not read the configuration.'; }
helper() { docker compose run --rm -T --no-deps -e "BT_BACKUP_OWNER=$(id -u):$(id -g)" --entrypoint python "$@" < scripts/deploy.py; }
start_app() {
  compose_check
  echo 'Building BetterTube. The first build may take several minutes...'
  docker compose build || fail 'The build failed. Check your internet connection and the error above, then run setup again.'
  helper bt-api - check || fail 'Docker cannot write to both storage folders. Check folder permissions and Docker Desktop file sharing.'
  echo 'Starting services and waiting for the web app...'
  if ! docker compose up -d --wait --wait-timeout 240; then
    docker compose ps
    fail 'Startup failed. Check whether your chosen port is already used, then run docker compose logs --tail 60 to see service errors.'
  fi
  binding=$(docker compose port bt-api 6645) || fail 'Could not find the web port.'
  url="http://localhost:${binding##*:}"
  echo "BetterTube is ready: $url"
  echo 'Other home devices: replace localhost with this computer’s LAN IP address.'
  if [ "${BT_NO_BROWSER:-0}" != 1 ]; then
    if command -v open >/dev/null 2>&1; then open "$url" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 || true; fi
  fi
}
