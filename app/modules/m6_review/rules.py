from decimal import Decimal as D

# 严重程度：缺测 > 偏移不可行 > 跨容差待复核 > 确定超差 > 通过。
SEVERITY = {'PASS': 0, 'LIMIT': 1, 'REVIEW': 2, 'UNDEFINED': 3, 'GAP': 4}


def _row_code(row, tolerance):
    if row['state'] == '缺测':
        return 'GAP', '待补测'
    low = row.get('residual_low', row.get('residual'))
    high = row.get('residual_high', row.get('residual'))
    if low is None or high is None:
        return 'UNDEFINED', '待复核'
    # 只有整个可能范围都越过容差才算超差；范围跨容差或偏差方向不明则待复核。
    if low > tolerance or high < -tolerance:
        return 'LIMIT', '待复核'
    if low < -tolerance or high > tolerance:
        return 'REVIEW', '待复核'
    return 'PASS', '通过'


def evaluate(rows, tolerance):
    result = []
    for row in rows:
        code, state = _row_code(row, tolerance)
        result.append({**row, 'code': code, 'state': state})
    return result


def conclude(rows):
    """整体复核结论随水位偏移范围变化重算。"""
    severity = max((SEVERITY[r['code']] for r in rows), default=0)
    if severity >= SEVERITY['GAP']:
        return '待补测'
    if severity >= SEVERITY['LIMIT']:
        return '待复核'
    return '通过'
