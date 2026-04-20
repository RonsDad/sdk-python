"""ubuntu_desktop — drive a containerized Ubuntu XFCE desktop over VNC.

This is the ONE net-new custom tool in the superagent. It mirrors the action
surface of ``strands_tools.use_computer`` but talks natively to a Docker
container running ``accetto/ubuntu-vnc-xfce-g3`` (MIT-licensed FOSS VNC/XFCE
Ubuntu image) via the VNC wire protocol (mouse/keyboard/screenshot) plus
``docker exec`` for app lifecycle and display queries.

Requires (runtime):
  - Docker on the host with a container named ``container`` (default
    ``superagent-ubuntu``) running ``accetto/ubuntu-vnc-xfce-g3``
    and publishing the VNC port (default 5901) to the host.
  - Python package ``vncdotool`` for the VNC wire protocol (BSD/MIT FOSS).
  - ``pytesseract`` + ``Pillow`` for ``analyze_screen`` OCR (same deps
    ``use_computer`` relies on for its OCR action).

This tool is implemented with the current ``@tool`` decorator
(``strands.tools.decorator.tool`` via ``from strands import tool``) and returns
the standard Strands ``ToolResult`` dict shape.
"""

from __future__ import annotations

import base64
import logging
import os
import shlex
import subprocess
import tempfile
import time
from typing import Any, Literal

from strands import tool

logger = logging.getLogger(__name__)

Action = Literal[
    "mouse_position",
    "move_mouse",
    "click",
    "drag",
    "scroll",
    "type",
    "key_press",
    "key_hold",
    "hotkey",
    "screen_size",
    "screenshot",
    "analyze_screen",
    "open_app",
    "close_app",
]

_LAST_POSITION: dict[str, tuple[int, int]] = {}


def _docker_exec(container: str, argv: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Run a command inside the named container and return (rc, stdout, stderr)."""
    cmd = ["docker", "exec", container, *argv]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _vnc_client(host: str, port: int, password: str | None):
    """Open a vncdotool API client. Imported lazily so the tool stays importable
    even when ``vncdotool`` is not installed — we only require it at call time."""
    from vncdotool import api  # type: ignore

    server = f"{host}::{port}"
    if password:
        return api.connect(server, password=password)
    return api.connect(server)


def _err(tool_use_id: str, message: str) -> dict[str, Any]:
    return {
        "toolUseId": tool_use_id,
        "status": "error",
        "content": [{"text": message}],
    }


def _ok(tool_use_id: str, text: str, extra: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"text": text}]
    if extra:
        content.extend(extra)
    return {"toolUseId": tool_use_id, "status": "success", "content": content}


@tool
def ubuntu_desktop(
    action: Action,
    container: str = "superagent-ubuntu",
    vnc_host: str = "127.0.0.1",
    vnc_port: int = 5901,
    vnc_password: str | None = None,
    x: int | None = None,
    y: int | None = None,
    x2: int | None = None,
    y2: int | None = None,
    text: str | None = None,
    keys: list[str] | None = None,
    button: Literal["left", "middle", "right"] = "left",
    duration_ms: int = 0,
    scroll_direction: Literal["up", "down"] = "down",
    scroll_amount: int = 3,
    app: str | None = None,
    pattern: str | None = None,
    send_screenshot: bool = False,
) -> dict[str, Any]:
    """Drive a containerized Ubuntu desktop over VNC and docker exec.

    Args:
        action: One of mouse_position, move_mouse, click, drag, scroll, type,
            key_press, key_hold, hotkey, screen_size, screenshot, analyze_screen,
            open_app, close_app.
        container: Docker container name (default 'superagent-ubuntu').
        vnc_host: Host/IP where the container's VNC port is published.
        vnc_port: TCP port where VNC is published on the host (default 5901).
        vnc_password: VNC password if the container was started with one.
        x, y: Target coordinates for pointer actions.
        x2, y2: Secondary coordinates for drag end.
        text: Text for the 'type' action.
        keys: Key list for 'key_press' / 'key_hold' / 'hotkey' actions
            (vncdotool key names, e.g. ["ctrl", "alt", "t"]).
        button: Mouse button for click/drag.
        duration_ms: Hold duration for key_hold (ms).
        scroll_direction: 'up' or 'down'.
        scroll_amount: Number of scroll ticks.
        app: Command line to launch with open_app.
        pattern: Process-match pattern for close_app (pkill -f).
        send_screenshot: If True, include a PNG image in the returned content
            for screenshot and analyze_screen actions.

    Returns:
        Strands ToolResult dict: {"toolUseId", "status", "content": [...]}.
    """
    tool_use_id = "ubuntu_desktop"

    try:
        # --- docker exec branch ---
        if action == "screen_size":
            rc, out, err = _docker_exec(container, ["xdpyinfo"], timeout=10)
            if rc != 0:
                return _err(tool_use_id, f"xdpyinfo failed: {err.strip()}")
            for line in out.splitlines():
                if "dimensions" in line:
                    return _ok(tool_use_id, line.strip())
            return _err(tool_use_id, "dimensions not found in xdpyinfo output")

        if action == "open_app":
            if not app:
                return _err(tool_use_id, "'app' is required for open_app")
            # detach the child so the exec returns immediately
            argv = ["bash", "-lc", f"setsid nohup {app} >/dev/null 2>&1 & echo $!"]
            rc, out, err = _docker_exec(container, argv, timeout=10)
            if rc != 0:
                return _err(tool_use_id, f"open_app failed: {err.strip()}")
            return _ok(tool_use_id, f"started pid={out.strip()} app={app!r}")

        if action == "close_app":
            if not pattern:
                return _err(tool_use_id, "'pattern' is required for close_app")
            rc, _, err = _docker_exec(container, ["pkill", "-f", pattern], timeout=10)
            return _ok(tool_use_id, f"pkill -f {pattern!r} rc={rc}")

        # --- VNC branch (everything else) ---
        client = _vnc_client(vnc_host, vnc_port, vnc_password)
        try:
            if action == "mouse_position":
                pos = _LAST_POSITION.get(container, (0, 0))
                return _ok(tool_use_id, f"x={pos[0]} y={pos[1]} (last sent; VNC has no readback)")

            if action == "move_mouse":
                if x is None or y is None:
                    return _err(tool_use_id, "x and y are required for move_mouse")
                client.mouseMove(x, y)
                _LAST_POSITION[container] = (x, y)
                return _ok(tool_use_id, f"mouse moved to ({x},{y})")

            if action == "click":
                if x is not None and y is not None:
                    client.mouseMove(x, y)
                    _LAST_POSITION[container] = (x, y)
                btn = {"left": 1, "middle": 2, "right": 3}[button]
                client.mousePress(btn)
                return _ok(tool_use_id, f"clicked {button} at {_LAST_POSITION.get(container)}")

            if action == "drag":
                if None in (x, y, x2, y2):
                    return _err(tool_use_id, "x, y, x2, y2 are required for drag")
                btn = {"left": 1, "middle": 2, "right": 3}[button]
                client.mouseMove(x, y)  # type: ignore[arg-type]
                client.mouseDown(btn)
                client.mouseMove(x2, y2)  # type: ignore[arg-type]
                client.mouseUp(btn)
                _LAST_POSITION[container] = (x2, y2)  # type: ignore[assignment]
                return _ok(tool_use_id, f"dragged {button} ({x},{y}) -> ({x2},{y2})")

            if action == "scroll":
                # VNC wheel: button 4 = up, button 5 = down
                btn = 4 if scroll_direction == "up" else 5
                for _ in range(max(1, scroll_amount)):
                    client.mousePress(btn)
                return _ok(tool_use_id, f"scrolled {scroll_direction} x{scroll_amount}")

            if action == "type":
                if text is None:
                    return _err(tool_use_id, "'text' is required for type")
                for ch in text:
                    client.keyPress(ch)
                return _ok(tool_use_id, f"typed {len(text)} chars")

            if action == "key_press":
                if not keys:
                    return _err(tool_use_id, "'keys' is required for key_press")
                for k in keys:
                    client.keyPress(k)
                return _ok(tool_use_id, f"pressed keys={keys}")

            if action == "key_hold":
                if not keys or duration_ms <= 0:
                    return _err(tool_use_id, "'keys' and duration_ms>0 required for key_hold")
                for k in keys:
                    client.keyDown(k)
                time.sleep(duration_ms / 1000.0)
                for k in reversed(keys):
                    client.keyUp(k)
                return _ok(tool_use_id, f"held keys={keys} for {duration_ms}ms")

            if action == "hotkey":
                if not keys:
                    return _err(tool_use_id, "'keys' is required for hotkey")
                for k in keys:
                    client.keyDown(k)
                for k in reversed(keys):
                    client.keyUp(k)
                return _ok(tool_use_id, f"hotkey={keys}")

            if action == "screenshot":
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    tmp_path = tf.name
                try:
                    client.captureScreen(tmp_path)
                    extras: list[dict[str, Any]] | None = None
                    if send_screenshot:
                        with open(tmp_path, "rb") as fh:
                            data = fh.read()
                        extras = [{
                            "image": {
                                "format": "png",
                                "source": {"bytes": base64.b64encode(data).decode("ascii")},
                            }
                        }]
                    return _ok(tool_use_id, f"screenshot captured ({os.path.getsize(tmp_path)} bytes)", extras)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

            if action == "analyze_screen":
                import pytesseract  # lazy
                from PIL import Image  # lazy

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    tmp_path = tf.name
                try:
                    client.captureScreen(tmp_path)
                    img = Image.open(tmp_path)
                    text_ocr = pytesseract.image_to_string(img)
                    extras = None
                    if send_screenshot:
                        with open(tmp_path, "rb") as fh:
                            data = fh.read()
                        extras = [{
                            "image": {
                                "format": "png",
                                "source": {"bytes": base64.b64encode(data).decode("ascii")},
                            }
                        }]
                    return _ok(tool_use_id, text_ocr, extras)
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

            return _err(tool_use_id, f"unknown action: {action}")
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    except subprocess.TimeoutExpired as e:
        return _err(tool_use_id, f"timeout: {e}")
    except FileNotFoundError as e:
        return _err(tool_use_id, f"docker or dependency not found: {e}")
    except Exception as e:  # noqa: BLE001 - tool must never raise
        logger.exception("ubuntu_desktop failure")
        return _err(tool_use_id, f"{type(e).__name__}: {e}")


__all__ = ["ubuntu_desktop"]
