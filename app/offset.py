from decimal import Decimal as D
from app.errors import DomainError
from app.normalize import number


def _text_pair(value):
    text = str(value).strip()
    if text.startswith('±'):
        bound = abs(number(text[1:]))
        return -bound, bound
    inner = text.strip('[]() ')
    if ',' in inner:
        parts = [p for p in (p.strip() for p in inner.split(',')) if p]
        if len(parts) == 2:
            return number(parts[0]), number(parts[1])
    bound = abs(number(text))
    return -bound, bound


def level_offset(value):
    """检定给出的水位偏移范围，返回 (下限, 上限)。

    标量、单元素序列或 "0.03" 视为 ±|值|；二元序列、{"low","high"} 或 "a,b" 为闭区间。
    偏移是整天共用的系统差，不是逐测次独立误差。
    """
    if value is None:
        return D(0), D(0)
    if isinstance(value, str) and not value.strip():
        return D(0), D(0)
    if isinstance(value, dict):
        low = value.get('low', value.get('min'))
        high = value.get('high', value.get('max'))
        if low is None or high is None:
            raise DomainError("RANGE", "水位偏移范围需同时给出上下限")
        low, high = number(low), number(high)
    else:
        points = list(value) if isinstance(value, (list, tuple)) else _text_pair(value)
        if len(points) == 1:
            bound = abs(number(points[0]))
            low, high = -bound, bound
        elif len(points) == 2:
            low, high = number(points[0]), number(points[1])
        else:
            raise DomainError("RANGE", "水位偏移范围需为两个数值")
    if low > high:
        raise DomainError("RANGE", "水位偏移下限不能大于上限")
    return low, high


def from_params(params):
    for key in ('level_offset_m', 'level_offset', 'offset_m'):
        if key in params:
            return level_offset(params[key])
    return level_offset(None)
