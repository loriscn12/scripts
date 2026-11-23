"""Line coverage for the shell scripts, from bash's own trace.

Each test runs a script with SHELLOPTS=xtrace and PS4 naming file and line,
written to a file (BASH_XTRACEFD) instead of stderr. At the end the lines
that ran are compared with the lines that hold a command, per script, and
the run fails below 85% (the owner's rule, agents/skills/code-change).

Used by each script folder's conftest.py:
    cov = Coverage(Path(__file__).parent, ("vpn.sh",))
    run = cov.run
    def pytest_sessionfinish(session, exitstatus): cov.finish(session)"""
import os
import re
import subprocess

THRESHOLD = 85
TRACE_LINE = re.compile(r"^\++(?:\S*/)?(\S+?):(\d+)\+ ")
# Lines with nothing to run: closers, openers, bare case patterns.
STRUCTURE = re.compile(r"^(?:[{}]|fi|done.*|esac|;;|else|then|do|.*\(\) \{|case .* in|[\w\"*. |-]+\)(?: ;;)?)$")


class Coverage:
    def __init__(self, here, scripts, after_run=None):
        self.here, self.after_run = here, after_run
        self.ran = {name: set() for name in scripts}

    def run(self, script, args=(), env=None, cwd=None, stdin=""):
        """Runs a script with tracing on; returns the CompletedProcess."""
        trace = self.here / f".trace.{os.getpid()}"
        fd = os.open(trace, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        full = dict(env or os.environ)
        full.update(SHELLOPTS="xtrace", PS4="+${BASH_SOURCE}:${LINENO}+ ", BASH_XTRACEFD=str(fd))
        try:
            return subprocess.run(["bash", str(self.here / script), *args], env=full, cwd=cwd, input=stdin,
                                  capture_output=True, text=True, pass_fds=(fd,), timeout=60)
        finally:
            if self.after_run:
                self.after_run(full)
            os.close(fd)
            for line in trace.read_text(errors="replace").splitlines():
                m = TRACE_LINE.match(line)
                if m and m.group(1) in self.ran:
                    self.ran[m.group(1)].add(int(m.group(2)))
            trace.unlink()

    def coverage(self):
        out = {}
        for name in self.ran:
            groups = statements(self.here / name)
            hit = [g for g in groups if self.ran[name] & set(g)]
            missed = [g[0] for g in groups if not self.ran[name] & set(g)]
            out[name] = (100 * len(hit) // max(len(groups), 1), missed)
        return out

    def finish(self, session):
        if not any(self.ran.values()):
            return
        low = False
        for name, (pct, missed) in self.coverage().items():
            print(f"\n{name}: {pct}% of commands ran; not run: lines {missed}")
            low |= pct < THRESHOLD
        if low:
            print(f"coverage below {THRESHOLD}%")
            session.exitstatus = 1


def statements(path):
    """Groups of line numbers that hold one command: lines joined by a
    trailing \\, | or && / ||; heredoc bodies and comments left out."""
    groups, current, heredoc = [], [], None
    for no, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if heredoc:
            if line == heredoc:
                heredoc = None
            continue
        m = re.search(r"<<-?'?(\w+)'?", line)
        if m and "<<<" not in line:
            heredoc = m.group(1)
        if not line or line.startswith("#") or (not current and STRUCTURE.match(line)):
            continue
        current.append(no)
        if not re.search(r"(\\|\||&&|\|\|)$", line):
            groups.append(current)
            current = []
    return groups
