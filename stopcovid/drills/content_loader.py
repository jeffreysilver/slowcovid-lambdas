import json
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict

import boto3

from .drills import Drill, DrillSchema

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


class ContentLoader(ABC):
    @abstractmethod
    def get_drills(self) -> Dict[str, Drill]:
        pass

    @abstractmethod
    def get_translations(self) -> Dict[str, Dict[str, str]]:
        pass

    @staticmethod
    def _to_drills_dict(drill_content: str) -> Dict[str, Drill]:
        result = {}
        raw_drills = json.loads(drill_content)
        for drill_key, raw_drill in raw_drills.items():
            result[drill_key] = DrillSchema().load(raw_drill)
        return result

    @staticmethod
    def _to_translations_dict(translations_content: str) -> Dict[str, Dict[str, str]]:
        result = defaultdict(dict)
        raw_translations = json.loads(translations_content)
        for entry in raw_translations["instructions"]:
            result[entry["language"]][entry["label"]] = entry["translation"]

        return result


class SourceRepoLoader(ContentLoader):
    def __init__(self):
        with open(os.path.join(__location__, "drill_content/drills.json")) as f:
            self.drills_dict = self._to_drills_dict(f.read())
        with open(os.path.join(__location__, "drill_content/translations.json")) as f:
            self.translations_dict = self._to_translations_dict(f.read())

    def get_drills(self) -> Dict[str, Drill]:
        return self.drills_dict

    def get_translations(self) -> Dict[str, Dict[str, str]]:
        return self.translations_dict


class S3Loader(ContentLoader):
    def __init__(self, s3_bucket):
        self.s3_bucket = s3_bucket
        self._populate_from_s3()

    def _populate_from_s3(self):
        s3 = boto3.resource("s3")

        drill_object = s3.Object(self.s3_bucket, "drills.json")
        self.drills_dict = self._to_drills_dict(drill_object.get()["Body"].read().decode("utf-8"))
        translations_object = s3.Object(self.s3_bucket, "translations.json")
        self.translations_dict = self._to_translations_dict(
            translations_object.get()["Body"].read().decode("utf-8")
        )

    def get_drills(self) -> Dict[str, Drill]:
        return self.drills_dict

    def get_translations(self) -> Dict[str, Dict[str, str]]:
        return self.translations_dict


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
