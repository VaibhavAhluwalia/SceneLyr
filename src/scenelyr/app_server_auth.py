"""Opt-in host-side adapter contract; no credential-file access or browser tokens.

Not enabled by the web application. The owning host must supply a trusted,
initialized JSON-RPC connection and handle login completion/cancellation.
"""
from collections.abc import Callable
from urllib.parse import urlsplit


class AppServerAuth:
    def __init__(self, request: Callable[[str, dict], dict]):
        self.request = request

    def account(self) -> dict:
        result = self.request('account/read', {'refreshToken': False})
        account = result.get('account') or {}
        # Strict projection: email, tokens, account IDs and unknown fields stay server-side.
        return {'mode': 'chatgpt' if account.get('type') == 'chatgpt' else 'local',
                'label': 'ChatGPT connected' if account.get('type') == 'chatgpt' else 'Local workspace',
                'loginAvailable': True}

    def start_login(self) -> dict:
        result = self.request('account/login/start', {'type': 'chatgpt'})
        url = result.get('authUrl', '')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'auth.openai.com', 'chatgpt.com'} or parsed.username or parsed.password:
            raise ValueError('The host returned an unexpected login URL.')
        return {'authUrl': url, 'loginId': result.get('loginId'), 'state': 'pending'}
