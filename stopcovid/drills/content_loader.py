import json
import logging
import os
from copy import copy
from typing import Dict, List
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from time import sleep

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

        # dictionaries are unordered, so we determine drill order by sorting the drill slugs
        self.all_drill_slugs.sort()

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
        logging.info("Loading drill content from the file system")
        with open(os.path.join(__location__, "drill_content/drills.json")) as f:
            self._populate_drills(f.read())
        with open(os.path.join(__location__, "drill_content/translations.json")) as f:
            self._populate_translations(f.read())


class S3Loader(ContentLoader):
    def __init__(self, s3_bucket):
        self.s3_bucket = s3_bucket
        self._populate_from_s3()

    def _populate_from_s3(self):
        logging.info(f"Loading drill content from the {self.s3_bucket} S3 bucket")
        s3 = boto3.resource("s3")

        drill_object = s3.Object(self.s3_bucket, "drills.json")
        translations_object = s3.Object(self.s3_bucket, "translations.json")
        self._start_checking_for_updates(drill_object.version_id, translations_object.version_id)

        self._populate_drills(drill_object.get()["Body"].read().decode("utf-8"))
        self._populate_translations(translations_object.get()["Body"].read().decode("utf-8"))

    def _start_checking_for_updates(self, drill_version_id: str, translations_version_id: str):
        self.event = threading.Event()
        thread = threading.Thread(
            name="s3-poller",
            target=self._notify_on_update,
            args=(drill_version_id, translations_version_id, self.event),
            daemon=True,
        )
        thread.start()

    def _notify_on_update(
        self, drill_version_id: str, translations_version_id: str, event: threading.Event
    ):
        s3 = boto3.resource("s3")
        while True:
            drill_object = s3.Object(self.s3_bucket, "drills.json")
            translations_object = s3.Object(self.s3_bucket, "translations.json")
            if (
                drill_object.version_id != drill_version_id
                or translations_object.version_id != translations_version_id
            ):
                # NOTE: It's possible for one update cycle to detect only a change in the
                # drills.json or the translations.json files, because S3 doesn't support
                # transactional multi-file uploads. We should upload a backwards-compatible version
                # of translations.json first, then we should upload drills.json.

                logging.info("Drill or translation objects have changed in S3.")
                event.set()
                return
            sleep(30)

    def _is_content_stale(self) -> bool:
        return self.event.is_set()


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
