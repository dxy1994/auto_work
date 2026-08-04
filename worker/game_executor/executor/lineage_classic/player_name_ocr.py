"""按已知订单角色名分段识别天堂交易申请中的玩家名。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

try:
    import cv2
    import numpy as np
except ImportError:  # 由调用方转为人工审核
    cv2 = None
    np = None

from game_executor.executor.lineage_classic.font_metrics import (
    ENGLISH_OCR_ALLOWED_VISUAL_SYMBOLS,
    character_advance_width,
    character_ocr_adjustments,
    character_ocr_visual_equivalents,
    character_pair_advance_adjustment,
    korean_ocr_text_matches,
)
from game_executor.executor.lineage_classic.paddle_ocr import recognize_text_line


SEGMENT_PADDING = 0
REPEATED_ENGLISH_OCR_RIGHT_PADDING = 2
CONSTRAINED_MATCH_MIN_CONFIDENCE = 80.0
# 单个 5px 点阵字母（尤其 n/s）即使裁剪正确，英文模型也可能只有约 29%
# 置信度；最终仍需整串平均置信度及连续三帧共同约束。
SEGMENTED_EXACT_MIN_CONFIDENCE = 25.0
SEGMENTED_EXACT_MIN_AVERAGE_CONFIDENCE = 65.0


@dataclass(frozen=True)
class ExpectedNameRun:
    kind: str
    text: str


@dataclass(frozen=True)
class NameSegment:
    kind: str
    expected: str
    left: int
    right: int
    crop_left: int
    crop_right: int
    image: object


@dataclass(frozen=True)
class NameRunRecognition:
    kind: str
    expected: str
    observed: str
    visual_observed: str
    confidence: float
    left: int
    right: int
    crop_left: int
    crop_right: int
    high_risk_equivalent: bool = False


@dataclass(frozen=True)
class PlayerNameRecognition:
    text: str
    confidence: float
    average_confidence: float
    start_x: int
    end_x: int
    runs: tuple[NameRunRecognition, ...]
    verified: bool
    strategy: str
    visual_observed: str = ""


def character_kind(char: str) -> str:
    if "A" <= char <= "Z" or "a" <= char <= "z":
        return "english"
    if "\uac00" <= char <= "\ud7a3" or "\u3131" <= char <= "\u318e":
        return "korean"
    raise ValueError(f"玩家名包含不支持的字符: {char!r}")


def split_expected_name(expected_name: str) -> tuple[ExpectedNameRun, ...]:
    """英文逐字符拆分、韩文连续识别，避免 ``TT`` 被合并成 ``ㅠ``。"""
    value = str(expected_name or "").strip()
    if not value:
        raise ValueError("订单玩家名不能为空")
    runs: list[ExpectedNameRun] = []
    for char in value:
        kind = character_kind(char)
        if kind == "korean" and runs and runs[-1].kind == kind:
            previous = runs[-1]
            runs[-1] = ExpectedNameRun(kind, previous.text + char)
        else:
            runs.append(ExpectedNameRun(kind, char))
    return tuple(runs)


def estimated_character_width(char: str) -> int:
    """返回配置中的字符前进宽度。"""
    character_kind(char)
    return character_advance_width(char)


def estimated_text_width(text: str) -> int:
    return sum(estimated_character_width(char) for char in text)


def _foreground_mask(image):
    if cv2 is None or np is None:
        raise RuntimeError("未安装 OpenCV/Numpy，无法分割玩家名")
    if image is None or getattr(image, "size", 0) == 0:
        raise ValueError("玩家名截图为空")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # 面板棕色背景灰度约 110～145，浅米色文字的主体超过 175。
    # 使用字体主体而非抗锯齿边缘寻找空白列，可避免把整块面板当成文字。
    return (gray >= 175).astype("uint8")


ENGLISH_GLYPH_LEFT_INSETS = {
    # 这些窄字形在固定 10px 单元内从右侧开始绘制；分段起点仍需还原到单元左边界。
    "I": 2,
    "i": 3,
    "k": 2,
    "l": 3,
    "r": 2,
}


def _has_trade_panel_left_border(projection) -> bool:
    """识别 1280x960 交易提示框在姓名裁剪区左侧留下的固定装饰亮点。"""
    return (
        len(projection) >= 9
        and int(projection[4]) >= 3
        and int(projection[6:9].sum()) >= 4
        and int(projection[6:9].max()) <= 4
    )


def _detected_glyph_start(projection, search_limit: int = 32) -> int:
    limit = min(len(projection), max(1, search_limit))
    # 弹窗左边框偶尔会在前几列留下 1～2 个孤立亮点。r 等窄字符只有
    # 2 列，但纵向亮点总量仍不少于 6，因此同时使用宽度和总亮点过滤。
    column = 0
    while column < limit:
        if projection[column] <= 0:
            column += 1
            continue
        start = column
        while column < limit and projection[column] > 0:
            column += 1
        run = projection[start:column]
        # 1280x960 交易框左沿会在 X=4 和 X=6..8 留下少量装饰亮点；真实的
        # 英文字形纵向至少有 5 个亮点，借此避免把面板噪点当成名字起点。
        if (
            column - start >= 2
            and int(run.sum()) >= 8
            and int(run.max()) >= 5
        ):
            return int(start)
    active = np.flatnonzero(projection >= 2)
    return int(active[0]) if active.size else 0


def _text_start(projection, first_char: str, search_limit: int = 32) -> int:
    glyph_start = _detected_glyph_start(projection, search_limit)
    # 交易提示框中的姓名字符单元固定从 X=17 开始；韩文及窄英文字形的实际
    # 亮像素可能从 X=19/20 才出现，不能把亮像素起点误当成字符单元起点。
    if (
        _has_trade_panel_left_border(projection)
        and 17 <= glyph_start <= 20
    ):
        return 17
    inset = ENGLISH_GLYPH_LEFT_INSETS.get(first_char, 0)
    return max(0, glyph_start - inset)


def segment_expected_name(image, expected_name: str) -> tuple[NameSegment, ...]:
    """从姓名起点开始，完全按照字体宽度配置计算每段边界。"""
    runs = split_expected_name(expected_name)
    mask = _foreground_mask(image)
    projection = mask.sum(axis=0)
    glyph_start = _detected_glyph_start(projection)
    has_trade_panel_border = _has_trade_panel_left_border(projection)
    start = _text_start(projection, expected_name[0])

    expected_value = "".join(run.text for run in runs)
    boundaries = [start]
    cumulative_width = 0
    character_index = 0
    for index, run in enumerate(runs):
        for char in run.text:
            following = (
                expected_value[character_index + 1]
                if character_index + 1 < len(expected_value)
                else None
            )
            cumulative_width += (
                estimated_character_width(char)
                + character_pair_advance_adjustment(char, following)
            )
            character_index += 1
        boundary = start + cumulative_width
        if boundary > image.shape[1]:
            raise ValueError(
                f"玩家名配置宽度超出识别区域: expected={expected_name!r} "
                f"required={boundary}px available={image.shape[1]}px"
            )
        boundaries.append(boundary)

    segments: list[NameSegment] = []
    for index, run in enumerate(runs):
        left = max(0, boundaries[index] - SEGMENT_PADDING)
        right = min(image.shape[1], boundaries[index + 1] + SEGMENT_PADDING)
        if right <= left:
            raise ValueError(
                f"玩家名分段范围无效: {run.text!r} X[{left},{right})"
            )
        crop_left = left
        crop_right = right
        if run.kind == "korean" and index == 0 and has_trade_panel_border:
            # 保留固定 X=17 单元原点用于后续英文边界，但韩文 OCR 从首字实际
            # 亮像素开始，避免左侧两列面板底色影响韩文模型。
            crop_left = max(crop_left, glyph_start)
        if run.kind == "english":
            left_adjust, right_adjust = character_ocr_adjustments(run.text)
            crop_left = max(0, left + left_adjust)
            crop_right = min(image.shape[1], right + right_adjust)
            repeated_t_with_previous = (
                run.text == "T"
                and index > 0
                and runs[index - 1].kind == "english"
                and runs[index - 1].text == run.text
            )
            repeated_t_with_following = (
                run.text == "T"
                and index + 1 < len(runs)
                and runs[index + 1].kind == "english"
                and runs[index + 1].text == run.text
            )
            # 大写 T 连续出现时，前一字形会紧贴当前单元。当前字符左侧不再扩展
            # 到前一单元，并在右侧保留两列背景，避免实机样本中的 TT 被合并成 U。
            if repeated_t_with_previous:
                crop_left = max(crop_left, left)
            if repeated_t_with_previous or repeated_t_with_following:
                crop_right = min(
                    image.shape[1],
                    crop_right + REPEATED_ENGLISH_OCR_RIGHT_PADDING,
                )
        if crop_right <= crop_left:
            raise ValueError(
                f"玩家名 OCR 裁剪范围无效: {run.text!r} "
                f"X[{crop_left},{crop_right})"
            )
        segments.append(NameSegment(
            kind=run.kind,
            expected=run.text,
            left=left,
            right=right,
            crop_left=crop_left,
            crop_right=crop_right,
            image=image[:, crop_left:crop_right].copy(),
        ))
    return tuple(segments)


def _clean_recognized_text(value: str, kind: str) -> str:
    if kind == "english":
        return "".join(
            char for char in str(value or "")
            if (
                "A" <= char <= "Z"
                or "a" <= char <= "z"
                or "0" <= char <= "9"
                or char in ENGLISH_OCR_ALLOWED_VISUAL_SYMBOLS
            )
        )
    return "".join(
        char for char in str(value or "")
        if "\uac00" <= char <= "\ud7a3" or "\u3131" <= char <= "\u318e"
    )


def _matches_expected_segment(
    observed: str,
    expected: str,
    kind: str,
) -> bool:
    if kind == "english" and len(expected) == 1:
        return observed.casefold() in character_ocr_visual_equivalents(expected)
    if kind == "korean":
        return korean_ocr_text_matches(expected, observed)
    return observed.casefold() == expected.casefold()


def _is_exact_expected_segment(
    observed: str,
    expected: str,
) -> bool:
    return observed.casefold() == expected.casefold()


def _prepared_variants(image, kind: str) -> tuple[object, ...]:
    """提供原色与对比度增强两种输入；命中期望值时优先采用。"""
    if kind == "english":
        # 单个像素英文字母很窄；最近邻 8 倍放大可以保留 T/I 等笔画结构。
        nearest = cv2.resize(
            image, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST
        )
        cubic = cv2.resize(
            image, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC
        )
        gray = cv2.cvtColor(cubic, cv2.COLOR_BGR2GRAY)
        _, binary_150 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        _, binary_170 = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY)
        return tuple(
            cv2.copyMakeBorder(
                variant, 12, 12, 12, 12, cv2.BORDER_REPLICATE
            )
            for variant in (
                nearest,
                cubic,
                cv2.cvtColor(binary_150, cv2.COLOR_GRAY2BGR),
                cv2.cvtColor(binary_170, cv2.COLOR_GRAY2BGR),
            )
        )
    scaled = cv2.resize(
        image, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC
    )
    color = cv2.copyMakeBorder(
        scaled, 10, 10, 10, 10, cv2.BORDER_REPLICATE
    )
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    ).apply(gray)
    contrast = cv2.copyMakeBorder(
        cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR),
        10, 10, 10, 10,
        cv2.BORDER_REPLICATE,
    )
    return color, contrast


def _recognize_segment(
    segment: NameSegment,
    recognizer: Callable[[object, str], tuple[str, float]],
) -> NameRunRecognition:
    candidates: list[tuple[str, float]] = []
    for prepared in _prepared_variants(segment.image, segment.kind):
        raw_text, confidence = recognizer(prepared, segment.kind)
        candidate = (
            _clean_recognized_text(raw_text, segment.kind),
            float(confidence),
        )
        candidates.append(candidate)
        if (
            _is_exact_expected_segment(
                candidate[0],
                segment.expected,
            )
            and candidate[1] >= 70.0
        ):
            break
    exact_matches = [
        candidate for candidate in candidates
        if _is_exact_expected_segment(candidate[0], segment.expected)
    ]
    high_risk_matches = [
        candidate for candidate in candidates
        if (
            not _is_exact_expected_segment(candidate[0], segment.expected)
            and _matches_expected_segment(
                candidate[0],
                segment.expected,
                segment.kind,
            )
        )
    ]
    matches = exact_matches or high_risk_matches
    visual_observed, confidence = max(
        matches or candidates,
        key=lambda candidate: candidate[1],
    )
    observed = segment.expected if matches else visual_observed
    return NameRunRecognition(
        kind=segment.kind,
        expected=segment.expected,
        observed=observed,
        visual_observed=visual_observed,
        confidence=confidence,
        left=segment.left,
        right=segment.right,
        crop_left=segment.crop_left,
        crop_right=segment.crop_right,
        high_risk_equivalent=bool(high_risk_matches and not exact_matches),
    )


def _mixed_key(value: str) -> str:
    return "".join(
        char.casefold()
        for char in str(value or "")
        if (
            "A" <= char <= "Z"
            or "a" <= char <= "z"
            or "\uac00" <= char <= "\ud7a3"
            or "\u3131" <= char <= "\u318e"
        )
    )


def _expected_korean_visual_keys(expected_name: str) -> frozenset[str]:
    """生成韩文模型对已知姓名可能产生的严格等价视觉串。

    天堂的小号像素字体会把连续 ``TT`` 识别为 ``ㅠ``、``ㅜ`` 或
    拉丁小写 ``w``。这里只替换订单姓名中明确存在的 ``TT`` 对，
    其他字符仍必须逐字一致。
    """
    value = str(expected_name)
    keys = {""}
    index = 0
    while index < len(value):
        if (
            index + 1 < len(value)
            and value[index].casefold() == "t"
            and value[index + 1].casefold() == "t"
        ):
            keys = {
                prefix + visual
                for prefix in keys
                for visual in ("ㅠ", "ㅜ", "w", "tt")
            }
            index += 2
            continue
        keys = {
            prefix + value[index].casefold()
            for prefix in keys
        }
        index += 1
    return frozenset(keys)


def _is_expected_korean_visual(
    observed: str,
    expected_name: str,
) -> bool:
    observed_key = _mixed_key(observed)
    # 姓名后只允许天堂交易提示使用的主格助词，不能接受任意长前缀匹配。
    allowed_suffixes = {"", "이", "가", "이가"}
    return any(
        observed_key.startswith(expected_key)
        and observed_key[len(expected_key):] in allowed_suffixes
        for expected_key in _expected_korean_visual_keys(expected_name)
    )


def _recognize_korean_constrained_candidate(
    image,
    expected_name: str,
    start: int,
    end: int,
    recognizer: Callable[[object, str], tuple[str, float]],
) -> tuple[str, float] | None:
    # 多取最多 40px 让韩文模型完整看到姓名后的 이[가]；比例字体会让
    # 姓名终点提前，固定 40px 可覆盖括号与助词且仍位于交易提示首句内。
    right = min(image.shape[1], end + 40)
    source = image[:, max(0, start):right]
    candidates: list[tuple[str, float]] = []
    for prepared in _prepared_variants(source, "korean"):
        text, confidence = recognizer(prepared, "korean")
        if (
            float(confidence) >= CONSTRAINED_MATCH_MIN_CONFIDENCE
            and _is_expected_korean_visual(text, expected_name)
        ):
            candidates.append((str(text), float(confidence)))
    return max(candidates, key=lambda candidate: candidate[1]) if candidates else None


def recognize_expected_player_name(
    image,
    expected_name: str,
    *,
    recognizer: Callable[[object, str], tuple[str, float]] = recognize_text_line,
) -> PlayerNameRecognition:
    """分别识别英文和韩文段，然后按原顺序拼接。"""
    segments = segment_expected_name(image, expected_name)
    runs = tuple(
        _recognize_segment(segment, recognizer)
        for segment in segments
    )
    text = "".join(run.observed for run in runs)
    visual_text = "".join(run.visual_observed for run in runs)
    confidences = [run.confidence for run in runs if run.observed]
    confidence = min(confidences) if len(confidences) == len(runs) else -1.0
    average_confidence = (
        sum(confidences) / len(confidences)
        if len(confidences) == len(runs)
        else -1.0
    )
    start_x = min(run.left for run in runs)
    end_x = max(run.right for run in runs)
    segmented_exact = text.casefold() == str(expected_name).casefold()
    high_risk_equivalent_used = any(
        run.high_risk_equivalent for run in runs
    )
    if (
        segmented_exact
        and confidence >= SEGMENTED_EXACT_MIN_CONFIDENCE
        and average_confidence >= SEGMENTED_EXACT_MIN_AVERAGE_CONFIDENCE
    ):
        return PlayerNameRecognition(
            text=str(expected_name),
            confidence=confidence,
            average_confidence=average_confidence,
            start_x=start_x,
            end_x=end_x,
            runs=runs,
            verified=True,
            strategy=(
                "segmented_high_risk_equivalent"
                if high_risk_equivalent_used
                else "segmented_exact"
            ),
            visual_observed=visual_text,
        )

    constrained = _recognize_korean_constrained_candidate(
        image,
        expected_name,
        start_x,
        end_x,
        recognizer,
    )
    if constrained is not None:
        constrained_observed, constrained_confidence = constrained
        return PlayerNameRecognition(
            text=str(expected_name),
            confidence=constrained_confidence,
            average_confidence=constrained_confidence,
            start_x=start_x,
            end_x=end_x,
            runs=runs,
            verified=True,
            strategy="korean_visual_constrained",
            visual_observed=constrained_observed,
        )

    return PlayerNameRecognition(
        text=text,
        confidence=confidence,
        average_confidence=average_confidence,
        start_x=start_x,
        end_x=end_x,
        runs=runs,
        verified=False,
        strategy="segmented_unverified",
        visual_observed=visual_text,
    )
