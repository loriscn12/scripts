#!/usr/bin/env bash
# disk-cleanup.sh: frees space on ubuntu-server's root disk, weekly by a
# systemd timer and by hand when the disk alert fires (infrastructure repo,
# documentation/alerts/disk-space.md). Deletes only what is rebuilt on demand:
#   - each GitHub runner's old checkouts (_work, except the _tool cache) and
#     Go build cache, with the runner stopped; a runner in the middle of a
#     job is skipped. Deleted as the runner's own user: its folder is under
#     its control, so a symlink planted there must not steer a root delete;
#   - all Docker build cache and dangling layers (never tagged images,
#     containers or volumes: the host's own containers share this Docker);
#   - journal entries older than 14 days, apt's downloaded packages.
# Kubernetes images are left to the kubelet, which deletes unused ones above
# 85% use. Lives in the scripts repo (loriscn12/scripts); the disk alert's
# playbook is in the infrastructure repo.
#   sudo disk-cleanup.sh            clean now
#   sudo disk-cleanup.sh install    install as /usr/local/sbin/disk-cleanup.sh
#                                   with a weekly timer (Sundays 04:30)
set -u
RUNNERS=${RUNNERS:-/opt/gha-runner}
DEST=${DEST:-/usr/local/sbin/disk-cleanup.sh}
UNIT_DIR=${UNIT_DIR:-/etc/systemd/system}
LOCK=${LOCK:-/run/disk-cleanup.lock}

log() { echo "disk-cleanup: $*"; }
die() { log "$*" >&2; exit 1; }
free_gb() { df --output=avail -BG / | tail -1 | tr -dc '0-9'; }

clean_runner() {  # runner dir; returns 1 if the runner didn't start again
  local dir=$1 repo user unit
  repo=$(basename "$dir")
  user="gha-$repo"
  unit="gha-runner-$repo.service"
  systemctl cat "$unit" >/dev/null 2>&1 || { log "$repo: no $unit, skipped"; return 0; }
  # A job runs in the runner's own Runner.Worker binary. Stopping the
  # service would cancel it.
  if pgrep -u "$user" -f "^$dir/bin/Runner.Worker" >/dev/null; then
    log "$repo: a job is running, skipped"
    return 0
  fi
  systemctl stop "$unit" || { log "$repo: $unit didn't stop, skipped"; return 0; }
  # A file the user can't delete (written as root by a container in a job)
  # fails the run; rm's message above says which.
  local deleted=1
  runuser -u "$user" -- find "$dir/_work" -mindepth 1 -maxdepth 1 ! -name _tool -exec rm -rf {} + || deleted=0
  runuser -u "$user" -- rm -rf "$dir/.cache/go-build" || deleted=0
  systemctl start "$unit" || { log "$repo: $unit didn't start again"; return 1; }
  [ "$deleted" = 1 ] || { log "$repo: some files couldn't be deleted"; return 1; }
  log "$repo: cleaned"
}

clean() {
  [ "$(id -u)" = 0 ] || die "run it as root (sudo)"
  # One run at a time: a second one could restart a runner while the first
  # is still deleting its checkouts.
  exec 9>"$LOCK"
  flock -n 9 || die "already running"
  # The runners' users can't enter most folders (sudo from /home/loris):
  # find stops if it can't use the folder it was started in.
  cd / || die "can't change to /"
  local before failed=0 dir
  before=$(free_gb)
  for dir in "${RUNNERS:?}"/*/; do
    [ -d "$dir/_work" ] || continue
    clean_runner "${dir%/}" || failed=1
  done
  docker builder prune -af >/dev/null 2>&1 || log "docker build cache: prune failed"
  docker image prune -f >/dev/null 2>&1 || log "docker dangling layers: prune failed"
  journalctl --vacuum-time=14d >/dev/null 2>&1 || log "journal: vacuum failed"
  apt-get clean || log "apt: clean failed"
  log "free on /: ${before} GB before, $(free_gb) GB now"
  return "$failed"
}

install_timer() {
  [ "$(id -u)" = 0 ] || die "run it as root (sudo)"
  # Run as the installed copy (the README's way): only the timer to set up.
  if [ "$(realpath "${BASH_SOURCE[0]}")" != "$(realpath -m "$DEST")" ]; then
    install -o root -g root -m 0755 "${BASH_SOURCE[0]}" "$DEST" || die "couldn't copy the script to $DEST"
  fi
  cat >"$UNIT_DIR/disk-cleanup.service" <<EOF
[Unit]
Description=Disk cleanup (disk-cleanup in the scripts repo)

[Service]
Type=oneshot
ExecStart=$DEST
EOF
  cat >"$UNIT_DIR/disk-cleanup.timer" <<EOF
[Unit]
Description=Weekly disk cleanup

[Timer]
OnCalendar=Sun *-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload && systemctl enable --now disk-cleanup.timer || die "couldn't enable disk-cleanup.timer"
  log "installed: $DEST, weekly (systemctl list-timers disk-cleanup.timer)"
}

case "${1:-}" in
  "") clean ;;
  install) install_timer ;;
  *) die "usage: disk-cleanup.sh [install]" ;;
esac
