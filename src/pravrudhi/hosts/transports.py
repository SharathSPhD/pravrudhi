"""Ways to reach a machine. Interchangeable by construction, so none is load-bearing."""

from __future__ import annotations

import shlex
import shutil
import subprocess

from pravrudhi.hosts.base import HostSpec


class LocalTransport:
    """This machine. The default, and the only one a single-machine install needs."""

    name = "local"

    def __init__(self, spec: HostSpec | None = None) -> None:
        self.spec = spec or HostSpec(name="local")

    def available(self) -> bool:
        return True

    def run(self, command: str, timeout_s: int = 300) -> tuple[int, str, str]:
        try:
            p = subprocess.run(["bash", "-lc", command], capture_output=True, text=True, timeout=timeout_s)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            return 124, (e.stdout or "") if isinstance(e.stdout, str) else "", f"timeout after {timeout_s}s"


class SshTransport:
    """Another machine over plain SSH: no agent, no daemon, nothing to install first."""

    name = "ssh"

    def __init__(self, spec: HostSpec) -> None:
        self.spec = spec

    @property
    def target(self) -> str:
        return f"{self.spec.user}@{self.spec.address}" if self.spec.user else self.spec.address

    def available(self) -> bool:
        if shutil.which("ssh") is None or not self.spec.address:
            return False
        code, _, _ = self.run("true", timeout_s=25)
        return code == 0

    def run(self, command: str, timeout_s: int = 300) -> tuple[int, str, str]:
        cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"ConnectTimeout={min(20, timeout_s)}",
            # the target is validated on HostSpec construction, and "--" stops option parsing regardless
            "--", self.target,
            # a login shell, so PATH matches what a person would see: version managers put agent CLIs there and a
            # non-login shell would report a host as lacking tools it has
            f"bash -lc {shlex.quote(command)}",
        ]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"ssh timeout after {timeout_s}s"


class OrcaTransport:
    """A machine Orca already manages. Orca supplies the session machinery; placement stays Pravrudhi's."""

    name = "orca"

    def __init__(self, spec: HostSpec) -> None:
        self.spec = spec

    def available(self) -> bool:
        if shutil.which("orca-ide") is None:
            return False
        p = subprocess.run(["orca-ide", "status"], capture_output=True, text=True, timeout=60)
        return "runtimeReachable: true" in p.stdout

    def run(self, command: str, timeout_s: int = 300) -> tuple[int, str, str]:
        args = ["orca-ide", "host", "run", "--host", self.spec.orca_host_id or "local", "--command", command, "--json"]
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout_s)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"orca timeout after {timeout_s}s"


def transport_for(spec: HostSpec) -> LocalTransport | SshTransport | OrcaTransport:
    if spec.transport == "local":
        return LocalTransport(spec)
    if spec.transport == "ssh":
        return SshTransport(spec)
    return OrcaTransport(spec)
