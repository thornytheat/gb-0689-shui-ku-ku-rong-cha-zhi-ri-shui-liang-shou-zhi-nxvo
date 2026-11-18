import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m5_budget.rules import day_budget
from app.modules.m4_storage.service import level_to_volume
from app.modules.m3_integrate.rules import integrate
C=[(D(100),D(0)),(D(102),D(30000))]
def p(time,level):return dict(station='S',time=instant(time),inflow=D(1),outflow=D(0),level=D(level))

def test_midnight_split():
    # TRAP-23
    x=integrate([p('2026-12-31T23:00:00+08:00','100'),p('2027-01-01T01:00:00+08:00','102')],D(2))[0];days=day_budget(x,C,level_to_volume);assert len(days)==2 and [r['in_m3'] for r in days]==[3600,3600]

def test_storage_conservation():
    x=integrate([p('2026-11-16T23:00:00+08:00','100'),p('2026-11-17T01:00:00+08:00','102')],D(2))[0];assert sum(r['storage_change'] for r in day_budget(x,C,level_to_volume))==30000

def test_partial_day_flagged():
    x=integrate([p('2026-11-16T00:00:00Z','100'),p('2026-11-16T01:00:00Z','101')],D(2))[0];assert day_budget(x,C,level_to_volume)[0]['state']=='缺测'

def test_empty():
    assert day_budget([],C,level_to_volume)==[]

def test_real_day_count(raw):
    assert len(run(raw,stop=5,persist=False)['budgets'])>=2

def test_real_missing_day(raw):
    assert any(x['state']=='缺测' for x in run(raw,stop=5,persist=False)['budgets'])

def test_real_daily_integral(raw):
    x=run(raw,stop=5,persist=False);assert abs(sum(D(y['in_m3']) for y in x['budgets'])-sum(D(y['in_m3']) for y in x['flows']))<D('.000000001')
import pytest


def test_knot_budget_range():
    from app.modules.m5_budget.rules import day_budget
    from app.modules.m4_storage.service import level_to_volume
    from app.modules.m3_integrate.rules import integrate
    curve = [(D(100), D(0)), (D(102), D(30000)), (D(105), D(100000))]
    def p(t, h):
        return dict(station='S', time=instant(t), inflow=D(2), outflow=D(1), level=D(h))
    flows, _ = integrate([p('2026-11-16T23:00:00+08:00', '101.8'), p('2026-11-17T01:00:00+08:00', '105')], D(2))
    point = day_budget(flows, curve, level_to_volume)[0]
    widened = day_budget(flows, curve, level_to_volume, (D('-0.02'), D('0.02')))[0]
    assert widened['residual_low'] < point['residual_low'] == point['residual_high']
    assert widened['residual_high'] > point['residual_high']


def test_offset_outside_curve_is_undefined():
    from app.modules.m5_budget.rules import day_budget
    from app.modules.m4_storage.service import level_to_volume
    from app.modules.m3_integrate.rules import integrate
    curve = [(D(100), D(0)), (D(102), D(30000))]
    def p(t, h):
        return dict(station='S', time=instant(t), inflow=D(1), outflow=D(0), level=D(h))
    flows, _ = integrate([p('2026-11-16T23:00:00+08:00', '101.99'), p('2026-11-17T01:00:00+08:00', '101.5')], D(2))
    day = day_budget(flows, curve, level_to_volume, (D('0.05'), D('0.1')))[0]
    assert day['residual_low'] is None and day['residual_high'] is None


def test_offset_parsing():
    from app.offset import level_offset
    assert level_offset(None) == (D(0), D(0))
    assert level_offset('0.03') == (D('-0.03'), D('0.03'))
    assert level_offset('±0.02') == (D('-0.02'), D('0.02'))
    assert level_offset('-0.02,0.03') == (D('-0.02'), D('0.03'))
    assert level_offset(['-0.02', '0.03']) == (D('-0.02'), D('0.03'))
    assert level_offset({'low': '-0.01', 'high': '0.04'}) == (D('-0.01'), D('0.04'))
    with pytest.raises(DomainError): level_offset('0.05,-0.01')

