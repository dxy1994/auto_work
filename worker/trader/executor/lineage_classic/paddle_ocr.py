"""PaddleOCR 韩文识别适配器（固定 CPU 推理）。"""

import json
import os
import threading
from typing import Iterable


_engine = None
_engine_lock = threading.Lock()


def build_paddle_ocr_engine():
    """创建轻量韩文 OCR 引擎；调用方负责复用实例。"""
    # 直接使用已指定的官方模型，避免每次启动探测多个模型托管站点。
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "未安装 PaddleOCR/PaddlePaddle，请安装 Trader 依赖"
        ) from exc
    return PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
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


def paddle_ocr_text(results: Iterable[object]) -> tuple[str, float]:
    """从 PaddleOCR 3.x Result 中提取文本及所有非空词块的最低置信度。"""
    tokens: list[tuple[str, float]] = []
    for result in results or ():
        payload = getattr(result, "json", result)
        if callable(payload):
            payload = payload()
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            continue
        data = payload.get("res", payload)
        if not isinstance(data, dict):
            continue
        texts = data.get("rec_texts")
        scores = data.get("rec_scores")
        if texts is None or scores is None:
            continue
        for raw_text, raw_score in zip(texts, scores):
            text = str(raw_text).strip()
            if not text:
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = -1.0
            # PaddleOCR 返回 0–1；保留对测试桩或兼容结果中 0–100 的支持。
            confidence = score * 100.0 if 0.0 <= score <= 1.0 else score
            tokens.append((text, confidence))
    if not tokens:
        return "", -1.0
    return (
        " ".join(text for text, _confidence in tokens),
        min(confidence for _text, confidence in tokens),
    )
