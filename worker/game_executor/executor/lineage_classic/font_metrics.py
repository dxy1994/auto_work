"""天堂经典版 800x600 客户区中的玩家名字体宽度配置。"""

from types import MappingProxyType


# 这里记录的是“字符前进宽度”：当前字符单元起点到下一个字符单元起点，
# 包含字形右侧的固定字间距，不是明亮像素本身的包围盒宽度。
#
# 大写 A-Z 以及小写 a-x 已使用 2026-07-23 的实际交易请求截图标定；
# 其余小写字符先按同一套像素字体的字形结构配置，后续拿到对应样本时
# 只需调整此表。
ENGLISH_ADVANCE_WIDTHS = MappingProxyType({
    "A": 6,
    "B": 6,
    "C": 6,
    "D": 7,
    "E": 6,
    "F": 6,
    "G": 6,
    "H": 8,
    "I": 5,
    "J": 6,
    "K": 6,
    "L": 6,
    "M": 7,
    "N": 6,
    "O": 6,
    "P": 6,
    "Q": 7,
    "R": 6,
    "S": 6,
    "T": 6,
    "U": 6,
    "V": 6,
    "W": 6,
    "X": 6,
    "Y": 6,
    "Z": 6,
    "a": 6,
    "b": 6,
    "c": 6,
    "d": 6,
    "e": 6,
    "f": 6,
    "g": 7,
    "h": 8,
    "i": 5,
    "j": 6,
    "k": 7,
    "l": 5,
    "m": 6,
    "n": 6,
    "o": 6,
    "p": 6,
    "q": 7,
    "r": 5,
    "s": 6,
    "t": 5,
    "u": 6,
    "v": 6,
    "w": 6,
    "x": 6,
    "y": 6,
    "z": 6,
})

DEFAULT_ENGLISH_ADVANCE_WIDTH = 6
# 韩文字体暂按每个音节 13px 前进；连续韩文会整段交给韩文 OCR，
# 再仅保留识别结果中的韩文字符与订单姓名的韩文段比较。
KOREAN_ADVANCE_WIDTH = 13
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
    "O": frozenset({"o", "0"}),
    "o": frozenset({"o", "0"}),
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
    "g": frozenset({"g", "9"}),
    # 下列点阵字母的主体很小，英文模型可能只保留成相似标点。
    "r": frozenset({"r", ",", "."}),
    "S": frozenset({"s", "$"}),
    "s": frozenset({"s", "$"}),
    "T": frozenset({"t", "+"}),
    "t": frozenset({"t", "+"}),
    "X": frozenset({"x", "*"}),
    "x": frozenset({"x", "*"}),
    "Z": frozenset({"z", ":", ";"}),
    "z": frozenset({"z", ":", ";"}),
})

# 只保留上表明确配置过的 OCR 标点结果。订单昵称本身仍只允许英文和韩文；
# 未在对应期望字母等价集合中的标点不会通过匹配。
ENGLISH_OCR_ALLOWED_VISUAL_SYMBOLS = frozenset(
    visual
    for equivalents in ENGLISH_OCR_HIGH_RISK_EQUIVALENTS.values()
    for visual in equivalents
    if not visual.isalnum()
)

# 部分相邻字符会改变下一个字符的起点；值会加到前一个字符的前进宽度。
# 这不是 OCR 容错，而是依据实际交易请求截图标定的游戏字体排版数据。
CHARACTER_PAIR_ADVANCE_ADJUSTMENTS = MappingProxyType({
    # 2026-07-23 真实交易请求样本“킹차노스lokL”标定。
    ("l", "o"): -1,
    ("k", "L"): -2,
    ("t", "y"): 3,
    ("H", "M"): -2,
    ("M", "n"): -1,
})


def character_advance_width(char: str) -> int:
    """返回一个已支持英文或韩文字符的固定前进宽度。"""
    if "\uac00" <= char <= "\ud7a3" or "\u3131" <= char <= "\u318e":
        return KOREAN_ADVANCE_WIDTHS.get(char, KOREAN_ADVANCE_WIDTH)
    return ENGLISH_ADVANCE_WIDTHS.get(
        char,
        DEFAULT_ENGLISH_ADVANCE_WIDTH,
    )


def character_ocr_adjustments(char: str) -> tuple[int, int]:
    """返回字符单元转换成 OCR 裁剪框时的左右边界调整量。"""
    return (
        ENGLISH_OCR_LEFT_ADJUSTMENTS.get(
            char,
            DEFAULT_ENGLISH_OCR_LEFT_ADJUST,
        ),
        ENGLISH_OCR_RIGHT_ADJUSTMENTS.get(
            char,
            DEFAULT_ENGLISH_OCR_RIGHT_ADJUST,
        ),
    )


def character_pair_advance_adjustment(
    current: str,
    following: str | None,
) -> int:
    """返回相邻字符对对当前字符前进宽度的修正量。"""
    if following is None:
        return 0
    return CHARACTER_PAIR_ADVANCE_ADJUSTMENTS.get(
        (current, following),
        0,
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
