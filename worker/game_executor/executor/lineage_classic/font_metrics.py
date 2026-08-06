"""天堂经典版 1280x960 客户区中的玩家名字体宽度配置。"""

from types import MappingProxyType


# 现有标定表来自原 800x600 客户区；1280x960 的游戏 UI 按 1.6 倍等比渲染。
FONT_RENDER_SCALE = 1.6


def _scale_metric(value: int) -> int:
    return int(round(value * FONT_RENDER_SCALE))


# 2026-07-31 的五组 1280x960 实机交易请求覆盖了 A-Z/a-z。投影结果显示
# 所有英文字母都使用固定 10px 字符单元；字形本身虽然有宽窄差异，但下一个
# 字符的起点始终向右移动 10px。
ENGLISH_ADVANCE_WIDTH = 10
ENGLISH_ADVANCE_WIDTHS = MappingProxyType({
    char: ENGLISH_ADVANCE_WIDTH
    for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
})
DEFAULT_ENGLISH_ADVANCE_WIDTH = ENGLISH_ADVANCE_WIDTH
# 2026-07-31 的两组纯韩文实机交易请求显示，每个韩文音节使用固定 20px
# 字符单元；连续韩文会整段交给韩文 OCR，再与订单姓名的韩文段比较。
KOREAN_ADVANCE_WIDTH = 20
KOREAN_ADVANCE_WIDTHS = MappingProxyType({

})

# 单字符 OCR 通常需要保留字形左侧的一列棕色背景；部分窄字或带下伸部的
# 小写字母需要按实际字形修正裁剪边界。这里同样是字体配置，不参与动态吸附。
DEFAULT_ENGLISH_OCR_LEFT_ADJUST = -1
DEFAULT_ENGLISH_OCR_RIGHT_ADJUST = 0
ENGLISH_OCR_RIGHT_ADJUSTMENTS = MappingProxyType({
    "G": -1,
    "d": 1,
    "e": 1,
    "j": 1,
    # lokL 样本中的 l/o 都需要在右侧保留一列背景，不能带入下一字形。
    "l": -1,
    # n 的右边界紧贴下一字符，少取一列可避免把 o 的起笔带入。
    "n": -1,
    "o": -1,
    # t 的主要笔画位于字符单元中部，右侧留白不能带入下一字符。
    "t": -1,
})
ENGLISH_OCR_LEFT_ADJUSTMENTS = MappingProxyType({
    # V 需要保留完整尖角但不能带入左侧背景；配合 150 阈值可直接识别为 V。
    "V": 0,
    # g、i 从自身字符单元起点裁剪时，英文模型才能保留正确的下伸部/点。
    "g": 0,
    "i": 0,
    # o 左侧多保留一列背景，避免圆形字形被英文模型识别为 b。
    "o": -2,
    "t": 1,
})
ENGLISH_OCR_HIGH_RISK_EQUIVALENTS = MappingProxyType({
    # 这些规则只按订单中的期望字符单向启用，不会先对整段 OCR 文本做全局替换。
    # 天堂角色名不允许数字，因此 0/1/9 只能来自 OCR 的视觉误判。
    "C": frozenset({"c", "("}),
    "c": frozenset({"c", "("}),
    # 1280x960 点阵字形的 b/e/o 在单字 OCR 中可能分别呈现为 D/b/b；
    # 仅当订单对应位置明确期望该字母时才接受，不能做全局替换。
    "b": frozenset({"b", "d"}),
    "e": frozenset({"e", "b"}),
    "O": frozenset({"o", "0"}),
    "o": frozenset({"o", "0", "b"}),
    # 细竖线字形会在 I/i/l、数字 1、感叹号与竖线之间波动。
    "I": frozenset({"i", "l", "1", "!", "|"}),
    "i": frozenset({"i", "l", "1", "!", "|"}),
    "l": frozenset({"l", "i", "1", "!", "|"}),
    # 带下伸笔画的小写 j 偶尔只剩分号形态。
    "J": frozenset({"j", ";"}),
    "j": frozenset({"j", ";"}),
    # L 的横竖笔画容易被识别成左方括号或下划线。
    "L": frozenset({"l", "[", "_"}),
    # 小写 g 的下伸部在游戏点阵字体中经常被识别为数字 9。
    "g": frozenset({"g", "9", "3"}),
    # 下列点阵字母的主体很小，英文模型可能只保留成相似标点。
    "r": frozenset({"r", ",", "."}),
    "S": frozenset({"s", "$"}),
    "s": frozenset({"s", "$"}),
    "T": frozenset({"t", "+"}),
    "t": frozenset({"t", "+"}),
    "X": frozenset({"x", "*"}),
    "x": frozenset({"x", "*"}),
    # 大写 V/Z 的 1280x960 实机样本会稳定落到 u/2。
    "V": frozenset({"v", "u"}),
    "Z": frozenset({"z", ":", ";", "2"}),
    "z": frozenset({"z", ":", ";"}),
})

# 用户确认的常见韩文字形混淆按组双向匹配。规则仍只在订单姓名的对应位置
# 生效，不会先对 OCR 文本做全局替换。
KOREAN_OCR_BIDIRECTIONAL_GROUPS = (
    frozenset({"훅", "혹"}),
    frozenset({"당", "탕", "댱", "턍"}),
    frozenset({"옥", "욱", "종", "중"}),
    frozenset({"쭉", "쪽"}),
    frozenset({"횽", "흉"}),
)

# 1280x960 实机标定规则保留原有单向关系；用户指定的组则允许组内双向匹配。
KOREAN_OCR_HIGH_RISK_EQUIVALENTS = MappingProxyType({
    "샤": frozenset({"사"}),
    "뚱": frozenset({"풍"}),
    "빵": frozenset({"방"}),
    **{
        expected: frozenset(group - {expected})
        for group in KOREAN_OCR_BIDIRECTIONAL_GROUPS
        for expected in group
    },
})

# 只保留上表明确配置过的 OCR 标点结果。订单昵称本身仍只允许英文和韩文；
# 未在对应期望字母等价集合中的标点不会通过匹配。
ENGLISH_OCR_ALLOWED_VISUAL_SYMBOLS = frozenset(
    visual
    for equivalents in ENGLISH_OCR_HIGH_RISK_EQUIVALENTS.values()
    for visual in equivalents
    if not visual.isalnum()
)

# 1280x960 实机样本中的相邻英文字符没有额外挤压或扩张。
CHARACTER_PAIR_ADVANCE_ADJUSTMENTS = MappingProxyType({})


def character_advance_width(char: str) -> int:
    """返回一个已支持英文或韩文字符的固定前进宽度。"""
    if "\uac00" <= char <= "\ud7a3" or "\u3131" <= char <= "\u318e":
        return KOREAN_ADVANCE_WIDTHS.get(char, KOREAN_ADVANCE_WIDTH)
    else:
        return ENGLISH_ADVANCE_WIDTHS.get(
            char,
            DEFAULT_ENGLISH_ADVANCE_WIDTH,
        )


def character_ocr_adjustments(char: str) -> tuple[int, int]:
    """返回字符单元转换成 OCR 裁剪框时的左右边界调整量。"""
    return tuple(_scale_metric(value) for value in (
        ENGLISH_OCR_LEFT_ADJUSTMENTS.get(
            char,
            DEFAULT_ENGLISH_OCR_LEFT_ADJUST,
        ),
        ENGLISH_OCR_RIGHT_ADJUSTMENTS.get(
            char,
            DEFAULT_ENGLISH_OCR_RIGHT_ADJUST,
        ),
    ))


def character_pair_advance_adjustment(
    current: str,
    following: str | None,
) -> int:
    """返回相邻字符对对当前字符前进宽度的修正量。"""
    if following is None:
        return 0
    return _scale_metric(
        CHARACTER_PAIR_ADVANCE_ADJUSTMENTS.get(
            (current, following),
            0,
        )
    )


def character_ocr_visual_equivalents(char: str) -> frozenset[str]:
    """返回订单期望字符允许的、大小写归一后的 OCR 视觉结果。"""
    return frozenset({char.casefold()}) | ENGLISH_OCR_HIGH_RISK_EQUIVALENTS.get(
        char,
        frozenset(),
    )


def character_ocr_match_is_high_risk(
    expected: str,
    observed: str,
) -> bool:
    """判断一次已匹配的单字符结果是否使用了高风险视觉等价规则。"""
    observed_key = str(observed or "").casefold()
    return (
        observed_key != str(expected or "").casefold()
        and observed_key
        in ENGLISH_OCR_HIGH_RISK_EQUIVALENTS.get(expected, frozenset())
    )


def korean_ocr_visual_equivalents(char: str) -> frozenset[str]:
    """返回订单期望韩文字在当前位置允许的 OCR 视觉结果。"""
    return frozenset({str(char or "")}) | KOREAN_OCR_HIGH_RISK_EQUIVALENTS.get(
        char,
        frozenset(),
    )


def korean_ocr_text_matches(expected: str, observed: str) -> bool:
    """按订单字符位置比较韩文，并允许已配置的视觉等价字。"""
    expected_value = str(expected or "")
    observed_value = str(observed or "")
    if len(expected_value) != len(observed_value):
        return False
    return all(
        actual in korean_ocr_visual_equivalents(wanted)
        for wanted, actual in zip(expected_value, observed_value)
    )
