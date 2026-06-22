"""GradSchool Deploy MCP Server — wraps server deployment operations as MCP tools.

Provides: deploy_file, restart_service, service_status, health_check, view_logs,
          deploy_frontend, deploy_backend
"""

import json
import subprocess
import urllib.request
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

SSH_HOST = "gradschool"
SERVER_IP = "49.233.176.135"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SERVER_BACKEND = "/home/ubuntu/gradschool/backend"
SERVER_FRONTEND = "/home/ubuntu/gradschool/frontend/dist"
SERVICE_NAME = "gradschool"


def _ssh(cmd: str, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a command on the server via SSH."""
    full_cmd = f"ssh {SSH_HOST} {cmd!r}"
    kwargs = {"shell": True}
    if capture:
        kwargs["capture_output"] = True
        kwargs["encoding"] = "utf-8"
    return subprocess.run(full_cmd, **kwargs)


def _ssh_quiet(cmd: str) -> tuple[bool, str]:
    """Run SSH command and return (success, output)."""
    try:
        r = _ssh(cmd)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


async def deploy_file(file_path: str, service_path: str | None = None, restart: bool = True) -> str:
    """Upload a project file to the server.

    Args:
        file_path: Absolute or project-relative path to the local file.
        service_path: Absolute path on the server. Auto-derived from project structure if omitted.
        restart: Whether to restart the service after upload. Default True.
    """
    local = Path(file_path)
    if not local.is_absolute():
        local = PROJECT_ROOT / local
    if not local.exists():
        return f"ERROR: File not found — {local}"

    if service_path:
        remote_path = service_path
    else:
        rel = local.relative_to(PROJECT_ROOT)
        remote_path = f"/home/ubuntu/gradschool/{rel.as_posix()}"

    # scp the file
    r = subprocess.run(
        f'scp "{local.as_posix()}" {SSH_HOST}:"{remote_path}"',
        shell=True, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return f"SCP failed: {r.stderr.strip()}"

    lines = [f"Uploaded {local.name} → {remote_path}"]

    if restart:
        ok, out = _ssh_quiet(f"sudo systemctl restart {SERVICE_NAME}")
        if ok:
            # Wait briefly then check status
            ok2, status = _ssh_quiet(f"systemctl is-active {SERVICE_NAME}")
            lines.append(f"Service restarted — status: {status}")
        else:
            lines.append(f"Restart failed: {out}")

    return "\n".join(lines)


async def restart_service() -> str:
    """Restart the gradschool systemd service on the server."""
    ok, out = _ssh_quiet(f"sudo systemctl restart {SERVICE_NAME} && sleep 2 && systemctl is-active {SERVICE_NAME}")
    if ok:
        return f"Service restarted successfully — active: {out}"
    return f"Restart failed: {out}"


async def service_status() -> str:
    """Show the current status of the gradschool service."""
    ok, out = _ssh_quiet(
        f"sudo systemctl status {SERVICE_NAME} --no-pager -l 2>&1 | head -20"
    )
    return out


async def health_check() -> str:
    """Run a health check against the deployed site."""
    try:
        req = urllib.request.Request(
            f"http://{SERVER_IP}/api/health",
            headers={"Host": "49.233.176.135"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return f"Health OK — status={resp.status}, body={json.dumps(data, ensure_ascii=False)}"
    except Exception as e:
        return f"Health check failed: {e}"


async def view_logs(lines: int = 30) -> str:
    """View recent application logs from the server.

    Args:
        lines: Number of log lines to fetch. Default 30.
    """
    ok, out = _ssh_quiet(
        f"sudo journalctl -u {SERVICE_NAME} -n {lines} --no-pager 2>&1"
    )
    return out or "(no logs)"


async def deploy_frontend() -> str:
    """Build frontend locally and upload to server (no restart needed)."""
    local_dist = FRONTEND_DIR / "dist"
    if not local_dist.exists():
        return "ERROR: frontend/dist does not exist — run 'npm run build' first"

    r = subprocess.run(
        f'rsync -avz --delete "{local_dist.as_posix()}/" {SSH_HOST}:"{SERVER_FRONTEND}/"',
        shell=True, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return f"rsync failed: {r.stderr.strip()}"
    return "Frontend deployed successfully (no restart needed)"


async def deploy_backend(file_filter: str = "*.py") -> str:
    """Deploy all changed Python files from backend/ to server and restart.

    Args:
        file_filter: Glob pattern for files to deploy. Default '*.py'.
    """
    r = subprocess.run(
        f'rsync -avz --include="*/" --include="{file_filter}" --exclude="*" --exclude="__pycache__/" --exclude="*.pyc" --exclude=".venv/" "{BACKEND_DIR.as_posix()}/" {SSH_HOST}:"{SERVER_BACKEND}/"',
        shell=True, capture_output=True, text=True,
    )
    if r.returncode != 0:
        return f"rsync failed: {r.stderr.strip()}"

    # Restart service
    ok, out = _ssh_quiet(f"sudo systemctl restart {SERVICE_NAME} && sleep 2 && systemctl is-active {SERVICE_NAME}")
    status_line = f"Service restarted — active: {out}" if ok else f"Restart warning: {out}"

    uploaded = [line for line in r.stdout.strip().split("\n") if line and not line.endswith("/")]
    return f"Backend deployed ({len(uploaded)} files)\n{status_line}"


# ── MCP server setup ────────────────────────────────────────────────

server = Server("gradschool-deploy")

server._tool_registry = {
    "deploy_file": deploy_file,
    "restart_service": restart_service,
    "service_status": service_status,
    "health_check": health_check,
    "view_logs": view_logs,
    "deploy_frontend": deploy_frontend,
    "deploy_backend": deploy_backend,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="deploy_file",
            description="Upload a single file to the GradSchool server. Auto-derives the remote path from the project structure. Optionally restarts the service.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Local file path (absolute, or relative to project root)",
                    },
                    "service_path": {
                        "type": "string",
                        "description": "Optional: explicit server path override",
                    },
                    "restart": {
                        "type": "boolean",
                        "description": "Whether to restart systemd service after upload (default: true)",
                        "default": True,
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="restart_service",
            description="Restart the gradschool systemd service on the server.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="service_status",
            description="Show the current systemd service status for gradschool.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="health_check",
            description="HTTP health check against the deployed site (GET /api/health).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="view_logs",
            description="View recent gradschool application logs from journalctl.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines (default: 30)",
                        "default": 30,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="deploy_frontend",
            description="Deploy the frontend/dist directory to the server via rsync.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="deploy_backend",
            description="Deploy Python backend files to the server via rsync and restart the service.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_filter": {
                        "type": "string",
                        "description": "Glob pattern to filter files (default: '*.py')",
                        "default": "*.py",
                    },
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    func = server._tool_registry.get(name)
    if not func:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        result = await func(**arguments)
    except Exception as e:
        result = f"Tool error ({name}): {e}"

    return [TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
