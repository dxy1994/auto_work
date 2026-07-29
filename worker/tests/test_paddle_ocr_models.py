import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from game_executor.executor.lineage_classic import paddle_ocr


def create_model_root(root: Path) -> None:
    for model_name in paddle_ocr.OCR_MODEL_NAMES:
        model_directory = root / model_name
        model_directory.mkdir(parents=True)
        for file_name in paddle_ocr.OCR_MODEL_REQUIRED_FILES:
            (model_directory / file_name).write_bytes(b"model")


class BundledOcrModelTest(unittest.TestCase):
    def test_exception_chain_message_includes_wrapped_dependency_reason(self):
        dependency_error = RuntimeError(
            "The following dependencies are not available: python-bidi"
        )
        try:
            raise RuntimeError(
                "A dependency error occurred during predictor creation"
            ) from dependency_error
        except RuntimeError as error:
            message = paddle_ocr.exception_chain_message(error)

        self.assertIn("predictor creation", message)
        self.assertIn("python-bidi", message)

    def test_configured_model_root_resolves_all_required_models(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_root = Path(temporary_directory)
            create_model_root(model_root)

            with mock.patch.dict(
                os.environ,
                {"LINEAGE_OCR_MODEL_DIR": str(model_root)},
            ):
                directories = paddle_ocr.bundled_ocr_model_directories()

        self.assertEqual(set(paddle_ocr.OCR_MODEL_NAMES), set(directories))

    def test_incomplete_bundled_model_fails_instead_of_downloading(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_root = Path(temporary_directory)
            create_model_root(model_root)
            (model_root / "PP-OCRv5_mobile_det" / "inference.json").unlink()

            with mock.patch.dict(
                os.environ,
                {"LINEAGE_OCR_MODEL_DIR": str(model_root)},
            ), self.assertRaisesRegex(RuntimeError, "OCR 模型目录不完整"):
                paddle_ocr.bundled_ocr_model_directories()

    def test_ocr_builders_pass_bundled_model_directories(self):
        paddle_calls = []
        recognition_calls = []

        class FakePaddleOCR:
            def __init__(self, **kwargs):
                paddle_calls.append(kwargs)

        class FakeTextRecognition:
            def __init__(self, **kwargs):
                recognition_calls.append(kwargs)

        with tempfile.TemporaryDirectory() as temporary_directory:
            model_root = Path(temporary_directory)
            create_model_root(model_root)
            fake_module = SimpleNamespace(
                PaddleOCR=FakePaddleOCR,
                TextRecognition=FakeTextRecognition,
            )
            with mock.patch.dict(
                os.environ,
                {"LINEAGE_OCR_MODEL_DIR": str(model_root)},
            ), mock.patch.dict(sys.modules, {"paddleocr": fake_module}):
                paddle_ocr.build_paddle_ocr_engine()
                paddle_ocr.build_text_recognition_engine("english")

        self.assertEqual(
            str(model_root / "PP-OCRv5_mobile_det"),
            paddle_calls[0]["text_detection_model_dir"],
        )
        self.assertEqual(
            str(model_root / "korean_PP-OCRv5_mobile_rec"),
            paddle_calls[0]["text_recognition_model_dir"],
        )
        self.assertEqual(
            str(model_root / "en_PP-OCRv5_mobile_rec"),
            recognition_calls[0]["model_dir"],
        )


if __name__ == "__main__":
    unittest.main()
