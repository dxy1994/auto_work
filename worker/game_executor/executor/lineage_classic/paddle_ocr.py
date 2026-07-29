"""PaddleOCR 韩文识别适配器（固定 CPU 推理）。"""

import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_engine = None
_engine_lock = threading.Lock()
_text_recognition_engines: dict[str, object] = {}
_text_recognition_engine_lock = threading.Lock()

TEXT_RECOGNITION_MODELS = {
    "english": "en_PP-OCRv5_mobile_rec",
    "korean": "korean_PP-OCRv5_mobile_rec",
}
OCR_MODEL_NAMES = (
    "PP-OCRv5_mobile_det",
    "korean_PP-OCRv5_mobile_rec",
    "en_PP-OCRv5_mobile_rec",
)
OCR_MODEL_REQUIRED_FILES = (
    "inference.json",
    "inference.pdiparams",
    "inference.yml",
)


@dataclass(frozen=True)
class OcrTextBox:
    text: str
    confidence: float
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.right) / 2, (self.top + self.bottom) / 2


def bundled_ocr_model_root() -> Path | None:
    """返回显式配置或随 EXE 分发的 OCR 模型根目录。"""
    configured = os.getenv("LINEAGE_OCR_MODEL_DIR", "").strip()
    if configured:
        return Path(os.path.expandvars(configured)).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "ocr_models"
    return None


def bundled_ocr_model_directories() -> dict[str, Path]:
    """校验并返回随程序分发的三个模型目录；源码模式仍使用 PaddleX 缓存。"""
    root = bundled_ocr_model_root()
    if root is None:
        return {}

    missing: list[str] = []
    directories: dict[str, Path] = {}
    for model_name in OCR_MODEL_NAMES:
        model_directory = root / model_name
        absent_files = [
            file_name
            for file_name in OCR_MODEL_REQUIRED_FILES
            if not (model_directory / file_name).is_file()
        ]
        if absent_files:
            missing.append(f"{model_name}: {', '.join(absent_files)}")
        else:
            directories[model_name] = model_directory
    if missing:
        raise RuntimeError(
            f"OCR 模型目录不完整: {root}；"
            + "；".join(missing)
            + "。请重新解压完整的游戏执行端安装包"
        )
    return directories


def build_paddle_ocr_engine():
    """创建轻量韩文 OCR 引擎；调用方负责复用实例。"""
    # 直接使用已指定的官方模型，避免每次启动探测多个模型托管站点。
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "未安装 PaddleOCR/PaddlePaddle，请安装游戏执行端依赖"
        ) from exc
    model_directories = bundled_ocr_model_directories()
    return PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_detection_model_dir=str(
            model_directories["PP-OCRv5_mobile_det"]
        ) if model_directories else None,
        text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
        text_recognition_model_dir=str(
            model_directories["korean_PP-OCRv5_mobile_rec"]
        ) if model_directories else None,
        device="cpu",
        # Paddle 3.3.1 在 Windows CPU 上执行该模型的 oneDNN 图时会触发
        # ConvertPirAttribute2RuntimeAttribute；关闭后使用稳定的 CPU 推理路径。
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def get_paddle_ocr_engine():
    """线程安全地延迟初始化模型，避免 Worker 启动时阻塞。"""
    global _engine
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is None:
            _engine = build_paddle_ocr_engine()
    return _engine


def recognize_korean(image) -> tuple[str, float]:
    """识别 OpenCV/Numpy 图像，返回文本和最低词块置信度（0–100）。"""
    results = get_paddle_ocr_engine().predict(image)
    return paddle_ocr_text(results)


def recognize_korean_boxes(image) -> list[OcrTextBox]:
    """识别文本框，坐标相对于传入图像。"""
    results = get_paddle_ocr_engine().predict(image)
    return paddle_ocr_boxes(results)


def build_text_recognition_engine(language: str):
    """创建不包含文字检测步骤的单行识别器。"""
    model_name = TEXT_RECOGNITION_MODELS.get(str(language).casefold())
    if model_name is None:
        raise ValueError(f"不支持的文字识别语言: {language}")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    try:
        from paddleocr import TextRecognition
    except ImportError as exc:
        raise RuntimeError(
            "当前 PaddleOCR 版本不支持 TextRecognition，请升级游戏执行端依赖"
        ) from exc
    model_directories = bundled_ocr_model_directories()
    return TextRecognition(
        model_name=model_name,
        model_dir=str(model_directories[model_name]) if model_directories else None,
        device="cpu",
        enable_mkldnn=False,
    )


def get_text_recognition_engine(language: str):
    """按语言线程安全地延迟初始化纯识别模型。"""
    key = str(language).casefold()
    if key not in TEXT_RECOGNITION_MODELS:
        raise ValueError(f"不支持的文字识别语言: {language}")
    engine = _text_recognition_engines.get(key)
    if engine is not None:
        return engine
    with _text_recognition_engine_lock:
        engine = _text_recognition_engines.get(key)
        if engine is None:
            engine = build_text_recognition_engine(key)
            _text_recognition_engines[key] = engine
    return engine


def recognize_text_line(image, language: str) -> tuple[str, float]:
    """识别已经裁好的单行英文或韩文图片，不再执行文字框检测。"""
    results = get_text_recognition_engine(language).predict(
        input=image,
        batch_size=1,
    )
    return paddle_ocr_text(results)


def _result_data(result: object) -> dict | None:
    payload = getattr(result, "json", result)
    if callable(payload):
        payload = payload()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        return None
    data = payload.get("res", payload)
    return data if isinstance(data, dict) else None


def _confidence(raw_score: object) -> float:
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return -1.0
    return score * 100.0 if 0.0 <= score <= 1.0 else score


def _box_bounds(raw_box: object) -> tuple[float, float, float, float] | None:
    if hasattr(raw_box, "tolist"):
        raw_box = raw_box.tolist()
    if not isinstance(raw_box, (list, tuple)):
        return None
    if len(raw_box) == 4 and all(isinstance(value, (int, float)) for value in raw_box):
        left, top, right, bottom = (float(value) for value in raw_box)
        return left, top, right, bottom
    points = []
    for point in raw_box:
        if hasattr(point, "tolist"):
            point = point.tolist()
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def paddle_ocr_boxes(results: Iterable[object]) -> list[OcrTextBox]:
    """从 PaddleOCR 3.x Result 中提取每个文本框及置信度。"""
    output: list[OcrTextBox] = []
    for result in results or ():
        data = _result_data(result)
        if data is None:
            continue
        texts = data.get("rec_texts")
        scores = data.get("rec_scores")
        boxes = data.get("rec_boxes")
        if boxes is None:
            boxes = data.get("rec_polys")
        if boxes is None:
            boxes = data.get("dt_polys")
        if texts is None or scores is None or boxes is None:
            continue
        for raw_text, raw_score, raw_box in zip(texts, scores, boxes):
            text = str(raw_text).strip()
            bounds = _box_bounds(raw_box)
            if not text or bounds is None:
                continue
            output.append(OcrTextBox(text, _confidence(raw_score), *bounds))
    return output


def paddle_ocr_text(results: Iterable[object]) -> tuple[str, float]:
    """从 PaddleOCR 3.x Result 中提取文本及所有非空词块的最低置信度。"""
    tokens: list[tuple[str, float]] = []
    for result in results or ():
        data = _result_data(result)
        if data is None:
            continue
        texts = data.get("rec_texts")
        scores = data.get("rec_scores")
        if texts is None and scores is None:
            text = str(data.get("rec_text") or "").strip()
            if text:
                tokens.append((text, _confidence(data.get("rec_score"))))
            continue
        if texts is None or scores is None:
            continue
        for raw_text, raw_score in zip(texts, scores):
            text = str(raw_text).strip()
            if not text:
                continue
            tokens.append((text, _confidence(raw_score)))
    if not tokens:
        return "", -1.0
    return (
        " ".join(text for text, _confidence in tokens),
        min(confidence for _text, confidence in tokens),
    )
