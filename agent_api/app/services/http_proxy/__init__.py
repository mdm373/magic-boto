from settings import get_settings

from .http_proxy import HttpProxy

_settings = get_settings()


def create_openai_proxy() -> HttpProxy:
    return HttpProxy(_settings.openai_proxy_base_url, _settings.openai_proxy_timeout)


__all__ = ["create_openai_proxy", "HttpProxy"]
