from decimal import Decimal as D
from datetime import datetime, timedelta, timezone
from collections import defaultdict

ZONE = timezone(timedelta(hours=8))


def _shifted_change(levels, curve, interpolate, shift):
    total = D(0)
    for start_level, end_level in levels:
        total += interpolate(end_level + shift, curve) - interpolate(start_level + shift, curve)
    return total


def _residual_range(levels, curve, interpolate, residual, offset):
    """同一偏移量整天共用，收支差随偏移分段线性变化。

    在可行偏移区间的两端及曲线折点对应的偏移处取值，取最小/最大即为可能范围。
    偏移后水位越出曲线范围时，该偏移不可行；全部不可行则返回 (None, None)。
    """
    low, high = offset
    if (low == 0 and high == 0) or not levels:
        return residual, residual
    values = [v for pair in levels for v in pair]
    floor = max(low, curve[0][0] - min(values))
    ceil = min(high, curve[-1][0] - max(values))
    if floor > ceil:
        return None, None
    checks = {floor, ceil}
    for knot, _ in curve:
        for level in values:
            candidate = knot - level
            if floor <= candidate <= ceil:
                checks.add(candidate)
    zero = _shifted_change(levels, curve, interpolate, D(0))
    base = residual - zero
    results = [base + _shifted_change(levels, curve, interpolate, shift) for shift in checks]
    return min(results), max(results)


def day_budget(flows, curve, interpolate, offset=(D(0), D(0))):
    buckets = defaultdict(lambda: {'in_m3': D(0), 'out_m3': D(0), 'storage_change': D(0), 'coverage_hours': D(0), 'levels': []})
    for part in flows:
        left, right = part['left'], part['right']
        start, end = part['start'], part['end']
        duration = D(str((end - start).total_seconds()))
        cursor = start

        def at(t, key):
            return left[key] + (right[key] - left[key]) * D(str((t - start).total_seconds())) / duration

        while cursor < end:
            local = cursor.astimezone(ZONE)
            midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time(), ZONE)
            stop = min(end, midnight)
            seconds = D(str((stop - cursor).total_seconds()))
            b = buckets[(part['station'], local.date().isoformat())]
            b['in_m3'] += (at(cursor, 'inflow') + at(stop, 'inflow')) / 2 * seconds
            b['out_m3'] += (at(cursor, 'outflow') + at(stop, 'outflow')) / 2 * seconds
            b['storage_change'] += interpolate(at(stop, 'level'), curve) - interpolate(at(cursor, 'level'), curve)
            b['levels'].append((at(cursor, 'level'), at(stop, 'level')))
            b['coverage_hours'] += seconds / 3600
            cursor = stop
    result = []
    for (station, day), values in sorted(buckets.items()):
        levels = values.pop('levels')
        residual = values['storage_change'] - values['in_m3'] + values['out_m3']
        low, high = _residual_range(levels, curve, interpolate, residual, offset)
        result.append({'station': station, 'date': day, **values,
                       'residual': residual, 'residual_low': low, 'residual_high': high,
                       'state': '完整' if values['coverage_hours'] == 24 else '缺测'})
    return result
