import json
import os
from abc import ABC
from collections import defaultdict
from copy import copy
from typing import Dict, List

import boto3

from .drills import Drill, DrillSchema

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


class ContentLoader(ABC):
    def _populate_drills(self, drill_content: str):
        self.drills_dict = {}
        self.all_drill_slugs = []
        raw_drills = json.loads(drill_content)
        for drill_slug, raw_drill in raw_drills.items():
            self.drills_dict[drill_slug] = DrillSchema().load(raw_drill)
            self.all_drill_slugs.append(drill_slug)

    def _populate_translations(self, translations_content: str):
        self.translations_dict = defaultdict(dict)
        raw_translations = json.loads(translations_content)
        for entry in raw_translations["instructions"]:
            self.translations_dict[entry["language"]][entry["label"]] = entry["translation"]

    def get_drills(self) -> Dict[str, Drill]:
        return self.drills_dict

    def get_translations(self) -> Dict[str, Dict[str, str]]:
        return self.translations_dict

    def get_all_drill_slugs(self) -> List[str]:
        return copy(self.all_drill_slugs)


class SourceRepoLoader(ContentLoader):
    def __init__(self):
        with open(os.path.join(__location__, "drill_content/drills.json")) as f:
            self._populate_drills(f.read())
        with open(os.path.join(__location__, "drill_content/translations.json")) as f:
            self._populate_translations(f.read())


class S3Loader(ContentLoader):
    def __init__(self, s3_bucket):
        self.s3_bucket = s3_bucket
        self._populate_from_s3()

    def _populate_from_s3(self):
        s3 = boto3.resource("s3")

        drill_object = s3.Object(self.s3_bucket, "drills.json")
        self._populate_drills(drill_object.get()["Body"].read().decode("utf-8"))
        translations_object = s3.Object(self.s3_bucket, "translations.json")
        self._populate_translations(translations_object.get()["Body"].read().decode("utf-8"))


CONTENT_LOADER = None


def get_content_loader() -> ContentLoader:
    global CONTENT_LOADER
    if CONTENT_LOADER is None:
        s3_bucket = os.getenv("DRILL_CONTENT_S3_BUCKET")
        if s3_bucket:
            CONTENT_LOADER = S3Loader(s3_bucket)
        else:
            CONTENT_LOADER = SourceRepoLoader()
    return CONTENT_LOADER
