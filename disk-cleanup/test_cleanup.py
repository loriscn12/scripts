"""Tests for disk-cleanup.sh, with systemd, Docker and the rest stood in by
small scripts on PATH. Run: python3 -m pytest scripts/disk-cleanup"""
import os

import pytest

from cleanup_coverage import run

STUBS = {
    "id": 'echo "${FAKE_UID:-0}"',
    # systemctl: `cat` succeeds for units listed in UNITS; stop/start fail
    # for the units named in STOP_FAIL / START_FAIL.
    "systemctl": 'echo "$*" >>"$LOG/systemctl"\n'
                 'case "$1" in\n'
                 '  cat) [[ " ${UNITS:-} " == *" $2 "* ]] ;;\n'
                 '  stop) [[ " ${STOP_FAIL:-} " != *" $2 "* ]] ;;\n'
                 '  start) [[ " ${START_FAIL:-} " != *" $2 "* ]] ;;\n'
                 '  enable) exit "${ENABLE_RC:-0}" ;;\n'
                 'esac',
    # pgrep: a job is running for the users listed in BUSY.
    "pgrep": 'echo "$*" >>"$LOG/pgrep"\n[[ " ${BUSY:-} " == *" $2 "* ]]',
    "docker": 'echo "$*" >>"$LOG/docker"\nexit "${DOCKER_RC:-0}"',
    "journalctl": 'echo "$*" >>"$LOG/journalctl"\nexit "${JOURNAL_RC:-0}"',
    "apt-get": 'echo "$*" >>"$LOG/apt-get"\nexit "${APT_RC:-0}"',
    # df: 10 GB free on the first call, 20 GB after.
    "df": 'n=$(cat "$LOG/df" 2>/dev/null || echo 0); echo $((n + 1)) >"$LOG/df"\n'
          'echo Avail; [ "$n" = 0 ] && echo " 10G" || echo " 20G"',
    # runuser: logged, then the command run (as the test's own user).
    "runuser": 'echo "$*" >>"$LOG/runuser"\npwd >>"$LOG/runuser.pwd"\n[[ -n "${RUNUSER_FAIL:-}" && "$*" == *"$RUNUSER_FAIL"* ]] && exit 1\nshift 3\nexec "$@"',
    # install: copies (the real one would also chown to root).
    "install": 'echo "$*" >>"$LOG/install"\n[ -n "${INSTALL_FAIL:-}" ] && exit 1\ncp "${@: -2:1}" "${@: -1}"',
}


@pytest.fixture
def env(tmp_path):
    bin_dir, log = tmp_path / "bin", tmp_path / "log"
    bin_dir.mkdir()
    log.mkdir()
    for name, body in STUBS.items():
        p = bin_dir / name
        p.write_text("#!/usr/bin/env bash\n" + body + "\n")
        p.chmod(0o755)
    units = tmp_path / "units"
    units.mkdir()
    return dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", LOG=str(log),
                RUNNERS=str(tmp_path / "runners"), DEST=str(tmp_path / "sbin" / "disk-cleanup.sh"),
                UNIT_DIR=str(units), LOCK=str(tmp_path / "lock"))


def runner(env, repo):
    """A runner folder with a checkout, the tool cache and a Go build cache."""
    d = os.path.join(env["RUNNERS"], repo)
    for sub in ("_work/" + repo + "/src", "_work/_tool/go", "_work/_temp", ".cache/go-build/ab", "externals"):
        os.makedirs(os.path.join(d, sub))
    return d


def log(env, name):
    try:
        with open(os.path.join(env["LOG"], name)) as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def test_cleans_an_idle_runner_and_keeps_its_tools(env, tmp_path):
    d = runner(env, "moneytrac")
    env["UNITS"] = "gha-runner-moneytrac.service"
    r = run("disk-cleanup.sh", env=env, cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(os.listdir(os.path.join(d, "_work"))) == ["_tool"]
    assert os.path.isdir(os.path.join(d, "_work/_tool/go"))
    assert not os.path.exists(os.path.join(d, ".cache/go-build"))
    assert os.path.isdir(os.path.join(d, "externals"))
    assert log(env, "pgrep") == [f"-u gha-moneytrac -f ^{d}/bin/Runner.Worker"]
    # deleted as the runner's own user, never as root
    assert [c.split(" -- ")[0] for c in log(env, "runuser")] == ["-u gha-moneytrac"] * 2
    # from /, not the caller's folder (which the runner's user can't enter)
    assert log(env, "runuser.pwd") == ["/", "/"]
    calls = log(env, "systemctl")
    assert calls.index("stop gha-runner-moneytrac.service") < calls.index("start gha-runner-moneytrac.service")
    assert "moneytrac: cleaned" in r.stdout
    assert "10 GB before, 20 GB now" in r.stdout


def test_prunes_only_build_cache_and_dangling_layers(env):
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert log(env, "docker") == ["builder prune -af", "image prune -f"]
    assert log(env, "journalctl") == ["--vacuum-time=14d"]
    assert log(env, "apt-get") == ["clean"]


def test_skips_a_runner_in_the_middle_of_a_job(env):
    d = runner(env, "mttk")
    env.update(UNITS="gha-runner-mttk.service", BUSY="gha-mttk")
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 0
    assert "mttk: a job is running, skipped" in r.stdout
    assert os.path.isdir(os.path.join(d, "_work/mttk"))
    assert not any(c.startswith("stop") for c in log(env, "systemctl"))


def test_skips_a_folder_without_a_runner_service(env):
    d = runner(env, "old")
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 0
    assert "old: no gha-runner-old.service, skipped" in r.stdout
    assert os.path.isdir(os.path.join(d, "_work/old"))


def test_ignores_folders_without_a_work_dir(env):
    os.makedirs(os.path.join(env["RUNNERS"], "bin"))
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 0
    assert log(env, "systemctl") == []


def test_keeps_files_when_the_runner_does_not_stop(env):
    d = runner(env, "lollilog")
    env.update(UNITS="gha-runner-lollilog.service", STOP_FAIL="gha-runner-lollilog.service")
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 0
    assert "lollilog: gha-runner-lollilog.service didn't stop, skipped" in r.stdout
    assert os.path.isdir(os.path.join(d, "_work/lollilog"))
    assert not any(c.startswith("start") for c in log(env, "systemctl"))


def test_fails_when_a_runner_does_not_start_again_but_cleans_the_rest(env):
    runner(env, "a")
    b = runner(env, "b")
    env.update(UNITS="gha-runner-a.service gha-runner-b.service", START_FAIL="gha-runner-a.service")
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 1
    assert "a: gha-runner-a.service didn't start again" in r.stdout
    assert "b: cleaned" in r.stdout
    assert sorted(os.listdir(os.path.join(b, "_work"))) == ["_tool"]
    assert log(env, "docker")  # the rest still ran


def test_carries_on_when_a_prune_fails(env):
    env.update(DOCKER_RC="1", JOURNAL_RC="1", APT_RC="1")
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 0
    for msg in ("docker build cache: prune failed", "docker dangling layers: prune failed",
                "journal: vacuum failed", "apt: clean failed"):
        assert msg in r.stdout
    assert "GB now" in r.stdout


@pytest.mark.parametrize("args", [(), ("install",)])
def test_refuses_to_run_without_root(env, args):
    d = runner(env, "moneytrac")
    env.update(FAKE_UID="1000", UNITS="gha-runner-moneytrac.service")
    r = run("disk-cleanup.sh", args, env=env)
    assert r.returncode == 1
    assert "run it as root" in r.stderr
    assert os.path.isdir(os.path.join(d, "_work/moneytrac"))
    assert log(env, "systemctl") == []


def test_install_copies_itself_and_enables_a_weekly_timer(env):
    os.makedirs(os.path.dirname(env["DEST"]))
    r = run("disk-cleanup.sh", ("install",), env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert log(env, "install")[0].startswith("-o root -g root -m 0755 ")
    with open(env["DEST"]) as f, open(os.path.join(os.path.dirname(__file__), "disk-cleanup.sh")) as src:
        assert f.read() == src.read()
    service = open(os.path.join(env["UNIT_DIR"], "disk-cleanup.service")).read()
    assert f"ExecStart={env['DEST']}\n" in service and "Type=oneshot" in service
    timer = open(os.path.join(env["UNIT_DIR"], "disk-cleanup.timer")).read()
    assert "OnCalendar=Sun *-*-* 04:30:00" in timer and "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer
    assert log(env, "systemctl") == ["daemon-reload", "enable --now disk-cleanup.timer"]
    assert "installed:" in r.stdout


def test_install_stops_when_the_copy_fails(env):
    env["INSTALL_FAIL"] = "1"
    r = run("disk-cleanup.sh", ("install",), env=env)
    assert r.returncode == 1
    assert "couldn't copy the script" in r.stderr
    assert not os.path.exists(os.path.join(env["UNIT_DIR"], "disk-cleanup.timer"))


def test_install_reports_a_timer_that_will_not_enable(env):
    os.makedirs(os.path.dirname(env["DEST"]))
    env["ENABLE_RC"] = "1"
    r = run("disk-cleanup.sh", ("install",), env=env)
    assert r.returncode == 1
    assert "couldn't enable disk-cleanup.timer" in r.stderr


def test_unknown_argument_prints_usage(env):
    r = run("disk-cleanup.sh", ("purge",), env=env)
    assert r.returncode == 1
    assert "usage: disk-cleanup.sh [install]" in r.stderr


def test_a_second_run_at_the_same_time_stops(env):
    import fcntl
    d = runner(env, "moneytrac")
    env["UNITS"] = "gha-runner-moneytrac.service"
    with open(env["LOCK"], "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 1
    assert "already running" in r.stderr
    assert os.path.isdir(os.path.join(d, "_work/moneytrac"))
    assert log(env, "systemctl") == []


def test_install_run_as_the_installed_copy_only_sets_up_the_timer(env):
    env["DEST"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "disk-cleanup.sh")
    r = run("disk-cleanup.sh", ("install",), env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert log(env, "install") == []
    assert os.path.exists(os.path.join(env["UNIT_DIR"], "disk-cleanup.timer"))
    assert log(env, "systemctl") == ["daemon-reload", "enable --now disk-cleanup.timer"]


def test_reports_files_the_runner_user_could_not_delete(env):
    runner(env, "moneytrac")
    env.update(UNITS="gha-runner-moneytrac.service", RUNUSER_FAIL="go-build")
    r = run("disk-cleanup.sh", env=env)
    assert r.returncode == 1
    assert "moneytrac: some files couldn't be deleted" in r.stdout
    assert "moneytrac: cleaned" not in r.stdout
    assert "start gha-runner-moneytrac.service" in log(env, "systemctl")  # started again all the same
