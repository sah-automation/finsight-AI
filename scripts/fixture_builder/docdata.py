"""Deterministic, non-SEC data used in the sample documents.

The financial statements come from real SEC XBRL facts (see ``source.py`` and
``model.py``). Everything else in the fixture set - a budget, a ledger extract, a
bank statement, an invoice, board minutes and a regional split - is invented
here once, in one place.

Both the document writers and the question generator import this module, so a
number can never appear in a document and a different number in the answer key.
Every function is pure and every total is computed, not typed in twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fixture_builder.model import CompanyModel

# --- Budget vs actual -------------------------------------------------------

BUDGET_UNIT = 'USD millions'


@dataclass(frozen=True)
class BudgetRow:
    line: str
    budget: float
    actual: float

    @property
    def variance(self) -> float:
        return self.actual - self.budget

    @property
    def variance_pct(self) -> float:
        return round(self.variance / self.budget * 100, 1)


def budget_rows(model: CompanyModel) -> tuple[BudgetRow, ...]:
    """FY2025 plan against FY2025 actuals for company-a.

    The plan is a fixed, slightly conservative version of the actual result. The
    subtotals are computed from the plan lines so the sheet always adds up.
    """
    fy2025 = model.annual[0]
    income = fy2025.income
    plan_revenue = 410_000.0
    plan_cogs = 218_000.0
    plan_rnd = 34_000.0
    plan_sga = 27_000.0
    plan_gross = plan_revenue - plan_cogs
    plan_opex = plan_rnd + plan_sga
    plan_operating = plan_gross - plan_opex
    plan_net = 110_000.0
    return (
        BudgetRow('Total net revenue', plan_revenue, income['revenue']),
        BudgetRow('Cost of revenue', plan_cogs, income['cost_of_revenue']),
        BudgetRow('Gross profit', plan_gross, income['gross_profit']),
        BudgetRow('Research and development', plan_rnd, income['research_development']),
        BudgetRow('Selling, general and administrative', plan_sga, income['selling_general_admin']),
        BudgetRow('Total operating expenses', plan_opex, income['total_operating_expenses']),
        BudgetRow('Operating income', plan_operating, income['operating_income']),
        BudgetRow('Net income', plan_net, income['net_income']),
    )


# --- General ledger ---------------------------------------------------------

LEDGER_COLUMNS = (
    'entry_date',
    'account_code',
    'account_name',
    'cost_centre',
    'description',
    'debit',
    'credit',
)

LEDGER_PERIOD = ('2025-06-29', '2025-09-27')

# (date, account code, account name, cost centre, description, debit, credit)
LEDGER_ROWS: tuple[tuple[str, str, str, str, str, float, float], ...] = (
    ('2025-07-02', '6100', 'Software subscriptions', 'CC-100', 'Design suite renewal', 18400, 0),
    ('2025-07-03', '6200', 'Travel and entertainment', 'CC-200', 'Customer visit airfare', 2150, 0),
    ('2025-07-08', '6400', 'Marketing programs', 'CC-200', 'Regional campaign', 46000, 0),
    ('2025-07-10', '6300', 'Professional fees', 'CC-300', 'External audit fee', 82500, 0),
    ('2025-07-15', '6500', 'Office and facilities', 'CC-400', 'Office rent', 61200, 0),
    ('2025-07-18', '6100', 'Software subscriptions', 'CC-300', 'Analytics platform', 27900, 0),
    ('2025-07-22', '6200', 'Travel and entertainment', 'CC-100', 'Engineering offsite', 5480, 0),
    ('2025-07-25', '6400', 'Marketing programs', 'CC-200', 'Partner event', 31750, 0),
    ('2025-07-31', '6300', 'Professional fees', 'CC-100', 'Patent filing', 9600, 0),
    ('2025-08-04', '6500', 'Office and facilities', 'CC-400', 'Utilities', 7340, 0),
    ('2025-08-06', '6100', 'Software subscriptions', 'CC-200', 'Sales enablement tool', 12600, 0),
    ('2025-08-11', '6200', 'Travel and entertainment', 'CC-200', 'Sales conference', 14900, 0),
    ('2025-08-14', '6400', 'Marketing programs', 'CC-200', 'Digital advertising', 58300, 0),
    ('2025-08-19', '6300', 'Professional fees', 'CC-300', 'Tax advisory', 24000, 0),
    ('2025-08-21', '6500', 'Office and facilities', 'CC-400', 'Facilities maintenance', 3850, 0),
    ('2025-08-26', '6100', 'Software subscriptions', 'CC-100', 'Cloud compute', 44700, 0),
    ('2025-08-29', '6200', 'Travel and entertainment', 'CC-300', 'Audit committee travel', 1980, 0),
    ('2025-09-03', '6400', 'Marketing programs', 'CC-200', 'Product launch', 72400, 0),
    ('2025-09-05', '6300', 'Professional fees', 'CC-100', 'Recruitment fees', 16500, 0),
    ('2025-09-09', '6500', 'Office and facilities', 'CC-400', 'Security services', 5220, 0),
    ('2025-09-12', '6100', 'Software subscriptions', 'CC-300', 'ERP licence', 33800, 0),
    ('2025-09-16', '6200', 'Travel and entertainment', 'CC-100', 'Team offsite', 6750, 0),
    ('2025-09-19', '6400', 'Marketing programs', 'CC-200', 'Analyst briefing', 8900, 0),
    ('2025-09-23', '6300', 'Professional fees', 'CC-300', 'Legal fees', 41000, 0),
    ('2025-09-25', '6100', 'Software subscriptions', 'CC-100', 'Cloud compute', 39250, 0),
    ('2025-09-26', '6200', 'Travel and entertainment', 'CC-200', 'Sales conference', 12300, 0),
    ('2025-09-27', '6400', 'Marketing programs', 'CC-200', 'Media agency rebate', 0, 5000),
    ('2025-09-27', '6500', 'Office and facilities', 'CC-400', 'Landlord credit', 0, 2100),
)


def ledger_total(account_code: str) -> float:
    """Net debit (debits minus credits) for one account."""
    return sum(row[5] - row[6] for row in LEDGER_ROWS if row[1] == account_code)


def ledger_total_debits() -> float:
    return sum(row[5] for row in LEDGER_ROWS)


def ledger_total_credits() -> float:
    return sum(row[6] for row in LEDGER_ROWS)


def ledger_total_for_centre(cost_centre: str) -> float:
    return sum(row[5] - row[6] for row in LEDGER_ROWS if row[3] == cost_centre)


def ledger_count(account_code: str) -> int:
    return sum(1 for row in LEDGER_ROWS if row[1] == account_code)


# --- Bank statement ---------------------------------------------------------

BANK_NAME = 'Northbank National Association'
BANK_ACCOUNT_LABEL = 'Operating account ending 4471'
BANK_STATEMENT_PERIOD = ('September 28, 2025', 'June 27, 2026')

# (date, description, amount). Positive is money in, negative is money out.
BANK_TRANSACTIONS: tuple[tuple[str, str, float], ...] = (
    ('2026-04-03', 'Customer receipts', 112_400.00),
    ('2026-04-17', 'Payroll and benefits', -18_250.00),
    ('2026-05-08', 'Supplier payments', -82_600.00),
    ('2026-05-22', 'Income taxes', -4_800.00),
    ('2026-06-12', 'Interest received', 420.00),
    ('2026-06-24', 'Equipment purchases', -3_560.00),
)


def bank_opening_balance(model: CompanyModel) -> float:
    if model.interim is None:
        msg = 'Bank statement needs the interim cash flow'
        raise LookupError(msg)
    return model.interim.current_9m.cash_flow['cash_beginning']


def bank_closing_balance(model: CompanyModel) -> float:
    if model.interim is None:
        msg = 'Bank statement needs the interim cash flow'
        raise LookupError(msg)
    return model.interim.current_9m.cash_flow['cash_ending']


def bank_net_activity() -> float:
    return sum(amount for _, _, amount in BANK_TRANSACTIONS)


# --- Vendor invoice ---------------------------------------------------------

INVOICE_NUMBER = 'INV-2025-0842'
INVOICE_DATE = '2025-08-14'
INVOICE_DUE_DATE = '2025-09-13'
INVOICE_VENDOR = 'Cedar Ridge Logistics LLC'
INVOICE_CUSTOMER = 'Company A, Inc.'
INVOICE_PO = 'PO-6612'
INVOICE_TERMS = 'Net 30'
INVOICE_TAX_RATE = 0.08

# (description, quantity, unit price)
INVOICE_LINES: tuple[tuple[str, int, float], ...] = (
    ('Inbound freight, September close', 1, 1_240.00),
    ('Warehouse handling, pallet storage', 12, 265.00),
    ('Returns processing', 1, 560.00),
)


def invoice_subtotal() -> float:
    return round(sum(quantity * price for _, quantity, price in INVOICE_LINES), 2)


def invoice_tax() -> float:
    return round(invoice_subtotal() * INVOICE_TAX_RATE, 2)


def invoice_total() -> float:
    return round(invoice_subtotal() + invoice_tax(), 2)


# --- Board minutes ----------------------------------------------------------

BOARD_MEETING_DATE = '2025-10-14'
BOARD_NEXT_MEETING = '2026-01-13'
BOARD_ATTENDEES = (
    'Chair of the Board',
    'Chief Executive Officer',
    'Chief Financial Officer',
    'Chair of the Audit Committee',
    'Head of Internal Audit',
)
BOARD_APOLOGIES = ('Non-Executive Director 1', 'Non-Executive Director 2')
BOARD_QUORUM = 'Five of seven directors present; quorum met.'

# (decision, owner, effective date)
BOARD_DECISIONS: tuple[tuple[str, str, str], ...] = (
    (
        'Approve an additional share repurchase authorisation of $90 billion',
        'Chief Financial Officer',
        '2025-10-15',
    ),
    ('Raise the quarterly dividend to $0.26 per share', 'Chief Financial Officer', '2025-11-14'),
    (
        'Hold general and administrative headcount flat through the first half of FY2026',
        'Chief Executive Officer',
        '2025-11-01',
    ),
)


def board_headline_revenue(model: CompanyModel) -> float:
    return model.annual[0].income['revenue']


def board_headline_net_income(model: CompanyModel) -> float:
    return model.annual[0].income['net_income']


# --- Company B revenue by region -------------------------------------------

REGION_COLUMNS = ('region', 'fy2024', 'fy2025', 'fy2026')

# (region, FY2024, FY2025, FY2026) in USD millions. Fixed here so both the CSV
# and the question set read the same numbers.
REGION_DATA: tuple[tuple[str, float, float, float], ...] = (
    ('Americas', 23_180.0, 25_180.0, 27_614.0),
    ('Europe', 7_340.0, 7_980.0, 8_720.0),
    ('Asia Pacific', 4_337.0, 4_735.0, 5_191.0),
)


def region_rows(model: CompanyModel) -> tuple[tuple[str, float, float, float], ...]:
    """Check the regional split sums to company-b's reported revenue each year."""
    by_label = {period.label: period.income['revenue'] for period in model.annual}
    for index, label in enumerate(('FY2024', 'FY2025', 'FY2026')):
        added = sum(row[index + 1] for row in REGION_DATA)
        if round(added) != round(by_label[label]):
            msg = f'{label}: regional split {added} != reported revenue {by_label[label]}'
            raise AssertionError(msg)
    return REGION_DATA


def region_value(region: str, fiscal_year: str) -> float:
    index = {'fy2024': 1, 'fy2025': 2, 'fy2026': 3}[fiscal_year]
    for row in REGION_DATA:
        if row[0] == region:
            return row[index]
    msg = f'Unknown region: {region}'
    raise KeyError(msg)


# --- Guidance (invented, stated in the interim report) ---------------------

GUIDANCE = {
    'revenue_low': 445_000.0,
    'revenue_high': 455_000.0,
    'gross_margin_low': 46.0,
    'gross_margin_high': 47.0,
    'tax_rate_low': 15.0,
    'tax_rate_high': 16.0,
}
