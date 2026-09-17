"""CUTI Ops Control Deck — Unified Terminal User Interface (TUI).

Provides a centralized dashboard to supervise FastAPI, Vite, daily pipeline,
workers, and offline verification without loose .bat scripts.
"""

from __future__ import annotations

import argparse
import datetime
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# Fallback Guard: check for textual library
try:
    from rich.text import Text
    from textual import work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Grid, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.widgets import (
        Button,
        Footer,
        Header,
        Label,
        RichLog,
        Static,
        TabbedContent,
        TabPane,
    )
    TEXTUAL_AVAILABLE = True
except ImportError:
    Text = None
    TEXTUAL_AVAILABLE = False
    CutiControlApp = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a local TCP port is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((host, port)) == 0


def kill_process_tree(pid: int) -> None:
    """Safely terminate a process and all its child processes."""
    try:
        import psutil
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            parent.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        gone, alive = psutil.wait_procs(children + [parent], timeout=2.0)
        for p in alive:
            try:
                p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # Fallback if psutil is not available
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass


def setup_windows_console() -> None:
    """Ensure Windows console is configured for UTF-8."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        if hasattr(sys.stderr, "reconfigure"):
            try:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def copy_to_system_clipboard(text: str) -> bool:
    """Copy text to system clipboard with full Unicode support (Win32 CF_UNICODETEXT / UTF-16LE)."""
    if os.name == "nt":
        # 1. Native Win32 API clipboard allocation (CF_UNICODETEXT)
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            GMEM_MOVEABLE = 0x0002
            CF_UNICODETEXT = 13

            data = text.encode("utf-16le") + b"\x00\x00"

            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            user32.SetClipboardData.restype = wintypes.HANDLE
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL

            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                    if h_mem:
                        ptr = kernel32.GlobalLock(h_mem)
                        if ptr:
                            ctypes.memmove(ptr, data, len(data))
                            kernel32.GlobalUnlock(h_mem)
                            user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                            return True
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

        # 2. Fallback to Windows clip.exe with UTF-16LE encoding (clip.exe decodes UTF-16LE correctly)
        try:
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=False)
            return True
        except Exception:
            pass

    return False


@dataclass
class SystemMetrics:
    """Snapshot of database and port metrics."""
    lots_count: int = 0
    pending_images: int = 0
    api_active: bool = False
    vite_active: bool = False


def query_metrics(db_path: Optional[Path] = None) -> SystemMetrics:
    """Query current system metrics non-destructively."""
    db_file = db_path or (PROJECT_ROOT / "cuti.db")
    lots = 0
    pending = 0
    if db_file.is_file():
        try:
            import sqlite3
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM lots")
                row = cursor.fetchone()
                if row:
                    lots = int(row[0])
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("SELECT COUNT(*) FROM lot_images WHERE local_path IS NULL")
                row = cursor.fetchone()
                if row:
                    pending = int(row[0])
            except sqlite3.OperationalError:
                pass
            conn.close()
        except Exception:
            pass

    return SystemMetrics(
        lots_count=lots,
        pending_images=pending,
        api_active=is_port_open(8000),
        vite_active=is_port_open(5173),
    )


class SubprocessTask:
    """A managed background subprocess streaming output via queue."""

    def __init__(
        self,
        name: str,
        tag: str,
        cmd: list[str],
        cwd: Path,
        env: Optional[dict[str, str]] = None,
        on_line: Optional[Callable[[str, str], None]] = None,
        on_exit: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        self.name = name
        self.tag = tag
        self.cmd = cmd
        self.cwd = cwd
        self.env = dict(env) if env is not None else dict(os.environ)
        self.env.setdefault("PYTHONIOENCODING", "utf-8")
        self.env.setdefault("PYTHONUTF8", "1")
        self.on_line = on_line
        self.on_exit = on_exit
        self.process: Optional[subprocess.Popen[str]] = None
        self._thread: Optional[threading.Thread] = None
        self._stopped = False

    def start(self) -> None:
        """Start the process and launch the reader thread."""
        self.process = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._thread.start()

    def _reader_loop(self) -> None:
        if not self.process or not self.process.stdout:
            return
        try:
            for line in iter(self.process.stdout.readline, ""):
                if self.on_line and line:
                    self.on_line(self.tag, line.rstrip("\r\n"))
        except Exception:
            pass
        finally:
            if self.process and self.process.stdout:
                try:
                    self.process.stdout.close()
                except Exception:
                    pass
            if self.process:
                code = self.process.wait()
                if self.on_exit and not self._stopped:
                    self.on_exit(self.tag, code)

    def stop(self) -> None:
        """Stop the process gracefully."""
        self._stopped = True
        if self.process and self.process.poll() is None:
            kill_process_tree(self.process.pid)


if TEXTUAL_AVAILABLE:

    class CutiControlApp(App[None]):
        """CUTI Ops Control Deck main Textual application."""

        CSS = """
        Screen {
            background: #0b0f19;
            color: #f1f5f9;
        }

        #metrics-bar {
            height: 3;
            background: #111827;
            border-bottom: solid #1e293b;
            padding: 0 1;
        }

        .metric-card {
            width: 1fr;
            height: 100%;
            content-align: center middle;
            text-style: bold;
            border: round #334155;
            margin-right: 1;
            background: #1e293b;
            color: #e2e8f0;
        }

        #sidebar {
            width: 36;
            background: #0f172a;
            border-right: solid #1e293b;
            padding: 1;
        }

        #sidebar-title {
            text-align: center;
            text-style: bold;
            color: #38bdf8;
            margin-bottom: 1;
        }

        #button-grid {
            layout: grid;
            grid-size: 2;
            grid-gutter: 1;
            margin-bottom: 1;
        }

        .action-btn {
            width: 100%;
            height: 3;
            min-width: 12;
        }

        #btn_quit {
            column-span: 2;
        }

        #main-area {
            width: 1fr;
            height: 1fr;
        }

        TabbedContent {
            height: 1fr;
        }

        TabPane {
            height: 1fr;
            padding: 0;
        }

        RichLog {
            height: 1fr;
            background: #030712;
            border: none;
            scrollbar-color: #38bdf8 #111827;
        }
        """

        BINDINGS = [
            Binding("d", "toggle_dev", "Dev Server", show=True),
            Binding("p", "run_pipeline", "Daily Pipeline", show=True),
            Binding("s", "run_settle", "Settle", show=True),
            Binding("i", "run_image_worker", "Tải ảnh", show=True),
            Binding("r", "run_refine", "Refine", show=True),
            Binding("x", "stop_batch_task", "Dừng tác vụ", show=True),
            Binding("c", "clear_active_log", "Xóa log", show=True),
            Binding("y", "copy_active_log", "Copy log", show=True),
            Binding("w", "toggle_wrap", "Word-wrap", show=True),
            Binding("space", "toggle_scroll", "Auto-scroll", show=True),
            Binding("q", "quit_all", "Thoát", show=True),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.running_tasks: dict[str, SubprocessTask] = {}
            self.current_batch_task: Optional[SubprocessTask] = None
            self.dev_active = False
            self.batch_running = False
            self.log_buffers: dict[str, list[str]] = {
                "tab_all": [],
                "tab_api": [],
                "tab_vite": [],
                "tab_pipe": [],
            }

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="metrics-bar"):
                yield Static("API :8000: [red]OFFLINE[/red]", id="card_api", classes="metric-card")
                yield Static("Vite :5173: [red]OFFLINE[/red]", id="card_vite", classes="metric-card")
                yield Static("Pipeline: [dim]IDLE[/dim]", id="card_pipe", classes="metric-card")
                yield Static("DB Lots: 0 | Queue: 0", id="card_db", classes="metric-card")

            with Horizontal(id="main-area"):
                with Vertical(id="sidebar"):
                    yield Static("⚡ [bold cyan]ĐIỀU KHIỂN[/bold cyan]", id="sidebar-title")
                    with Grid(id="button-grid"):
                        yield Button("Dev Server [d]", id="btn_dev", variant="primary", classes="action-btn")
                        yield Button("Daily [p]", id="btn_pipeline", variant="success", classes="action-btn")
                        yield Button("Settle [s]", id="btn_settle", classes="action-btn")
                        yield Button("Tải ảnh [i]", id="btn_worker", classes="action-btn")
                        yield Button("Refine [r]", id="btn_refine", classes="action-btn")
                        yield Button("Dừng [x]", id="btn_stop", variant="warning", classes="action-btn", disabled=True)
                        yield Button("Xóa log [c]", id="btn_clear", classes="action-btn")
                        yield Button("Copy log [y]", id="btn_copy", classes="action-btn")
                        yield Button("Thoát [q]", id="btn_quit", variant="error", classes="action-btn")

                with TabbedContent(id="tabs"):
                    with TabPane("Tất cả Log", id="tab_all"):
                        yield RichLog(id="log_all", max_lines=2000, highlight=True, markup=True, wrap=True)
                    with TabPane("FastAPI (:8000)", id="tab_api"):
                        yield RichLog(id="log_api", max_lines=2000, highlight=True, markup=True, wrap=True)
                    with TabPane("Vite (:5173)", id="tab_vite"):
                        yield RichLog(id="log_vite", max_lines=2000, highlight=True, markup=True, wrap=True)
                    with TabPane("Pipeline & Tasks", id="tab_pipe"):
                        yield RichLog(id="log_pipe", max_lines=2000, highlight=True, markup=True, wrap=True)

            yield Footer()

        def on_mount(self) -> None:
            """Initialize timers and greetings on mount."""
            self.set_interval(3.0, self.update_system_metrics)
            self.update_system_metrics()
            self._log("SYSTEM", "[bold green]CUTI Ops Control Deck khởi động thành công.[/bold green]")
            self._log("SYSTEM", "Nhấn [bold cyan][d][/bold cyan] để bật Dev Server, [bold cyan][p][/bold cyan] để chạy Daily Pipeline, [bold cyan][q][/bold cyan] để thoát an toàn.")

        def update_system_metrics(self) -> None:
            """Poll metrics and update top bar."""
            metrics = query_metrics()
            try:
                card_api = self.query_one("#card_api", Static)
                api_status = "[bold green]ONLINE :8000[/bold green]" if metrics.api_active else "[dim red]OFFLINE[/dim red]"
                card_api.update(f"FastAPI: {api_status}")

                card_vite = self.query_one("#card_vite", Static)
                vite_status = "[bold green]ONLINE :5173[/bold green]" if metrics.vite_active else "[dim red]OFFLINE[/dim red]"
                card_vite.update(f"Vite: {vite_status}")

                card_db = self.query_one("#card_db", Static)
                card_db.update(f"DB: [bold cyan]{metrics.lots_count:,}[/bold cyan] lots | Queue: [bold yellow]{metrics.pending_images}[/bold yellow]")
            except Exception:
                pass

        def _log(self, tag: str, message: str) -> None:
            """Thread-safe log routing to tabs with colors and buffer caching."""
            now = datetime.datetime.now().strftime("%H:%M:%S")
            color_map = {
                "SYSTEM": "bold white",
                "API": "cyan",
                "Vite": "magenta",
                "Pipeline": "yellow",
                "Settle": "blue",
                "Worker": "green",
                "Refine": "cyan",
            }
            color = color_map.get(tag, "white")

            if Text is not None:
                prefix = Text.from_markup(f"[dim]{now}[/dim] [{color}][{tag}][/{color}] ")
                if "\x1b" in message:
                    content_text = Text.from_ansi(message)
                elif "[" in message and "]" in message:
                    try:
                        content_text = Text.from_markup(message)
                    except Exception:
                        content_text = Text(message)
                else:
                    content_text = Text(message)
                formatted = prefix + content_text
                plain_msg = content_text.plain
            else:
                formatted = f"[dim]{now}[/dim] [{color}][{tag}][/{color}] {message}"
                plain_msg = re.sub(r"\[/?[a-zA-Z0-9_\#\s]+\]", "", message)
                plain_msg = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", plain_msg)

            plain_line = f"[{now}] [{tag}] {plain_msg}"

            buf_all = self.log_buffers["tab_all"]
            buf_all.append(plain_line)
            if len(buf_all) > 2000:
                del buf_all[:-2000]

            try:
                log_all = self.query_one("#log_all", RichLog)
                log_all.write(formatted)
            except Exception:
                pass

            target_log_id = None
            target_tab_key = None
            if tag == "API":
                target_log_id = "#log_api"
                target_tab_key = "tab_api"
            elif tag == "Vite":
                target_log_id = "#log_vite"
                target_tab_key = "tab_vite"
            elif tag in {"Pipeline", "Settle", "Worker", "Refine"}:
                target_log_id = "#log_pipe"
                target_tab_key = "tab_pipe"

            if target_tab_key:
                buf_target = self.log_buffers[target_tab_key]
                buf_target.append(plain_line)
                if len(buf_target) > 2000:
                    del buf_target[:-2000]

            if target_log_id:
                try:
                    log_target = self.query_one(target_log_id, RichLog)
                    log_target.write(formatted)
                except Exception:
                    pass

        def _on_subprocess_line(self, tag: str, line: str) -> None:
            self.call_from_thread(self._log, tag, line)

        def _on_subprocess_exit(self, tag: str, code: int) -> None:
            status_text = f"[bold green]kết thúc thành công (code 0)[/bold green]" if code == 0 else f"[bold red]thoát với mã lỗi {code}[/bold red]"
            self.call_from_thread(self._log, tag, f"Tiến trình {tag} {status_text}.")
            if tag in {"Pipeline", "Settle", "Worker", "Refine"}:
                self.call_from_thread(self._finish_batch_task, tag, code)
            elif tag in {"API", "Vite"}:
                self.call_from_thread(self.update_system_metrics)

        def _finish_batch_task(self, tag: str, code: int) -> None:
            self.batch_running = False
            self.current_batch_task = None
            card_pipe = self.query_one("#card_pipe", Static)
            if code == 0:
                card_pipe.update(f"{tag}: [bold green]XONG (0)[/bold green]")
            elif code == 130:
                card_pipe.update(f"{tag}: [bold yellow]ĐÃ DỪNG[/bold yellow]")
            else:
                card_pipe.update(f"{tag}: [bold red]LỖI ({code})[/bold red]")
            btn_pipe = self.query_one("#btn_pipeline", Button)
            btn_pipe.disabled = False
            btn_pipe.label = "Daily [p]"

            btn_stop = self.query_one("#btn_stop", Button)
            btn_stop.disabled = True

        def action_toggle_dev(self) -> None:
            """Toggle FastAPI and Vite dev servers."""
            btn = self.query_one("#btn_dev", Button)
            if self.dev_active:
                self._log("SYSTEM", "Đang dừng các máy chủ phát triển (FastAPI & Vite)...")
                if "api" in self.running_tasks:
                    self.running_tasks["api"].stop()
                    del self.running_tasks["api"]
                if "vite" in self.running_tasks:
                    self.running_tasks["vite"].stop()
                    del self.running_tasks["vite"]
                self.dev_active = False
                btn.variant = "primary"
                btn.label = "Dev Server [d]"
                self.update_system_metrics()
            else:
                self._log("SYSTEM", "Đang khởi động FastAPI (:8000) và Vite (:5173)...")
                env = dict(os.environ)
                env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

                api_task = SubprocessTask(
                    name="FastAPI Server",
                    tag="API",
                    cmd=[sys.executable, "-m", "cuti.server", "8000"],
                    cwd=PROJECT_ROOT,
                    env=env,
                    on_line=self._on_subprocess_line,
                    on_exit=self._on_subprocess_exit,
                )
                api_task.start()
                self.running_tasks["api"] = api_task

                npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
                vite_task = SubprocessTask(
                    name="Vite UI Dev",
                    tag="Vite",
                    cmd=[npm_cmd, "run", "dev:ui"],
                    cwd=FRONTEND_DIR,
                    env=env,
                    on_line=self._on_subprocess_line,
                    on_exit=self._on_subprocess_exit,
                )
                vite_task.start()
                self.running_tasks["vite"] = vite_task

                self.dev_active = True
                btn.variant = "error"
                btn.label = "Dừng Dev [d]"
                self.update_system_metrics()

        def _start_batch_job(self, name: str, tag: str, cmd: list[str]) -> None:
            if self.batch_running:
                self._log("SYSTEM", f"[bold yellow]Cảnh báo:[/bold yellow] Một tác vụ đang chạy, vui lòng đợi hoàn thành hoặc bấm 'Dừng [x]'!")
                try:
                    self.notify("Một tác vụ đang chạy. Bấm 'Dừng [x]' nếu muốn hủy.", title="Cảnh báo", severity="warning")
                except Exception:
                    pass
                return
            self.batch_running = True
            card_pipe = self.query_one("#card_pipe", Static)
            card_pipe.update(f"{tag}: [bold yellow]RUNNING...[/bold yellow]")

            btn_pipe = self.query_one("#btn_pipeline", Button)
            btn_pipe.disabled = True
            btn_pipe.label = "Đang chạy..."

            btn_stop = self.query_one("#btn_stop", Button)
            btn_stop.disabled = False

            self._log("SYSTEM", f"Bắt đầu tác vụ: [bold]{name}[/bold]")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(PROJECT_ROOT / "src") + os.pathsep + str(PROJECT_ROOT / "scripts") + os.pathsep + env.get("PYTHONPATH", "")

            task = SubprocessTask(
                name=name,
                tag=tag,
                cmd=cmd,
                cwd=PROJECT_ROOT,
                env=env,
                on_line=self._on_subprocess_line,
                on_exit=self._on_subprocess_exit,
            )
            self.current_batch_task = task
            self.running_tasks[tag.lower()] = task
            task.start()

        def action_run_pipeline(self) -> None:
            """Run Daily Pipeline."""
            self._start_batch_job(
                name="Daily Pipeline (Crawl, Settle, Images, Gemini)",
                tag="Pipeline",
                cmd=[sys.executable, "scripts/run_daily.py"],
            )

        def action_run_settle(self) -> None:
            """Run Settle task."""
            self._start_batch_job(
                name="Settle Lots",
                tag="Settle",
                cmd=[sys.executable, "-m", "cuti.cli", "settle"],
            )

        def action_run_image_worker(self) -> None:
            """Run Image Worker until empty."""
            self._start_batch_job(
                name="Tải ảnh còn thiếu",
                tag="Worker",
                cmd=[sys.executable, "scripts/run_image_worker.py", "--until-empty"],
            )

        def action_run_refine(self) -> None:
            """Run Gemini Refinement."""
            self._start_batch_job(
                name="Gemini Refine",
                tag="Refine",
                cmd=[sys.executable, "scripts/run_llm_refine.py"],
            )

        def action_stop_batch_task(self) -> None:
            """Stop the currently running batch task."""
            if not self.batch_running or not self.current_batch_task:
                try:
                    self.notify("Hiện không có tác vụ nào đang chạy.", title="Dừng tác vụ", severity="warning")
                except Exception:
                    pass
                return

            self._log("SYSTEM", "[bold yellow]Đang yêu cầu dừng tác vụ hiện tại...[/bold yellow]")
            task = self.current_batch_task
            self.current_batch_task = None
            task.stop()
            self._finish_batch_task(task.tag, 130)

        def action_clear_active_log(self) -> None:
            """Clear log of currently active tab."""
            tabs = self.query_one("#tabs", TabbedContent)
            active_pane = tabs.active or "tab_all"
            log_id_map = {
                "tab_all": "#log_all",
                "tab_api": "#log_api",
                "tab_vite": "#log_vite",
                "tab_pipe": "#log_pipe",
            }
            log_id = log_id_map.get(active_pane)
            if log_id:
                try:
                    rich_log = self.query_one(log_id, RichLog)
                    rich_log.clear()
                    if active_pane in self.log_buffers:
                        self.log_buffers[active_pane].clear()
                    self._log("SYSTEM", f"Đã xóa log {active_pane}.")
                except Exception:
                    pass

        def action_copy_active_log(self) -> None:
            """Copy plain-text logs of active tab to system clipboard."""
            tabs = self.query_one("#tabs", TabbedContent)
            active_pane = tabs.active or "tab_all"
            lines = self.log_buffers.get(active_pane, [])
            if not lines:
                try:
                    self.notify("Tab hiện tại chưa có log để copy.", title="Copy Log", severity="warning")
                except Exception:
                    pass
                return

            text_to_copy = "\n".join(lines)
            copied = False
            try:
                self.copy_to_clipboard(text_to_copy)
                copied = True
            except Exception:
                pass

            if copy_to_system_clipboard(text_to_copy):
                copied = True

            if copied:
                try:
                    self.notify(f"Đã copy {len(lines)} dòng log từ {active_pane} vào clipboard!", title="Copy Log", severity="information")
                except Exception:
                    pass
                self._log("SYSTEM", f"[bold green]Đã copy {len(lines)} dòng log ({active_pane}) vào clipboard.[/bold green]")
            else:
                try:
                    self.notify("Không thể truy cập clipboard.", title="Copy Log", severity="error")
                except Exception:
                    pass

        def action_toggle_scroll(self) -> None:
            """Toggle auto-scrolling on active tab."""
            tabs = self.query_one("#tabs", TabbedContent)
            active_pane = tabs.active
            log_id_map = {
                "tab_all": "#log_all",
                "tab_api": "#log_api",
                "tab_vite": "#log_vite",
                "tab_pipe": "#log_pipe",
            }
            log_id = log_id_map.get(active_pane)
            if log_id:
                try:
                    rich_log = self.query_one(log_id, RichLog)
                    rich_log.auto_scroll = not rich_log.auto_scroll
                    state = "BẬT" if rich_log.auto_scroll else "TẮT"
                    self._log("SYSTEM", f"Auto-scroll trên {active_pane}: {state}")
                except Exception:
                    pass

        def action_toggle_wrap(self) -> None:
            """Toggle word-wrap on active tab."""
            tabs = self.query_one("#tabs", TabbedContent)
            active_pane = tabs.active or "tab_all"
            log_id_map = {
                "tab_all": "#log_all",
                "tab_api": "#log_api",
                "tab_vite": "#log_vite",
                "tab_pipe": "#log_pipe",
            }
            log_id = log_id_map.get(active_pane)
            if log_id:
                try:
                    rich_log = self.query_one(log_id, RichLog)
                    rich_log.wrap = not rich_log.wrap
                    state = "BẬT" if rich_log.wrap else "TẮT"
                    try:
                        self.notify(f"Word-wrap trên {active_pane}: {state}", title="Word-wrap")
                    except Exception:
                        pass
                    self._log("SYSTEM", f"Word-wrap trên {active_pane}: {state}")
                except Exception:
                    pass

        def action_quit_all(self) -> None:
            """Graceful shutdown protocol."""
            self._log("SYSTEM", "[bold yellow]Đang dọn dẹp và dừng mọi tiến trình con...[/bold yellow]")
            for name, task in list(self.running_tasks.items()):
                task.stop()
            self.running_tasks.clear()
            self.exit()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id
            if button_id == "btn_dev":
                self.action_toggle_dev()
            elif button_id == "btn_pipeline":
                self.action_run_pipeline()
            elif button_id == "btn_settle":
                self.action_run_settle()
            elif button_id == "btn_worker":
                self.action_run_image_worker()
            elif button_id == "btn_refine":
                self.action_run_refine()
            elif button_id == "btn_stop":
                self.action_stop_batch_task()
            elif button_id == "btn_clear":
                self.action_clear_active_log()
            elif button_id == "btn_copy":
                self.action_copy_active_log()
            elif button_id == "btn_quit":
                self.action_quit_all()


def main() -> int:
    setup_windows_console()
    parser = argparse.ArgumentParser(description="CUTI Ops Control Deck (TUI)")
    parser.add_argument("--check", action="store_true", help="Kiểm tra môi trường và thoát")
    args = parser.parse_args()

    if not TEXTUAL_AVAILABLE:
        print(
            "Lỗi: Chưa cài đặt thư viện 'textual'.\n"
            "Vui lòng cài đặt bằng lệnh: pip install -e .[tui] hoặc pip install textual\n",
            file=sys.stderr,
        )
        return 1

    if args.check:
        print("TUI Environment OK: textual is installed and ready.")
        return 0

    app = CutiControlApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
