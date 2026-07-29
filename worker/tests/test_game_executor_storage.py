import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_executor import config
from game_executor import storage


class _Body(io.BytesIO):
    pass


class GameExecutorStorageTest(unittest.TestCase):
    def setUp(self):
        storage._client = None

    def tearDown(self):
        storage._client = None

    def test_upload_relative_address_becomes_rustfs_object_key(self):
        self.assertEqual(
            "images/item.png",
            storage.object_key("/uploads/images/item.png"),
        )
        self.assertEqual(
            "images/item.png",
            storage.object_key("uploads/images/item.png"),
        )

    def test_object_key_rejects_parent_traversal(self):
        with self.assertRaises(storage.StorageImageError):
            storage.object_key("/uploads/../secret.txt")

    def test_read_image_uses_configured_bucket_and_object_key(self):
        client = mock.Mock()
        client.get_object.return_value = {"Body": _Body(b"png-bytes")}
        with mock.patch.object(storage, "_get_client", return_value=client), \
                mock.patch.object(config, "STORAGE_BUCKET", "auto-uploads"):
            raw, address = storage.read_image("/uploads/images/item.png")

        self.assertEqual(b"png-bytes", raw)
        self.assertEqual("s3://auto-uploads/images/item.png", address)
        client.get_object.assert_called_once_with(
            Bucket="auto-uploads",
            Key="images/item.png",
        )

    def test_read_image_rejects_oversized_object(self):
        client = mock.Mock()
        client.get_object.return_value = {"Body": _Body(b"12345")}
        with mock.patch.object(storage, "_get_client", return_value=client):
            with self.assertRaises(storage.StorageImageError):
                storage.read_image("/uploads/images/item.png", max_bytes=4)


if __name__ == "__main__":
    unittest.main()
