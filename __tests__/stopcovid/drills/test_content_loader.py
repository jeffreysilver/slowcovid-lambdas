import unittest
from time import sleep
from unittest.mock import patch, MagicMock

from stopcovid.drills.content_loader import S3Loader


@patch("stopcovid.drills.content_loader.S3Loader._populate_drills")
@patch("stopcovid.drills.content_loader.S3Loader._populate_translations")
class TestS3LoaderThreading(unittest.TestCase):
    def setUp(self) -> None:
        self.version = "1"

        def mock_object(*args, **kwargs):
            result = MagicMock()
            result.version_id = self.version
            return result

        s3_mock = MagicMock()
        s3_mock.Object.side_effect = mock_object

        boto3_patch = patch("stopcovid.drills.content_loader.boto3.resource", return_value=s3_mock)
        boto3_patch.start()

        sleep_patch = patch("stopcovid.drills.content_loader.sleep")
        sleep_patch.start()

        self.addCleanup(boto3_patch.stop)
        self.addCleanup(sleep_patch.stop)

    def test_not_stale_content(self, populate_translations_patch, populate_drills_patch):
        loader = S3Loader("bucket-foo")
        sleep(0.05)  # give polling thread time to run
        self.assertEqual(1, populate_translations_patch.call_count)
        self.assertEqual(1, populate_drills_patch.call_count)
        loader.get_all_drill_slugs()
        self.assertEqual(1, populate_translations_patch.call_count)
        self.assertEqual(1, populate_drills_patch.call_count)

    def test_stale_content(self, populate_translations_patch, populate_drills_patch):
        loader = S3Loader("bucket-foo")
        self.assertEqual(1, populate_translations_patch.call_count)
        self.assertEqual(1, populate_drills_patch.call_count)
        self.version = "2"
        sleep(0.05)  # give polling thread time to run
        loader.get_all_drill_slugs()
        self.assertEqual(2, populate_translations_patch.call_count)
        self.assertEqual(2, populate_drills_patch.call_count)
        sleep(0.05)  # give polling thread time to run
        loader.get_all_drill_slugs()
        self.assertEqual(2, populate_translations_patch.call_count)
        self.assertEqual(2, populate_drills_patch.call_count)
