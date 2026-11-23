# disk-cleanup

Frees space on ubuntu-server's root disk (`/`), weekly and when the disk
alert fires ([playbook](https://github.com/loriscn12/infrastructure/blob/main/documentation/alerts/disk-space.md), infrastructure repo). Added
2026-11-23, when `/` reached 98%: the CI runners' folders had grown to 15 GB
and Docker's build cache to 3 GB.

## What it deletes

Only what is rebuilt on demand:

| What | Kept |
|---|---|
| Each GitHub runner (`/opt/gha-runner/<repo>`): `_work/*` (old checkouts, build output) and `.cache/go-build`, with the runner stopped and started again. A runner running a job is skipped (stopping it would cancel the job) | `_work/_tool` (Go, Node), `externals`, the Go module cache |
| All Docker build cache, dangling layers | tagged images, containers, volumes: the host's own containers share this Docker |
| Journal entries older than 14 days, apt's downloaded packages | |

Kubernetes images are left to the kubelet, which deletes unused ones above
85% use. The CI hook ([`ci-runner-job-completed.sh`](https://github.com/loriscn12/infrastructure/blob/main/scripts/ci-runner-job-completed.sh), infrastructure repo) cleans Docker
after every job but keeps build cache up to 3 days old; this also clears
that, and the runners' folders, which nothing cleaned.

Not cleaned yet: other caches in the runners' folders (npm, pip, old Go and
Node versions in `_work/_tool`). If `/opt/gha-runner` grows again, measure
with `sudo du -sh /opt/gha-runner/*/{.cache/*,.npm,go,_work/_tool}`.

How it stays safe:
- The runners' deletions run **as the runner's user** (`runuser`), never
  as root: CI code controls that folder, and a symlink planted there would
  otherwise make root delete elsewhere.
- One run at a time (a lock in `/run`).
- A job is detected by the runner's own `bin/Runner.Worker` running. A job
  that starts in the instant between that check and the stop is cancelled;
  CI does run at night, but the window is milliseconds.
- Stopping a runner doesn't kill processes a job left behind
  (`KillMode=process`); they can only touch what their user owns.

## Install (once, and after a change)

```
! git -C ~/scripts fetch -q && git -C ~/scripts show origin/main:disk-cleanup/disk-cleanup.sh | sudo install -o root -g root -m 0755 /dev/stdin /usr/local/sbin/disk-cleanup.sh && sudo /usr/local/sbin/disk-cleanup.sh install
```
It installs what is merged on GitHub (`origin/main`), never the working
copy in `~/scripts`: agents can edit that, and this runs as root.
Copies the script to `/usr/local/sbin/disk-cleanup.sh` (root-owned: the
timer never runs a file anyone else can change) and enables
`disk-cleanup.timer` (Sundays 04:30; missed runs catch up at boot). A
systemd timer rather than cron, so each run's output is in the journal. The
copy doesn't follow the repo: after a change to the script, run
the same command again.

## Use

| Command | Does |
|---|---|
| `sudo /usr/local/sbin/disk-cleanup.sh` | clean now; prints free GB before and after |
| `systemctl list-timers disk-cleanup.timer` | next run |
| `journalctl -u disk-cleanup` | what each run did |

It exits 1 if a runner didn't start again: check
`systemctl status gha-runner-<repo>`.

## Tests

`python3 -m pytest disk-cleanup` (needs `pytest`; this repo has no CI, so run
them before every change). Under 85% line coverage the run fails
(`bash_coverage.py`, a copy of the infrastructure repo's `scripts/bash_coverage.py`).
