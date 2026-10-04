"""Authentication boundary. Tokens never cross into the web workspace."""
import subprocess
import threading
import tomllib
from pathlib import Path
from typing import Protocol

from .runtime import find_codex


class AuthAdapter(Protocol):
    def account(self) -> dict: ...
    def start_login(self) -> dict: ...


class LocalAuth:
    """Use Codex's supported ChatGPT login while keeping credentials in Codex."""

    def __init__(self, codex_path: Path | None = None):
        self.codex_path = codex_path or find_codex() or Path('/Applications/ChatGPT.app/Contents/Resources/codex')
        self._login: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def account(self) -> dict:
        model = effort = None
        try:
            with (Path.home() / '.codex' / 'config.toml').open('rb') as config_file:
                config = tomllib.load(config_file)
                model = config.get('model')
                effort = config.get('model_reasoning_effort')
        except (OSError, tomllib.TOMLDecodeError):
            pass
        codex = self.codex_path
        if codex.is_file():
            try:
                status = subprocess.run([str(codex), 'login', 'status'], capture_output=True,
                                        text=True, timeout=5, check=False)
                if status.returncode == 0 and 'Logged in using ChatGPT' in (status.stdout + status.stderr):
                    return {'mode': 'codex', 'label': 'ChatGPT connected', 'loginAvailable': True,
                            'message': 'Using the ChatGPT account already signed in to Codex.',
                            'model': model, 'reasoningEffort': effort,
                            'planUsage': True, 'usageLabel': 'Using ChatGPT plan',
                            'integration': 'Natural-language requests run through Codex App Server, which can call the configured SceneLyr MCP tools.'}
            except (OSError, subprocess.TimeoutExpired):
                pass
        pending = bool(self._login and self._login.poll() is None)
        return {'mode': 'local', 'label': 'Local workspace', 'loginAvailable': codex.is_file(),
                'loginPending': pending, 'planUsage': False,
                'message': 'Images and edits stay on this computer. No account is required.',
                'integration': ('Continue with ChatGPT to use Codex and the SceneLyr MCP tools.' if codex.is_file()
                                else 'Install the ChatGPT desktop app to enable ChatGPT sign-in.')}

    def start_login(self) -> dict:
        if self.account().get('mode') == 'codex':
            return {'state': 'connected'}
        if not self.codex_path.is_file():
            raise ValueError('ChatGPT sign-in is unavailable because the desktop Codex runtime was not found.')
        with self._lock:
            if self._login and self._login.poll() is None:
                return {'state': 'pending'}
            try:
                self._login = subprocess.Popen(
                    [str(self.codex_path), 'login'], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                )
            except OSError as error:
                raise ValueError('ChatGPT sign-in could not be started.') from error
        return {'state': 'browser_opened'}


auth: AuthAdapter = LocalAuth()
