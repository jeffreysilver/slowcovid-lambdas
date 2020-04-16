import json
import os
from collections import defaultdict
from typing import Dict, Optional

import boto3
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
    if CACHE is None:
        _populate_cache()
    return CACHE[lang]


def _populate_cache():
    global CACHE
    CACHE = defaultdict(dict)
    raw_translations = json.loads(_get_translations())
    for entry in raw_translations["instructions"]:
        CACHE[entry["language"]][entry["label"]] = entry["translation"]


def _get_translations() -> str:
    s3_bucket = os.getenv("DRILL_CONTENT_S3_BUCKET")
    if not s3_bucket:
        # in production, we serve from S3. The file-system JSON is useful for demo purposes.
        with open(os.path.join(__location__, "drill_content/translations.json")) as f:
            return f.read()
    s3 = boto3.resource("s3")
    translations = s3.Object(s3_bucket, "translations.json")
    return translations.get()["Body"].read().decode("utf-8")
