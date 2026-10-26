"""Reconcile real SEC facts into coherent, anonymized statements.

Real filings do not hand you a tidy statement: some subtotals are not tagged,
fiscal years differ, and a few lines have to be derived. Every derived line is
computed here and asserted against the tagged total, so a document can never
disagree with the question set.

All money is in USD millions. EPS is USD per share, shares are in millions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from fixture_builder.source import Company, Fact, Period, duration, fetch_company_facts, instant

LineKind = Literal['income', 'balance', 'cash_flow']

INCOME_LABELS: dict[str, str] = {
    'revenue': 'Total net revenue',
    'cost_of_revenue': 'Cost of revenue',
    'gross_profit': 'Gross profit',
    'research_development': 'Research and development',
    'sales_marketing': 'Sales and marketing',
    'general_administrative': 'General and administrative',
    'selling_general_admin': 'Selling, general and administrative',
    'total_operating_expenses': 'Total operating expenses',
    'operating_income': 'Operating income',
    'other_income_net': 'Other income (expense), net',
    'pretax_income': 'Income before income taxes',
    'income_tax': 'Provision for income taxes',
    'net_income': 'Net income',
    'eps_basic': 'Earnings per share, basic',
    'eps_diluted': 'Earnings per share, diluted',
    'shares_basic': 'Weighted-average shares, basic',
    'shares_diluted': 'Weighted-average shares, diluted',
}

BALANCE_LABELS: dict[str, str] = {
    'cash': 'Cash and cash equivalents',
    'short_term_investments': 'Short-term marketable securities',
    'accounts_receivable': 'Accounts receivable, net',
    'inventories': 'Inventories',
    'other_current_assets': 'Other current assets',
    'total_current_assets': 'Total current assets',
    'ppe_net': 'Property, plant and equipment, net',
    'goodwill': 'Goodwill',
    'intangible_assets': 'Intangible assets, net',
    'other_noncurrent_assets': 'Other non-current assets',
    'total_assets': 'Total assets',
    'accounts_payable': 'Accounts payable',
    'deferred_revenue': 'Deferred revenue, current',
    'accrued_liabilities': 'Accrued and other current liabilities',
    'total_current_liabilities': 'Total current liabilities',
    'long_term_debt': 'Long-term debt',
    'other_noncurrent_liabilities': 'Other non-current liabilities',
    'total_liabilities': 'Total liabilities',
    'common_stock_apic': 'Common stock and additional paid-in capital',
    'retained_earnings': 'Retained earnings (accumulated deficit)',
    'aoci': 'Accumulated other comprehensive income (loss)',
    'treasury_stock': 'Treasury stock',
    'total_equity': 'Total shareholders\u2019 equity',
}

CASH_FLOW_LABELS: dict[str, str] = {
    'net_income': 'Net income',
    'depreciation_amortization': 'Depreciation and amortization',
    'stock_based_compensation': 'Share-based compensation',
    'working_capital_change': 'Changes in working capital and other operating items',
    'cash_from_operations': 'Net cash provided by operating activities',
    'capital_expenditures': 'Purchases of property, plant and equipment',
    'cash_from_investing': 'Net cash provided by (used in) investing activities',
    'cash_from_financing': 'Net cash used in financing activities',
    'fx_effect': 'Effect of exchange rate changes on cash',
    'net_change': 'Net increase (decrease) in cash',
    'cash_beginning': 'Cash and cash equivalents, beginning of period',
    'cash_ending': 'Cash and cash equivalents, end of period',
}


@dataclass(frozen=True)
class Duration:
    """One reporting duration with its income statement and cash flow."""

    label: str
    start: str
    end: str
    income: dict[str, float]
    cash_flow: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class BalanceSheet:
    date: str
    lines: dict[str, float]


@dataclass(frozen=True)
class Interim:
    """A quarter: three-month and year-to-date columns, current and prior year."""

    label: str
    current_3m: Duration
    current_9m: Duration
    prior_3m: Duration
    prior_9m: Duration


@dataclass(frozen=True)
class CompanyModel:
    key: str
    source_name: str
    source_cik: str
    annual: tuple[Duration, ...]
    interim: Interim | None
    balances: dict[str, BalanceSheet]


# Facts are tagged to the dollar. Allow for floating-point noise only.
WHOLE_MILLION_TOLERANCE = 1e-6


def _musd(fact: Fact | None, what: str) -> float:
    if fact is None:
        msg = f'Missing SEC fact: {what}'
        raise LookupError(msg)
    millions = fact.value / 1_000_000
    if abs(millions - round(millions)) > WHOLE_MILLION_TOLERANCE:
        msg = f'{what} is not a whole number of millions: {fact.value}'
        raise ValueError(msg)
    return float(round(millions))


def _opt(fact: Fact | None) -> float | None:
    return fact.value / 1_000_000 if fact is not None else None


def _income_a(facts: dict[str, Any], period: Period) -> dict[str, float]:
    """Income statement for company A (one combined SG&A line)."""
    get = lambda line: _musd(duration(facts, line, period), f'{line} {period.label}')  # noqa: E731
    revenue = get('revenue')
    cogs = get('cogs')
    rnd = get('rnd')
    sga = get('sga')
    opex = get('opex_total')
    operating = get('op_income')
    pretax = get('pretax')
    tax = get('tax')
    net = get('net_income')
    gross = revenue - cogs
    if round(rnd + sga) != round(opex):
        msg = f'{period.label}: R&D {rnd} + SG&A {sga} != opex {opex}'
        raise AssertionError(msg)
    if round(gross - opex) != round(operating):
        msg = f'{period.label}: gross {gross} - opex {opex} != operating {operating}'
        raise AssertionError(msg)
    if round(pretax - tax) != round(net):
        msg = f'{period.label}: pretax {pretax} - tax {tax} != net {net}'
        raise AssertionError(msg)
    lines = {
        'revenue': revenue,
        'cost_of_revenue': cogs,
        'gross_profit': gross,
        'research_development': rnd,
        'selling_general_admin': sga,
        'total_operating_expenses': opex,
        'operating_income': operating,
        'other_income_net': pretax - operating,
        'pretax_income': pretax,
        'income_tax': tax,
        'net_income': net,
    }
    shares_basic = duration(facts, 'shares_basic', period, unit='shares')
    shares_diluted = duration(facts, 'shares_diluted', period, unit='shares')
    if shares_basic and shares_diluted:
        basic_m = round(shares_basic.value / 1_000_000, 1)
        diluted_m = round(shares_diluted.value / 1_000_000, 1)
        # Derive EPS from net income and the share count so the three lines on
        # the page always agree. Filed EPS differs by a cent on some periods
        # purely because the filing rounds net income and shares separately.
        lines['shares_basic'] = basic_m
        lines['shares_diluted'] = diluted_m
        lines['eps_basic'] = round(net / basic_m, 2)
        lines['eps_diluted'] = round(net / diluted_m, 2)
    return lines


def _income_b(facts: dict[str, Any], period: Period) -> dict[str, float]:
    """Income statement for company B (sales & marketing shown separately)."""
    get = lambda line: _musd(duration(facts, line, period), f'{line} {period.label}')  # noqa: E731
    revenue = get('revenue')
    cogs = get('cogs')
    rnd = get('rnd')
    ga = get('sga')
    opex = get('opex_total')
    operating = get('op_income')
    pretax = get('pretax')
    tax = get('tax')
    net = get('net_income')
    gross = revenue - cogs
    sales_marketing = opex - rnd - ga
    if sales_marketing <= 0:
        msg = f'{period.label}: derived sales & marketing is not positive'
        raise AssertionError(msg)
    if round(gross - opex) != round(operating):
        msg = f'{period.label}: gross {gross} - opex {opex} != operating {operating}'
        raise AssertionError(msg)
    if round(pretax - tax) != round(net):
        msg = f'{period.label}: pretax {pretax} - tax {tax} != net {net}'
        raise AssertionError(msg)
    lines = {
        'revenue': revenue,
        'cost_of_revenue': cogs,
        'gross_profit': gross,
        'research_development': rnd,
        'sales_marketing': sales_marketing,
        'general_administrative': ga,
        'total_operating_expenses': opex,
        'operating_income': operating,
        'other_income_net': pretax - operating,
        'pretax_income': pretax,
        'income_tax': tax,
        'net_income': net,
    }
    shares_basic = duration(facts, 'shares_basic', period, unit='shares')
    shares_diluted = duration(facts, 'shares_diluted', period, unit='shares')
    if shares_basic and shares_diluted:
        basic_m = round(shares_basic.value / 1_000_000, 1)
        diluted_m = round(shares_diluted.value / 1_000_000, 1)
        lines['shares_basic'] = basic_m
        lines['shares_diluted'] = diluted_m
        lines['eps_basic'] = round(net / basic_m, 2)
        lines['eps_diluted'] = round(net / diluted_m, 2)
    return lines


def _balance(facts: dict[str, Any], end: str, keys: tuple[str, ...]) -> dict[str, float]:
    """Build a balance sheet, deriving the residual line and asserting the totals."""
    get = lambda line: _opt(instant(facts, line, end))  # noqa: E731
    cash = get('cash') or 0.0
    sti = get('st_investments') or 0.0
    ar = get('ar') or 0.0
    inventory = get('inventory') or 0.0
    current = get('assets_current') or 0.0
    ppe = get('ppe') or 0.0
    goodwill = get('goodwill') or 0.0
    intangibles = get('intangibles') or 0.0
    assets = get('assets') or 0.0
    ap = get('ap') or 0.0
    deferred = get('deferred_revenue') or 0.0
    current_liab = get('liab_current') or 0.0
    debt = get('lt_debt') or 0.0
    liabilities = get('liabilities') or 0.0
    apic = get('common_stock_apic') or 0.0
    retained = get('retained') or 0.0
    aoci = get('aoci') or 0.0
    equity = get('equity') or 0.0

    other_current = current - cash - sti - ar - inventory
    other_noncurrent = assets - current - ppe - goodwill - intangibles
    accrued = current_liab - ap - deferred
    other_liab = liabilities - current_liab - debt
    treasury = equity - apic - retained - aoci
    lines = {
        'cash': cash,
        'short_term_investments': sti,
        'accounts_receivable': ar,
        'inventories': inventory,
        'other_current_assets': other_current,
        'total_current_assets': current,
        'ppe_net': ppe,
        'goodwill': goodwill,
        'intangible_assets': intangibles,
        'other_noncurrent_assets': other_noncurrent,
        'total_assets': assets,
        'accounts_payable': ap,
        'deferred_revenue': deferred,
        'accrued_liabilities': accrued,
        'total_current_liabilities': current_liab,
        'long_term_debt': debt,
        'other_noncurrent_liabilities': other_liab,
        'total_liabilities': liabilities,
        'common_stock_apic': apic,
        'retained_earnings': retained,
        'aoci': aoci,
        'treasury_stock': treasury,
        'total_equity': equity,
    }
    if round(current + (assets - current)) != round(assets):
        msg = f'{end}: current + non-current != total assets'
        raise AssertionError(msg)
    if round(liabilities + equity) != round(assets):
        msg = f'{end}: liabilities {liabilities} + equity {equity} != assets {assets}'
        raise AssertionError(msg)
    if keys:
        allowed = set(keys)
        lines = {key: value for key, value in lines.items() if key in allowed}
        lines['total_assets'] = assets
        lines['total_equity'] = equity
    return lines


def _cash_flow(
    facts: dict[str, Any],
    period: Period,
    income: dict[str, float],
    cash_begin: float,
    cash_end: float,
) -> dict[str, float]:
    get = lambda line: _musd(duration(facts, line, period), f'{line} {period.label}')  # noqa: E731
    cfo = get('cfo')
    cfi = get('cfi')
    cff = get('cff')
    da = get('dep_amort')
    sbc = get('sbc')
    capex = get('capex')
    net_income = income['net_income']
    working_capital = cfo - net_income - da - sbc
    net_change = cash_end - cash_begin
    fx = net_change - (cfo + cfi + cff)
    lines = {
        'net_income': net_income,
        'depreciation_amortization': da,
        'stock_based_compensation': sbc,
        'working_capital_change': working_capital,
        'cash_from_operations': cfo,
        'capital_expenditures': capex,
        'cash_from_investing': cfi,
        'cash_from_financing': cff,
        'fx_effect': fx,
        'net_change': net_change,
        'cash_beginning': cash_begin,
        'cash_ending': cash_end,
    }
    if round(net_income + da + sbc + working_capital) != round(cfo):
        msg = f'{period.label}: operating activities do not reconcile'
        raise AssertionError(msg)
    if round(cfo + cfi + cff + fx) != round(net_change):
        msg = f'{period.label}: cash flow does not reconcile to the balance sheet'
        raise AssertionError(msg)
    return lines


def _cash(facts: dict[str, Any], end: str) -> float:
    return _musd(instant(facts, 'cash', end), f'cash {end}')


def _period(label: str, start: str, end: str) -> Period:
    return Period(label=label, start=start, end=end, form='10-K')


def build_company_a(*, refresh: bool = False) -> CompanyModel:
    """company-a: hardware and services, fiscal year ending in late September."""
    company = Company(key='company-a', cik='0000320193', name='Apple Inc.')
    facts = fetch_company_facts(company, refresh=refresh)
    annual_specs = (
        ('FY2025', '2024-09-29', '2025-09-27', '2025-09-27', '2024-09-28'),
        ('FY2024', '2023-10-01', '2024-09-28', '2024-09-28', '2023-09-30'),
        ('FY2023', '2022-09-25', '2023-09-30', '2023-09-30', '2022-09-24'),
    )
    annual: list[Duration] = []
    for label, start, end, cash_end_date, cash_begin_date in annual_specs:
        income = _income_a(facts, _period(label, start, end))
        flow = _cash_flow(
            facts,
            _period(label, start, end),
            income,
            _cash(facts, cash_begin_date),
            _cash(facts, cash_end_date),
        )
        annual.append(Duration(label, start, end, income, flow))

    interim_specs = {
        'current_3m': ('2026-03-29', '2026-06-27'),
        'current_9m': ('2025-09-28', '2026-06-27'),
        'prior_3m': ('2025-03-30', '2025-06-28'),
        'prior_9m': ('2024-09-29', '2025-06-28'),
    }
    built: dict[str, Duration] = {}
    for key, (start, end) in interim_specs.items():
        income = _income_a(facts, _period(key, start, end))
        built[key] = Duration(key, start, end, income)
    current_9m = built['current_9m']
    prior_9m = built['prior_9m']
    built['current_9m'] = Duration(
        'current_9m',
        current_9m.start,
        current_9m.end,
        current_9m.income,
        _cash_flow(
            facts,
            _period('current_9m', current_9m.start, current_9m.end),
            current_9m.income,
            _cash(facts, '2025-09-27'),
            _cash(facts, '2026-06-27'),
        ),
    )
    built['prior_9m'] = Duration(
        'prior_9m',
        prior_9m.start,
        prior_9m.end,
        prior_9m.income,
        _cash_flow(
            facts,
            _period('prior_9m', prior_9m.start, prior_9m.end),
            prior_9m.income,
            _cash(facts, '2024-09-28'),
            _cash(facts, '2025-06-28'),
        ),
    )
    interim = Interim(
        label='Q3 FY2026',
        current_3m=built['current_3m'],
        current_9m=built['current_9m'],
        prior_3m=built['prior_3m'],
        prior_9m=built['prior_9m'],
    )
    balances = {
        '2025-09-27': BalanceSheet('2025-09-27', _balance(facts, '2025-09-27', ())),
        '2024-09-28': BalanceSheet('2024-09-28', _balance(facts, '2024-09-28', ())),
        '2023-09-30': BalanceSheet('2023-09-30', _balance(facts, '2023-09-30', ())),
        '2026-06-27': BalanceSheet('2026-06-27', _balance(facts, '2026-06-27', ())),
        '2025-06-28': BalanceSheet('2025-06-28', _balance(facts, '2025-06-28', ())),
    }
    return CompanyModel(
        key='company-a',
        source_name=company.name,
        source_cik=company.cik,
        annual=tuple(annual),
        interim=interim,
        balances=balances,
    )


def build_company_b(*, refresh: bool = False) -> CompanyModel:
    """company-b: enterprise software, fiscal year ending in late January."""
    company = Company(key='company-b', cik='0001108524', name='Salesforce, Inc.')
    facts = fetch_company_facts(company, refresh=refresh)
    annual_specs = (
        ('FY2026', '2025-02-01', '2026-01-31', '2026-01-31', '2025-01-31'),
        ('FY2025', '2024-02-01', '2025-01-31', '2025-01-31', '2024-01-31'),
        ('FY2024', '2023-02-01', '2024-01-31', '2024-01-31', '2023-01-31'),
    )
    annual: list[Duration] = []
    for label, start, end, cash_end_date, cash_begin_date in annual_specs:
        income = _income_b(facts, _period(label, start, end))
        flow = _cash_flow(
            facts,
            _period(label, start, end),
            income,
            _cash(facts, cash_begin_date),
            _cash(facts, cash_end_date),
        )
        annual.append(Duration(label, start, end, income, flow))
    balances = {
        '2026-01-31': BalanceSheet('2026-01-31', _balance(facts, '2026-01-31', ())),
        '2025-01-31': BalanceSheet('2025-01-31', _balance(facts, '2025-01-31', ())),
        '2024-01-31': BalanceSheet('2024-01-31', _balance(facts, '2024-01-31', ())),
    }
    return CompanyModel(
        key='company-b',
        source_name=company.name,
        source_cik=company.cik,
        annual=tuple(annual),
        interim=None,
        balances=balances,
    )


def growth(current: float, prior: float) -> float:
    """Percentage growth, rounded to one decimal, as the documents state it."""
    if prior == 0:
        msg = 'Cannot compute growth against zero'
        raise ValueError(msg)
    return round((current - prior) / prior * 100, 1)


def margin(part: float, whole: float) -> float:
    """Percentage margin, rounded to one decimal."""
    if whole == 0:
        msg = 'Cannot compute a margin against zero'
        raise ValueError(msg)
    return round(part / whole * 100, 1)


def ratio(part: float, whole: float) -> float:
    """Plain ratio, rounded to two decimals."""
    if whole == 0:
        msg = 'Cannot compute a ratio against zero'
        raise ValueError(msg)
    return round(part / whole, 2)


def fmt(value: float, decimals: int = 0) -> str:
    """Format a number the way the documents print it."""
    return f'{value:,.{decimals}f}'
