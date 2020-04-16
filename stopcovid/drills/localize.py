import os
from typing import Dict, Optional

from jinja2 import Template


CACHE = None
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


SUPPORTED_LANGUAGES = {"en", "es", "fr", "pt", "zh"}


def localize(message: str, lang: Optional[str], **kwargs) -> str:
    lang = lang or "en"
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    template = Template(message)
    result = template.render(**localizations_for(lang))
    if kwargs:
        template = Template(result)
        result = template.render(**kwargs)
    return result


def localizations_for(lang: str) -> Dict[str, str]:
    from .content_loader import get_content_loader

    return get_content_loader().get_translations()[lang]
