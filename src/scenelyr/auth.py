"""Authentication boundary. Status is queried without opening credential files."""
import subprocess
import tomllib
from pathlib import Path
from typing import Protocol


class AuthAdapter(Protocol):
    def account(self) -> dict: ...
    def start_login(self) -> dict: ...


class LocalAuth:
    def account(self) -> dict:
        model = effort = None
        try:
            with (Path.home() / '.codex' / 'config.toml').open('rb') as config_file:
                config = tomllib.load(config_file)
                model = config.get('model')
                effort = config.get('model_reasoning_effort')
        except (OSError, tomllib.TOMLDecodeError):
            pass
        codex = Path('/Applications/ChatGPT.app/Contents/Resources/codex')
        if codex.is_file():
            try:
                status = subprocess.run([str(codex), 'login', 'status'], capture_output=True,
                                        text=True, timeout=5, check=False)
                if status.returncode == 0 and 'Logged in using ChatGPT' in (status.stdout + status.stderr):
                    return {'mode': 'codex', 'label': 'Codex connected', 'loginAvailable': False,
                            'message': 'Using the ChatGPT account already signed in to Codex.',
                            'model': model, 'reasoningEffort': effort,
                            'integration': 'Natural-language requests run through Codex App Server, which can call the configured SceneLyr MCP tools.'}
            except (OSError, subprocess.TimeoutExpired):
                pass
        return {'mode': 'local', 'label': 'Local workspace', 'loginAvailable': False,
                'message': 'Images and edits stay on this computer. No account is required.',
                'integration': 'Codex App Server requires an explicitly configured host adapter.'}

    def start_login(self) -> dict:
        raise ValueError('Managed sign-in is not enabled. Continue in local mode.')


auth: AuthAdapter = LocalAuth()
