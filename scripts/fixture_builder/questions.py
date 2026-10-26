"""Generate the golden question set from the same model as the documents.

Every expected value is computed here from the reconciled statements or from the
fixed fixture data in ``docdata``. Nothing is typed in twice, so a question can
never disagree with the document it cites.

Run ``uv run python scripts/fixture_builder`` to write both the documents and
these files.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fixture_builder import docdata, yamlout
from fixture_builder.model import growth, margin

if TYPE_CHECKING:
    from fixture_builder.model import CompanyModel

OUTPUT_DIR = Path('tests/golden/questions')

DOC_A = 'pdf__company-a__2025-FY__annual-report.pdf'
DOC_A_Q3 = 'pdf__company-a__2026-Q3__interim-report.pdf'
DOC_A_DRAFT = 'pdf__company-a__2025-FY__annual-report-draft.pdf'
DOC_B = 'pdf__company-b__2026-FY__annual-report.pdf'
DOC_BANK = 'scan__company-a__2026-Q3__bank-statement.pdf'
DOC_INVOICE = 'image__company-a__2025-FY__vendor-invoice.png'
DOC_BUDGET = 'xlsx__company-a__2025-FY__budget-vs-actual.xlsx'
DOC_LEDGER = 'csv__company-a__2025-FY__q4-ledger.csv'
DOC_BOARD = 'docx__company-a__2025-FY__board-notes.docx'
DOC_REGIONS = 'csv__company-b__2026-FY__revenue-by-region.csv'

# (document, page) -> section heading recorded by the document writer
T_SELECTED_A = 'Selected financial data'
T_HIGHLIGHTS_A = 'Fiscal 2025 highlights'
T_MDA_A = 'Management discussion and analysis'
T_RATIOS_A = 'Key ratios'
T_INCOME_A = 'Consolidated statements of operations'
T_EPS_A = 'Earnings per share'
T_EPS_B = 'Earnings per share'
T_BS_A = 'Consolidated balance sheets'
T_CF_A = 'Consolidated statements of cash flows'
T_SUBSEQUENT_A = 'Subsequent events'
T_Q3_MDA = 'Third quarter and year to date'
T_Q3_RATIOS = 'Quarterly ratios'
T_Q3_INCOME = 'Condensed consolidated statements of operations'
T_Q3_BS = 'Condensed consolidated balance sheets'
T_Q3_CF = 'Condensed consolidated statements of cash flows'
T_Q3_OUTLOOK = '2. Outlook'
T_DRAFT_HEADLINE = 'Preliminary headline figures'
T_DRAFT_REVISIONS = 'Revision log'
T_SELECTED_B = 'Selected financial data'
T_HIGHLIGHTS_B = 'Fiscal 2026 highlights'
T_MDA_B = 'Management discussion and analysis'
T_INCOME_B = 'Consolidated statements of operations'
T_BS_B = 'Consolidated balance sheets'
T_CF_B = 'Consolidated statements of cash flows'
T_BUDGET = 'Budget vs Actual sheet'
T_ASSUMPTIONS = 'Assumptions sheet'
T_LEDGER = 'General ledger extract'
T_BANK_SUMMARY = 'Account summary'
T_BANK_TXNS = 'Transaction detail'
T_INVOICE_TOTAL = 'Invoice totals'
T_INVOICE_LINES = 'Invoice lines'
T_ATTENDANCE = 'Attendance'
T_CAPITAL = '2. Capital return'
T_RISKS = '3. Principal risks'
T_ACTIONS = '5. Actions'
T_REGIONS = 'Revenue by region'


def money(value: float, unit: str = 'million', decimals: int = 0) -> dict[str, Any]:
    return {'value': f'{value:.{decimals}f}', 'currency': 'USD', 'unit': unit}


def pct(value: float) -> dict[str, Any]:
    return {'value': f'{value:.1f}', 'currency': None, 'unit': 'percent'}


def count(value: int) -> dict[str, Any]:
    return {'value': str(int(value)), 'currency': None, 'unit': 'count'}


def cite(document: str, page: int, table: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {'document': document, 'page': page}
    if table is not None:
        entry['table'] = table
    return entry


def q(
    qid: str,
    question: str,
    *,
    category: str,
    difficulty: str,
    role: str,
    company: str,
    answer: str | None,
    numbers: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    tags: list[str],
    notes: str = '',
    insufficient: bool = False,
    denied: bool = False,
) -> dict[str, Any]:
    expected: dict[str, Any] = {
        'answer': answer,
        'numbers': numbers,
        'citations': citations,
        'insufficient_data': insufficient,
    }
    if denied:
        expected['access_denied'] = True
    entry: dict[str, Any] = {
        'id': qid,
        'question': question,
        'category': category,
        'difficulty': difficulty,
        'role': role,
        'company': company,
        'expected': expected,
        'tags': tags,
    }
    if notes:
        entry['notes'] = notes
    return entry


def _insufficient(
    qid: str,
    question: str,
    *,
    role: str = 'corporate_finance_planners',
    company: str = 'company-a',
    tags: list[str],
    notes: str = '',
) -> dict[str, Any]:
    return q(
        qid,
        question,
        category='financials',
        difficulty='easy',
        role=role,
        company=company,
        answer=None,
        numbers=[],
        citations=[],
        tags=tags,
        notes=notes or 'No document in the fixture set contains this figure.',
        insufficient=True,
    )


def _denied(
    qid: str,
    question: str,
    *,
    category: str,
    role: str,
    company: str = 'company-a',
    tags: list[str],
    notes: str,
) -> dict[str, Any]:
    return q(
        qid,
        question,
        category=category,
        difficulty='easy',
        role=role,
        company=company,
        answer=None,
        numbers=[],
        citations=[],
        tags=tags,
        notes=notes,
        denied=True,
    )


def _revenue_questions(model: CompanyModel) -> list[dict[str, Any]]:
    a25, a24, a23 = model.annual
    current, prior, oldest = a25.income, a24.income, a23.income
    items: list[dict[str, Any]] = []

    for index, (fy, values, page, table) in enumerate(
        (
            ('FY2025', current, 4, T_INCOME_A),
            ('FY2024', prior, 4, T_INCOME_A),
            ('FY2023', oldest, 4, T_INCOME_A),
        )
    ):
        value = values['revenue']
        items.append(
            q(
                f'rev-{index + 1:03d}',
                f'What was total net revenue in {fy}?',
                category='financials',
                difficulty='easy',
                role='corporate_finance_planners',
                company='company-a',
                answer=f'Total net revenue in {fy} was ${value:,.0f} million.',
                numbers=[money(value)],
                citations=[cite(DOC_A, page, table)],
                tags=['revenue', 'single_document'],
            )
        )

    g25 = growth(current['revenue'], prior['revenue'])
    g24 = growth(prior['revenue'], oldest['revenue'])
    items.append(
        q(
            'rev-004',
            'By what percentage did total net revenue grow in FY2025 compared with FY2024?',
            category='metrics',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=(
                f'Total net revenue grew {g25:.1f}% in FY2025, from ${prior["revenue"]:,.0f} million '
                f'to ${current["revenue"]:,.0f} million.'
            ),
            numbers=[pct(g25)],
            citations=[cite(DOC_A, 2, T_SELECTED_A), cite(DOC_A, 3, T_MDA_A)],
            tags=['revenue', 'growth', 'derived'],
        )
    )
    items.append(
        q(
            'rev-005',
            'How much did revenue grow in FY2024 compared with FY2023, in percentage terms?',
            category='metrics',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=(
                f'Total net revenue grew {g24:.1f}% in FY2024, from ${oldest["revenue"]:,.0f} million '
                f'to ${prior["revenue"]:,.0f} million.'
            ),
            numbers=[pct(g24)],
            citations=[cite(DOC_A, 2, T_SELECTED_A)],
            tags=['revenue', 'growth', 'derived'],
        )
    )

    if model.interim is None:
        return items
    q3_3m = model.interim.current_3m.income
    q3_3m_prior = model.interim.prior_3m.income
    q3_9m = model.interim.current_9m.income
    q3_9m_prior = model.interim.prior_9m.income

    for qid, label, value, page, table in (
        ('rev-006', 'the three months ended June 27, 2026', q3_3m['revenue'], 3, T_Q3_INCOME),
        ('rev-007', 'the nine months ended June 27, 2026', q3_9m['revenue'], 3, T_Q3_INCOME),
        ('rev-008', 'the three months ended June 28, 2025', q3_3m_prior['revenue'], 3, T_Q3_INCOME),
    ):
        items.append(
            q(
                qid,
                f'What was total net revenue for {label}?',
                category='financials',
                difficulty='easy',
                role='corporate_finance_planners',
                company='company-a',
                answer=f'Total net revenue for {label} was ${value:,.0f} million.',
                numbers=[money(value)],
                citations=[cite(DOC_A_Q3, page, table)],
                tags=['revenue', 'quarterly', 'single_document'],
            )
        )

    g_q3 = growth(q3_3m['revenue'], q3_3m_prior['revenue'])
    g_9m = growth(q3_9m['revenue'], q3_9m_prior['revenue'])
    items.append(
        q(
            'rev-009',
            'How fast did third-quarter revenue grow year over year?',
            category='metrics',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'Third-quarter revenue grew {g_q3:.1f}% to ${q3_3m["revenue"]:,.0f} million, from '
                f'${q3_3m_prior["revenue"]:,.0f} million a year earlier.'
            ),
            numbers=[pct(g_q3)],
            citations=[cite(DOC_A_Q3, 2, T_Q3_MDA)],
            tags=['revenue', 'growth', 'quarterly', 'derived'],
        )
    )
    items.append(
        q(
            'rev-010',
            'What was the year-to-date revenue growth at the end of the third quarter of fiscal 2026?',
            category='metrics',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'Year-to-date revenue grew {g_9m:.1f}% to ${q3_9m["revenue"]:,.0f} million, from '
                f'${q3_9m_prior["revenue"]:,.0f} million.'
            ),
            numbers=[pct(g_9m)],
            citations=[cite(DOC_A_Q3, 2, T_Q3_MDA)],
            tags=['revenue', 'growth', 'quarterly', 'derived'],
        )
    )
    items.append(
        q(
            'rev-011',
            'Which fiscal year had the highest total net revenue?',
            category='financials',
            difficulty='easy',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'FY2025 had the highest revenue at ${current["revenue"]:,.0f} million, ahead of '
                f'${prior["revenue"]:,.0f} million in FY2024 and ${oldest["revenue"]:,.0f} million in FY2023.'
            ),
            numbers=[money(current['revenue'])],
            citations=[cite(DOC_A, 2, T_SELECTED_A)],
            tags=['revenue', 'comparison', 'derived'],
        )
    )
    difference = current['revenue'] - prior['revenue']
    items.append(
        q(
            'rev-012',
            'How much more revenue did FY2025 produce than FY2024 in dollar terms?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=(
                f'FY2025 revenue was ${difference:,.0f} million higher than FY2024 '
                f'(${current["revenue"]:,.0f} million against ${prior["revenue"]:,.0f} million).'
            ),
            numbers=[money(difference)],
            citations=[cite(DOC_A, 2, T_SELECTED_A)],
            tags=['revenue', 'comparison', 'derived'],
        )
    )

    return items


def build_questions(
    model_a: CompanyModel, model_b: CompanyModel
) -> dict[str, list[dict[str, Any]]]:
    a25, a24, a23 = model_a.annual
    b26, b25, _ = model_b.annual
    a = a25.income
    a_prior = a24.income
    a_oldest = a23.income
    b = b26.income
    b_prior = b25.income
    bs = model_a.balances['2025-09-27'].lines
    bs_q3 = model_a.balances['2026-06-27'].lines
    cf = a25.cash_flow
    b_cf = b26.cash_flow
    b_bs = model_b.balances['2026-01-31'].lines

    if model_a.interim is None:
        msg = 'question generator needs the interim period'
        raise LookupError(msg)
    interim = model_a.interim
    q3_3m = interim.current_3m.income
    q3_9m = interim.current_9m.income
    q3_cf = interim.current_9m.cash_flow

    groups: dict[str, list[dict[str, Any]]] = {}

    # --- revenue ------------------------------------------------------------
    revenue = _revenue_questions(model_a)
    for label, value, page in (('FY2026', b['revenue'], 4), ('FY2025', b_prior['revenue'], 4)):
        revenue.append(
            q(
                f'rev-{len(revenue) + 1:03d}',
                f'What was Company B total net revenue in {label}?',
                category='financials',
                difficulty='easy',
                role='corporate_finance_planners',
                company='company-b',
                answer=f'Company B total net revenue in {label} was ${value:,.0f} million.',
                numbers=[money(value)],
                citations=[cite(DOC_B, page, T_INCOME_B)],
                tags=['revenue', 'company-b', 'single_document'],
            )
        )
    groups['revenue'] = revenue

    # --- margins ------------------------------------------------------------
    margins: list[dict[str, Any]] = []

    def add_margin(
        qid: str,
        question: str,
        value: float,
        *,
        answer: str,
        citations: list[dict[str, Any]],
        difficulty: str = 'medium',
        company: str = 'company-a',
        role: str = 'corporate_finance_planners',
        tags: list[str] | None = None,
    ) -> None:
        margins.append(
            q(
                qid,
                question,
                category='metrics',
                difficulty=difficulty,
                role=role,
                company=company,
                answer=answer,
                numbers=[pct(value)],
                citations=citations,
                tags=tags or ['margin', 'derived'],
            )
        )

    gm25 = margin(a['gross_profit'], a['revenue'])
    gm24 = margin(a_prior['gross_profit'], a_prior['revenue'])
    add_margin(
        'mar-001',
        'What was the gross margin in FY2025?',
        gm25,
        answer=f'Gross margin in FY2025 was {gm25:.1f}% (gross profit ${a["gross_profit"]:,.0f} million on revenue ${a["revenue"]:,.0f} million).',
        citations=[cite(DOC_A, 3, T_RATIOS_A)],
    )
    add_margin(
        'mar-002',
        'What was the gross margin in FY2024?',
        gm24,
        answer=f'Gross margin in FY2024 was {gm24:.1f}%.',
        citations=[cite(DOC_A, 3, T_RATIOS_A)],
    )
    om25 = margin(a['operating_income'], a['revenue'])
    add_margin(
        'mar-003',
        'What was the operating margin in FY2025?',
        om25,
        answer=f'Operating margin in FY2025 was {om25:.1f}% (operating income ${a["operating_income"]:,.0f} million).',
        citations=[cite(DOC_A, 3, T_RATIOS_A)],
    )
    nm25 = margin(a['net_income'], a['revenue'])
    add_margin(
        'mar-004',
        'What was the net margin in FY2025?',
        nm25,
        answer=f'Net margin in FY2025 was {nm25:.1f}%.',
        citations=[cite(DOC_A, 3, T_RATIOS_A)],
    )
    tax25 = margin(a['income_tax'], a['pretax_income'])
    add_margin(
        'mar-005',
        'What was the effective tax rate in FY2025?',
        tax25,
        answer=f'The effective tax rate in FY2025 was {tax25:.1f}% (tax ${a["income_tax"]:,.0f} million on pre-tax income ${a["pretax_income"]:,.0f} million).',
        citations=[cite(DOC_A, 3, T_RATIOS_A), cite(DOC_A, 7, '3. Income taxes')],
    )
    tax24 = margin(a_prior['income_tax'], a_prior['pretax_income'])
    add_margin(
        'mar-006',
        'What was the effective tax rate in FY2024?',
        tax24,
        answer=f'The effective tax rate in FY2024 was {tax24:.1f}%.',
        citations=[cite(DOC_A, 3, T_RATIOS_A)],
    )
    gm_q3 = margin(q3_3m['gross_profit'], q3_3m['revenue'])
    add_margin(
        'mar-007',
        'What was the gross margin for the third quarter of fiscal 2026?',
        gm_q3,
        answer=f'The third-quarter gross margin was {gm_q3:.1f}%.',
        citations=[cite(DOC_A_Q3, 2, T_Q3_RATIOS)],
        role='executive_leadership',
        tags=['margin', 'quarterly', 'derived'],
    )
    nm_9m = margin(q3_9m['net_income'], q3_9m['revenue'])
    add_margin(
        'mar-008',
        'What was the year-to-date net margin at the end of the third quarter of fiscal 2026?',
        nm_9m,
        answer=f'The year-to-date net margin was {nm_9m:.1f}%.',
        citations=[cite(DOC_A_Q3, 2, T_Q3_RATIOS)],
        tags=['margin', 'quarterly', 'derived'],
    )
    add_margin(
        'mar-009',
        'What was Company B gross margin in FY2026?',
        margin(b['gross_profit'], b['revenue']),
        answer=f'Company B gross margin in FY2026 was {margin(b["gross_profit"], b["revenue"]):.1f}%.',
        citations=[cite(DOC_B, 3, T_MDA_B)],
        company='company-b',
        tags=['margin', 'company-b', 'derived'],
    )
    add_margin(
        'mar-010',
        'What was Company B operating margin in FY2026?',
        margin(b['operating_income'], b['revenue']),
        answer=f'Company B operating margin in FY2026 was {margin(b["operating_income"], b["revenue"]):.1f}%.',
        citations=[cite(DOC_B, 3, T_MDA_B)],
        company='company-b',
        tags=['margin', 'company-b', 'derived'],
    )
    add_margin(
        'mar-011',
        'What was Company B net margin in FY2026?',
        margin(b['net_income'], b['revenue']),
        answer=f'Company B net margin in FY2026 was {margin(b["net_income"], b["revenue"]):.1f}%.',
        citations=[cite(DOC_B, 3, T_MDA_B)],
        company='company-b',
        tags=['margin', 'company-b', 'derived'],
    )
    best_year = max(
        (
            ('FY2025', gm25),
            ('FY2024', gm24),
            ('FY2023', margin(a_oldest['gross_profit'], a_oldest['revenue'])),
        ),
        key=lambda item: item[1],
    )
    add_margin(
        'mar-012',
        'In which of the three reported fiscal years was gross margin highest?',
        best_year[1],
        answer=f'{best_year[0]} had the highest gross margin at {best_year[1]:.1f}%.',
        citations=[cite(DOC_A, 3, T_RATIOS_A)],
        difficulty='hard',
        role='executive_leadership',
        tags=['margin', 'comparison', 'derived'],
    )
    groups['margins'] = margins

    # --- balance sheet ------------------------------------------------------
    balance: list[dict[str, Any]] = []

    def add_balance(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        page: int,
        table: str,
        unit: str = 'million',
        decimals: int = 0,
        tags: list[str] | None = None,
        role: str = 'corporate_finance_planners',
        document: str = DOC_A,
        as_of: str = '27 September 2025',
    ) -> None:
        rendered = f'{value:,.{decimals}f}'
        balance.append(
            q(
                qid,
                question,
                category='financials',
                difficulty='easy',
                role=role,
                company='company-a',
                answer=f'{label} stood at ${rendered} million at {as_of}.',
                numbers=[money(value, unit, decimals)],
                citations=[cite(document, page, table)],
                tags=tags or ['balance_sheet', 'single_document'],
            )
        )

    add_balance(
        'bal-001',
        'What were total assets at 27 September 2025?',
        bs['total_assets'],
        label='Total assets',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-002',
        'What were total liabilities at 27 September 2025?',
        bs['total_liabilities'],
        label='Total liabilities',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-003',
        'What was total shareholders equity at 27 September 2025?',
        bs['total_equity'],
        label='Total shareholders equity',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-004',
        'How much cash and cash equivalents did the company hold at 27 September 2025?',
        bs['cash'],
        label='Cash and cash equivalents',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-005',
        'How much was held in short-term marketable securities at 27 September 2025?',
        bs['short_term_investments'],
        label='Short-term marketable securities',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-006',
        'What were total current assets at 27 September 2025?',
        bs['total_current_assets'],
        label='Total current assets',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-007',
        'What were total current liabilities at 27 September 2025?',
        bs['total_current_liabilities'],
        label='Total current liabilities',
        page=5,
        table=T_BS_A,
    )
    add_balance(
        'bal-008',
        'What was long-term debt at 27 September 2025?',
        bs['long_term_debt'],
        label='Long-term debt',
        page=5,
        table=T_BS_A,
    )
    balance.append(
        q(
            'bal-009',
            'What was the retained earnings balance at 27 September 2025?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'Retained earnings were an accumulated deficit of ${abs(bs["retained_earnings"]):,.0f} million at 27 September 2025, shown as ({abs(bs["retained_earnings"]):,.0f}) on the balance sheet.',
            numbers=[money(bs['retained_earnings'])],
            citations=[cite(DOC_A, 5, T_BS_A)],
            tags=['balance_sheet', 'negative', 'sign'],
        )
    )
    add_balance(
        'bal-010',
        'What were total assets at 27 June 2026?',
        bs_q3['total_assets'],
        label='Total assets',
        page=4,
        table=T_Q3_BS,
        document=DOC_A_Q3,
        as_of='27 June 2026',
        tags=['balance_sheet', 'quarterly', 'single_document'],
    )
    add_balance(
        'bal-011',
        'What was total shareholders equity at 27 June 2026?',
        bs_q3['total_equity'],
        label='Total shareholders equity',
        page=4,
        table=T_Q3_BS,
        document=DOC_A_Q3,
        as_of='27 June 2026',
        tags=['balance_sheet', 'quarterly', 'single_document'],
    )
    balance.append(
        q(
            'bal-012',
            'How much did total assets change between 27 September 2025 and 27 June 2026?',
            category='financials',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'Total assets increased by ${bs_q3["total_assets"] - bs["total_assets"]:,.0f} million, from '
                f'${bs["total_assets"]:,.0f} million to ${bs_q3["total_assets"]:,.0f} million.'
            ),
            numbers=[money(bs_q3['total_assets'] - bs['total_assets'])],
            citations=[cite(DOC_A, 5, T_BS_A), cite(DOC_A_Q3, 4, T_Q3_BS)],
            tags=['balance_sheet', 'comparison', 'derived'],
        )
    )
    groups['balance_sheet'] = balance

    # --- cash flow ----------------------------------------------------------
    cash: list[dict[str, Any]] = []

    def add_cash(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        page: int,
        table: str,
        negative: bool = False,
        tags: list[str] | None = None,
        role: str = 'corporate_finance_planners',
        document: str = DOC_A,
    ) -> None:
        shown = abs(value) if negative else value
        answer = f'{label} was ${shown:,.0f} million.'
        cash.append(
            q(
                qid,
                question,
                category='financials',
                difficulty='easy',
                role=role,
                company='company-a',
                answer=answer,
                numbers=[money(value) if not negative else money(-value)],
                citations=[cite(document, page, table)],
                tags=tags or ['cash_flow', 'single_document'],
            )
        )

    add_cash(
        'cfl-001',
        'What was net cash provided by operating activities in FY2025?',
        cf['cash_from_operations'],
        label='Net cash provided by operating activities',
        page=6,
        table=T_CF_A,
    )
    add_cash(
        'cfl-002',
        'What was net cash provided by investing activities in FY2025?',
        cf['cash_from_investing'],
        label='Net cash provided by investing activities',
        page=6,
        table=T_CF_A,
    )
    cash[-1]['expected']['numbers'] = [money(cf['cash_from_investing'])]
    add_cash(
        'cfl-003',
        'How much cash did financing activities use in FY2025?',
        abs(cf['cash_from_financing']),
        label='Net cash used in financing activities',
        page=6,
        table=T_CF_A,
        negative=True,
        tags=['cash_flow', 'negative'],
    )
    add_cash(
        'cfl-004',
        'How much did the company spend on purchases of property, plant and equipment in FY2025?',
        cf['capital_expenditures'],
        label='Capital expenditure',
        page=6,
        table=T_CF_A,
    )
    add_cash(
        'cfl-005',
        'What was depreciation and amortisation in FY2025?',
        cf['depreciation_amortization'],
        label='Depreciation and amortisation',
        page=6,
        table=T_CF_A,
    )
    add_cash(
        'cfl-006',
        'What was share-based compensation in FY2025?',
        cf['stock_based_compensation'],
        label='Share-based compensation',
        page=6,
        table=T_CF_A,
    )
    add_cash(
        'cfl-007',
        'What was the net increase in cash in FY2025?',
        cf['net_change'],
        label='Net increase in cash',
        page=6,
        table=T_CF_A,
    )
    add_cash(
        'cfl-008',
        'What was the cash balance at the beginning of FY2025?',
        cf['cash_beginning'],
        label='Cash at the beginning of the year',
        page=6,
        table=T_CF_A,
    )
    add_cash(
        'cfl-009',
        'What was net cash provided by operating activities in the first nine months of fiscal 2026?',
        q3_cf['cash_from_operations'],
        label='Net cash provided by operating activities',
        page=5,
        table=T_Q3_CF,
        document=DOC_A_Q3,
        tags=['cash_flow', 'quarterly'],
    )
    add_cash(
        'cfl-010',
        'How much cash did financing activities use in the first nine months of fiscal 2026?',
        abs(q3_cf['cash_from_financing']),
        label='Net cash used in financing activities',
        page=5,
        table=T_Q3_CF,
        negative=True,
        document=DOC_A_Q3,
        tags=['cash_flow', 'quarterly', 'negative'],
    )
    add_cash(
        'cfl-011',
        'What was the net increase in cash in the first nine months of fiscal 2026?',
        q3_cf['net_change'],
        label='Net increase in cash',
        page=5,
        table=T_Q3_CF,
        document=DOC_A_Q3,
        tags=['cash_flow', 'quarterly'],
    )
    free_cash_flow = cf['cash_from_operations'] - cf['capital_expenditures']
    cash.append(
        q(
            'cfl-012',
            'What was free cash flow in FY2025, calculated as operating cash flow less capital expenditure?',
            category='metrics',
            difficulty='hard',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'Free cash flow was ${free_cash_flow:,.0f} million: operating cash flow of '
                f'${cf["cash_from_operations"]:,.0f} million less capital expenditure of '
                f'${cf["capital_expenditures"]:,.0f} million.'
            ),
            numbers=[money(free_cash_flow)],
            citations=[cite(DOC_A, 6, T_CF_A)],
            tags=['cash_flow', 'derived', 'free_cash_flow'],
            notes='The documents do not define free cash flow; the note records the definition used so the expected value is reproducible.',
        )
    )
    groups['cash_flow'] = cash

    # --- budget vs actual ---------------------------------------------------
    budget_rows = docdata.budget_rows(model_a)
    by_line = {row.line: row for row in budget_rows}
    budget: list[dict[str, Any]] = []

    def add_budget(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        unit: str = 'million',
        decimals: int = 0,
        sheet: str = T_BUDGET,
        tags: list[str] | None = None,
        difficulty: str = 'easy',
    ) -> None:
        rendered = f'{value:,.{decimals}f}'
        shown = f'{rendered}%' if unit == 'percent' else f'${rendered} million'
        budget.append(
            q(
                qid,
                question,
                category='forecasts',
                difficulty=difficulty,
                role='corporate_finance_planners',
                company='company-a',
                answer=f'{label} was {shown}.',
                numbers=[money(value, unit, decimals) if unit != 'percent' else pct(value)],
                citations=[cite(DOC_BUDGET, 1, sheet)],
                tags=tags or ['budget', 'single_document'],
            )
        )

    revenue_row = by_line['Total net revenue']
    add_budget(
        'bud-001',
        'What was the FY2025 revenue budget?',
        revenue_row.budget,
        label='The FY2025 revenue budget',
    )
    add_budget(
        'bud-002',
        'What was actual FY2025 revenue in the budget-versus-actual workbook?',
        revenue_row.actual,
        label='Actual FY2025 revenue',
    )
    add_budget(
        'bud-003',
        'What was the revenue variance against budget in FY2025?',
        revenue_row.variance,
        label='The FY2025 revenue variance',
    )
    add_budget(
        'bud-004',
        'What was the revenue variance against budget in percentage terms?',
        revenue_row.variance_pct,
        label='The FY2025 revenue variance',
        unit='percent',
        decimals=1,
    )
    net_row = by_line['Net income']
    add_budget(
        'bud-005',
        'What was the FY2025 net income budget?',
        net_row.budget,
        label='The FY2025 net income budget',
    )
    add_budget(
        'bud-006',
        'How far did net income beat budget in FY2025?',
        net_row.variance,
        label='The FY2025 net income variance',
        difficulty='medium',
    )
    op_row = by_line['Operating income']
    add_budget(
        'bud-007',
        'What was the operating income variance against budget in FY2025?',
        op_row.variance,
        label='The FY2025 operating income variance',
        difficulty='medium',
    )
    sga_row = by_line['Selling, general and administrative']
    add_budget(
        'bud-008',
        'By what percentage did selling, general and administrative spend exceed budget?',
        sga_row.variance_pct,
        label='The FY2025 SG&A variance',
        unit='percent',
        decimals=1,
        difficulty='medium',
    )
    largest = max(budget_rows, key=lambda row: row.variance)
    budget.append(
        q(
            'bud-009',
            'Which line item has the largest favourable variance in absolute dollars?',
            category='forecasts',
            difficulty='hard',
            role='executive_leadership',
            company='company-a',
            answer=f'{largest.line} has the largest favourable variance at ${largest.variance:,.0f} million.',
            numbers=[money(largest.variance)],
            citations=[cite(DOC_BUDGET, 1, T_BUDGET)],
            tags=['budget', 'comparison', 'derived'],
        )
    )
    budget.append(
        q(
            'bud-010',
            'How many line items are compared in the budget-versus-actual sheet?',
            category='forecasts',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'The sheet compares {len(budget_rows)} line items.',
            numbers=[count(len(budget_rows))],
            citations=[cite(DOC_BUDGET, 1, T_BUDGET)],
            tags=['budget', 'metadata'],
        )
    )
    budget.append(
        q(
            'bud-011',
            'Which currency and unit does the budget workbook use?',
            category='forecasts',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-a',
            answer='The workbook reports all amounts in USD millions.',
            numbers=[],
            citations=[cite(DOC_BUDGET, 1, T_ASSUMPTIONS)],
            tags=['budget', 'metadata', 'units'],
            notes='Unit answer has no numeric value; the citation must still resolve.',
        )
    )
    groups['budget_vs_actual'] = budget

    # --- ledger -------------------------------------------------------------
    ledger: list[dict[str, Any]] = []

    def add_ledger(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        difficulty: str = 'medium',
        tags: list[str] | None = None,
    ) -> None:
        ledger.append(
            q(
                qid,
                question,
                category='financials',
                difficulty=difficulty,
                role='audit_compliance',
                company='company-a',
                answer=f'{label} stood at ${value:,.2f}.',
                numbers=[money(value, '1', 2)],
                citations=[cite(DOC_LEDGER, 1, T_LEDGER)],
                tags=tags or ['ledger', 'derived', 'aggregation'],
            )
        )

    add_ledger(
        'led-001',
        'What was the net debit for account 6400, Marketing programs, in the fourth quarter of fiscal 2025, after deducting credits?',
        docdata.ledger_total('6400'),
        label='The net debit for account 6400',
    )
    add_ledger(
        'led-002',
        'What was the total net debit for account 6100, Software subscriptions?',
        docdata.ledger_total('6100'),
        label='The net debit for account 6100',
    )
    add_ledger(
        'led-003',
        'What was the net debit for cost centre CC-200, after deducting credits?',
        docdata.ledger_total_for_centre('CC-200'),
        label='The net debit for cost centre CC-200',
    )
    add_ledger(
        'led-004',
        'What was the total of all debits in the ledger extract?',
        docdata.ledger_total_debits(),
        label='Total debits',
    )
    add_ledger(
        'led-005',
        'What was the total of all credits in the ledger extract?',
        docdata.ledger_total_credits(),
        label='Total credits',
    )
    net_ledger = docdata.ledger_total_debits() - docdata.ledger_total_credits()
    add_ledger(
        'led-006',
        'What was the net spend in the ledger extract, debits less credits?',
        net_ledger,
        label='Net spend',
    )
    ledger.append(
        q(
            'led-007',
            'How many entries are posted to account 6100?',
            category='financials',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'Account 6100 has {docdata.ledger_count("6100")} entries.',
            numbers=[count(docdata.ledger_count('6100'))],
            citations=[cite(DOC_LEDGER, 1, T_LEDGER)],
            tags=['ledger', 'count'],
        )
    )
    largest_debit = max(docdata.LEDGER_ROWS, key=lambda row: row[5])
    ledger.append(
        q(
            'led-008',
            'What is the largest single debit in the ledger extract?',
            category='financials',
            difficulty='medium',
            role='audit_compliance',
            company='company-a',
            answer=f'The largest single debit was ${largest_debit[5]:,.2f} for {largest_debit[4]} on {largest_debit[0]}.',
            numbers=[money(largest_debit[5], '1', 2)],
            citations=[cite(DOC_LEDGER, 1, T_LEDGER)],
            tags=['ledger', 'max', 'derived'],
        )
    )
    best_centre = max(
        sorted({row[3] for row in docdata.LEDGER_ROWS}),
        key=docdata.ledger_total_for_centre,
    )
    ledger.append(
        q(
            'led-009',
            'Which cost centre has the highest net debit, after deducting credits?',
            category='financials',
            difficulty='hard',
            role='audit_compliance',
            company='company-a',
            answer=f'Cost centre {best_centre} has the highest net debit at ${docdata.ledger_total_for_centre(best_centre):,.2f}.',
            numbers=[money(docdata.ledger_total_for_centre(best_centre), '1', 2)],
            citations=[cite(DOC_LEDGER, 1, T_LEDGER)],
            tags=['ledger', 'comparison', 'derived'],
        )
    )
    ledger.append(
        q(
            'led-010',
            'What delimiter separates the columns in the ledger file?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The ledger uses a semicolon (;) as the column delimiter.',
            numbers=[],
            citations=[cite(DOC_LEDGER, 1, T_LEDGER)],
            tags=['ledger', 'metadata', 'parsing'],
            notes='Tests delimiter detection, not arithmetic.',
        )
    )
    groups['ledger'] = ledger

    # --- bank statement -----------------------------------------------------
    opening = docdata.bank_opening_balance(model_a)
    closing = docdata.bank_closing_balance(model_a)
    total_credits = sum(amount for _, _, amount in docdata.BANK_TRANSACTIONS if amount > 0)
    total_debits = sum(-amount for _, _, amount in docdata.BANK_TRANSACTIONS if amount < 0)
    bank: list[dict[str, Any]] = []

    def add_bank(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        table: str = T_BANK_SUMMARY,
        difficulty: str = 'medium',
        tags: list[str] | None = None,
    ) -> None:
        bank.append(
            q(
                qid,
                question,
                category='financials',
                difficulty=difficulty,
                role='audit_compliance',
                company='company-a',
                answer=f'{label} stood at ${value:,.2f}.',
                numbers=[money(value, '1', 2)],
                citations=[cite(DOC_BANK, 1, table)],
                tags=tags or ['bank_statement', 'ocr', 'single_document'],
            )
        )

    add_bank(
        'bnk-001',
        'What was the closing balance on the bank statement?',
        closing,
        label='The closing balance',
    )
    add_bank(
        'bnk-002',
        'What was the opening balance on the bank statement?',
        opening,
        label='The opening balance',
    )
    add_bank(
        'bnk-003',
        'What were total credits on the bank statement?',
        total_credits,
        label='Total credits',
    )
    add_bank(
        'bnk-004',
        'What were total debits on the bank statement?',
        total_debits,
        label='Total debits',
    )
    add_bank(
        'bnk-005',
        'What was the net movement in the account over the statement period?',
        closing - opening,
        label='The net movement',
        difficulty='medium',
    )
    largest_in = max(docdata.BANK_TRANSACTIONS, key=lambda row: row[2])
    bank.append(
        q(
            'bnk-006',
            'What was the largest single credit on the bank statement?',
            category='financials',
            difficulty='medium',
            role='audit_compliance',
            company='company-a',
            answer=f'The largest single credit was ${largest_in[2]:,.2f} on {largest_in[0]} for {largest_in[1]}.',
            numbers=[money(largest_in[2], '1', 2)],
            citations=[cite(DOC_BANK, 1, T_BANK_TXNS)],
            tags=['bank_statement', 'ocr', 'max', 'derived'],
        )
    )
    bank.append(
        q(
            'bnk-007',
            'What date does the bank statement period end on?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The statement period ends on June 27, 2026.',
            numbers=[],
            citations=[cite(DOC_BANK, 1, T_BANK_SUMMARY)],
            tags=['bank_statement', 'ocr', 'metadata'],
        )
    )
    bank.append(
        q(
            'bnk-008',
            'Which account does the bank statement cover?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'The statement covers the treasury sweep account ending {docdata.BANK_ACCOUNT_LABEL.split()[-1]}.',
            numbers=[],
            citations=[cite(DOC_BANK, 1, T_BANK_SUMMARY)],
            tags=['bank_statement', 'ocr', 'metadata'],
        )
    )
    groups['bank_statement'] = bank

    # --- invoice ------------------------------------------------------------
    invoice: list[dict[str, Any]] = []

    def add_invoice(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        table: str = T_INVOICE_TOTAL,
        difficulty: str = 'easy',
        tags: list[str] | None = None,
    ) -> None:
        invoice.append(
            q(
                qid,
                question,
                category='financials',
                difficulty=difficulty,
                role='audit_compliance',
                company='company-a',
                answer=f'{label} is ${value:,.2f}.',
                numbers=[money(value, '1', 2)],
                citations=[cite(DOC_INVOICE, 1, table)],
                tags=tags or ['invoice', 'ocr', 'single_document'],
            )
        )

    add_invoice(
        'inv-001',
        'What is the total amount due on the vendor invoice?',
        docdata.invoice_total(),
        label='The total amount due',
    )
    add_invoice(
        'inv-002',
        'What is the sales tax amount on the vendor invoice?',
        docdata.invoice_tax(),
        label='The sales tax',
    )
    add_invoice(
        'inv-003',
        'What is the subtotal before tax on the vendor invoice?',
        docdata.invoice_subtotal(),
        label='The subtotal',
    )
    invoice.append(
        q(
            'inv-004',
            'What is the invoice number?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'The invoice number is {docdata.INVOICE_NUMBER}.',
            numbers=[],
            citations=[cite(DOC_INVOICE, 1, T_INVOICE_TOTAL)],
            tags=['invoice', 'ocr', 'metadata'],
        )
    )
    invoice.append(
        q(
            'inv-005',
            'When is the invoice due?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'The invoice is due on {docdata.INVOICE_DUE_DATE} under {docdata.INVOICE_TERMS} terms.',
            numbers=[],
            citations=[cite(DOC_INVOICE, 1, T_INVOICE_TOTAL)],
            tags=['invoice', 'ocr', 'metadata'],
        )
    )
    warehouse_quantity = docdata.INVOICE_LINES[1][1]
    invoice.append(
        q(
            'inv-006',
            'How many units of warehouse handling were billed?',
            category='financials',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'{warehouse_quantity} units of warehouse handling were billed at ${docdata.INVOICE_LINES[1][2]:,.2f} each.',
            numbers=[count(warehouse_quantity)],
            citations=[cite(DOC_INVOICE, 1, T_INVOICE_LINES)],
            tags=['invoice', 'ocr', 'line_item'],
        )
    )
    groups['invoice'] = invoice

    # --- board notes --------------------------------------------------------
    board: list[dict[str, Any]] = []
    board.append(
        q(
            'brd-001',
            'What quarterly dividend per share did the finance committee recommend?',
            category='decisions',
            difficulty='easy',
            role='executive_leadership',
            company='company-a',
            answer='The committee recommended raising the quarterly dividend to $0.26 per share, effective 2025-11-14.',
            numbers=[money(0.26, '1', 2)],
            citations=[cite(DOC_BOARD, 1, T_CAPITAL)],
            tags=['board_notes', 'docx', 'dividend'],
        )
    )
    board.append(
        q(
            'brd-002',
            'How large was the additional share repurchase authorisation approved by the committee?',
            category='decisions',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer='The committee approved an additional share repurchase authorisation of $90 billion.',
            numbers=[money(90.0, 'billion')],
            citations=[cite(DOC_BOARD, 1, T_CAPITAL)],
            tags=['board_notes', 'docx', 'capital_return'],
        )
    )
    board.append(
        q(
            'brd-003',
            'When is the next finance committee meeting?',
            category='decisions',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'The next meeting is scheduled for {docdata.BOARD_NEXT_MEETING}.',
            numbers=[],
            citations=[cite(DOC_BOARD, 1, T_ATTENDANCE)],
            tags=['board_notes', 'docx', 'metadata'],
        )
    )
    board.append(
        q(
            'brd-004',
            'How many directors attended the finance committee meeting?',
            category='decisions',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'{len(docdata.BOARD_ATTENDEES)} directors are listed as attending, and the minutes state that five of seven were present.',
            numbers=[count(len(docdata.BOARD_ATTENDEES))],
            citations=[cite(DOC_BOARD, 1, T_ATTENDANCE)],
            tags=['board_notes', 'docx', 'count'],
        )
    )
    board.append(
        q(
            'brd-005',
            'Which principal risk is listed first in the minutes?',
            category='risks',
            difficulty='easy',
            role='executive_leadership',
            company='company-a',
            answer='The first principal risk is foreign exchange volatility affecting reported revenue.',
            numbers=[],
            citations=[cite(DOC_BOARD, 1, T_RISKS)],
            tags=['board_notes', 'docx', 'risk'],
        )
    )
    board.append(
        q(
            'brd-006',
            'Who owns the action to circulate the revised capital return policy?',
            category='decisions',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The Chief Financial Officer owns that action, due 2025-10-31.',
            numbers=[],
            citations=[cite(DOC_BOARD, 1, T_ACTIONS)],
            tags=['board_notes', 'docx', 'action'],
        )
    )
    board.append(
        q(
            'brd-007',
            'When is the fiscal 2026 operating plan due?',
            category='decisions',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-a',
            answer='The operating plan is due on 28 November 2025.',
            numbers=[],
            citations=[cite(DOC_BOARD, 1, '4. Fiscal 2026 plan')],
            tags=['board_notes', 'docx', 'planning'],
        )
    )
    board.append(
        q(
            'brd-008',
            'What is the headcount plan for general and administrative roles in the first half of fiscal 2026?',
            category='decisions',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer='General and administrative headcount is held flat through the first half of fiscal 2026.',
            numbers=[],
            citations=[cite(DOC_BOARD, 1, '4. Fiscal 2026 plan'), cite(DOC_BOARD, 1, T_CAPITAL)],
            tags=['board_notes', 'docx', 'planning'],
        )
    )
    groups['board_notes'] = board

    # --- company B ----------------------------------------------------------
    company_b: list[dict[str, Any]] = []

    def add_b(
        qid: str,
        question: str,
        value: float,
        *,
        label: str,
        page: int,
        table: str,
        decimals: int = 0,
        tags: list[str] | None = None,
    ) -> None:
        rendered = f'{value:,.{decimals}f}'
        company_b.append(
            q(
                qid,
                question,
                category='financials',
                difficulty='easy',
                role='corporate_finance_planners',
                company='company-b',
                answer=f'{label} stood at ${rendered} million.',
                numbers=[money(value, 'million', decimals)],
                citations=[cite(DOC_B, page, table)],
                tags=tags or ['company-b', 'single_document'],
            )
        )

    add_b(
        'cmb-001',
        'What was Company B net income in FY2026?',
        b['net_income'],
        label='Company B net income',
        page=4,
        table=T_INCOME_B,
    )
    add_b(
        'cmb-002',
        'What was Company B gross profit in FY2026?',
        b['gross_profit'],
        label='Company B gross profit',
        page=4,
        table=T_INCOME_B,
    )
    add_b(
        'cmb-003',
        'What was Company B sales and marketing expense in FY2026?',
        b['sales_marketing'],
        label='Company B sales and marketing expense',
        page=4,
        table=T_INCOME_B,
    )
    add_b(
        'cmb-004',
        'What was Company B general and administrative expense in FY2026?',
        b['general_administrative'],
        label='Company B general and administrative expense',
        page=4,
        table=T_INCOME_B,
    )
    add_b(
        'cmb-005',
        'What was Company B research and development expense in FY2026?',
        b['research_development'],
        label='Company B research and development expense',
        page=4,
        table=T_INCOME_B,
    )
    add_b(
        'cmb-006',
        'What were Company B total assets at 31 January 2026?',
        b_bs['total_assets'],
        label='Company B total assets',
        page=5,
        table=T_BS_B,
    )
    add_b(
        'cmb-007',
        'What was Company B goodwill at 31 January 2026?',
        b_bs['goodwill'],
        label='Company B goodwill',
        page=5,
        table=T_BS_B,
    )
    add_b(
        'cmb-008',
        'What was Company B deferred revenue at 31 January 2026?',
        b_bs['deferred_revenue'],
        label='Company B deferred revenue',
        page=5,
        table=T_BS_B,
    )
    add_b(
        'cmb-009',
        'What was Company B net cash provided by operating activities in FY2026?',
        b_cf['cash_from_operations'],
        label='Company B operating cash flow',
        page=6,
        table=T_CF_B,
    )
    add_b(
        'cmb-010',
        'What was Company B capital expenditure in FY2026?',
        b_cf['capital_expenditures'],
        label='Company B capital expenditure',
        page=6,
        table=T_CF_B,
    )
    company_b.append(
        q(
            'cmb-011',
            'What was Company B diluted earnings per share in FY2026?',
            category='metrics',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-b',
            answer=f'Company B diluted earnings per share was ${b["eps_diluted"]:.2f}.',
            numbers=[money(b['eps_diluted'], '1', 2)],
            citations=[cite(DOC_B, 4, T_EPS_B)],
            tags=['company-b', 'eps'],
        )
    )
    company_b.append(
        q(
            'cmb-012',
            'How fast did Company B revenue grow in FY2026?',
            category='metrics',
            difficulty='medium',
            role='executive_leadership',
            company='company-b',
            answer=f'Company B revenue grew {growth(b["revenue"], b_prior["revenue"]):.1f}% in FY2026, from ${b_prior["revenue"]:,.0f} million to ${b["revenue"]:,.0f} million.',
            numbers=[pct(growth(b['revenue'], b_prior['revenue']))],
            citations=[cite(DOC_B, 2, T_SELECTED_B), cite(DOC_B, 3, T_MDA_B)],
            tags=['company-b', 'growth', 'derived'],
        )
    )
    groups['company_b'] = company_b

    # --- comparisons --------------------------------------------------------
    comparisons: list[dict[str, Any]] = []
    comparisons.append(
        q(
            'cmp-001',
            'Which company reported higher revenue, Company A in FY2025 or Company B in FY2026?',
            category='metrics',
            difficulty='easy',
            role='executive_leadership',
            company='both',
            answer=f'Company A reported higher revenue at ${a["revenue"]:,.0f} million, compared with ${b["revenue"]:,.0f} million for Company B.',
            numbers=[money(a['revenue'])],
            citations=[cite(DOC_A, 4, T_INCOME_A), cite(DOC_B, 4, T_INCOME_B)],
            tags=['comparison', 'cross_company', 'derived'],
        )
    )
    ratio_ab = round(a['revenue'] / b['revenue'], 2)
    comparisons.append(
        q(
            'cmp-002',
            'How many times larger is Company A revenue than Company B revenue?',
            category='metrics',
            difficulty='hard',
            role='executive_leadership',
            company='both',
            answer=f'Company A revenue is {ratio_ab:.2f} times Company B revenue (${a["revenue"]:,.0f} million compared with ${b["revenue"]:,.0f} million).',
            numbers=[{'value': f'{ratio_ab:.2f}', 'currency': None, 'unit': 'ratio'}],
            citations=[cite(DOC_A, 4, T_INCOME_A), cite(DOC_B, 4, T_INCOME_B)],
            tags=['comparison', 'cross_company', 'derived'],
        )
    )
    comparisons.append(
        q(
            'cmp-003',
            'Which company has the higher gross margin?',
            category='metrics',
            difficulty='medium',
            role='executive_leadership',
            company='both',
            answer=f'Company B has the higher gross margin at {margin(b["gross_profit"], b["revenue"]):.1f}%, compared with {gm25:.1f}% for Company A.',
            numbers=[pct(margin(b['gross_profit'], b['revenue']))],
            citations=[cite(DOC_A, 3, T_RATIOS_A), cite(DOC_B, 3, T_MDA_B)],
            tags=['comparison', 'cross_company', 'margin', 'derived'],
        )
    )
    difference_ab = a['revenue'] - b['revenue']
    comparisons.append(
        q(
            'cmp-004',
            'What is the difference in revenue between Company A FY2025 and Company B FY2026?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='both',
            answer=f'Company A reported ${difference_ab:,.0f} million more revenue than Company B.',
            numbers=[money(difference_ab)],
            citations=[cite(DOC_A, 4, T_INCOME_A), cite(DOC_B, 4, T_INCOME_B)],
            tags=['comparison', 'cross_company', 'derived'],
        )
    )
    comparisons.append(
        q(
            'cmp-005',
            'What is the difference in net income between Company A FY2025 and Company B FY2026?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='both',
            answer=f'Company A earned ${a["net_income"] - b["net_income"]:,.0f} million more net income than Company B.',
            numbers=[money(a['net_income'] - b['net_income'])],
            citations=[cite(DOC_A, 4, T_INCOME_A), cite(DOC_B, 4, T_INCOME_B)],
            tags=['comparison', 'cross_company', 'derived'],
        )
    )
    rd_a = margin(a['research_development'], a['revenue'])
    rd_b = margin(b['research_development'], b['revenue'])
    spender = 'Company B' if rd_b > rd_a else 'Company A'
    comparisons.append(
        q(
            'cmp-006',
            'Which company spends more on research and development as a share of revenue?',
            category='metrics',
            difficulty='hard',
            role='corporate_finance_planners',
            company='both',
            answer=f'{spender} spends more on research and development as a share of revenue ({rd_b:.1f}% for Company B against {rd_a:.1f}% for Company A).',
            numbers=[pct(max(rd_a, rd_b))],
            citations=[cite(DOC_A, 4, T_INCOME_A), cite(DOC_B, 4, T_INCOME_B)],
            tags=['comparison', 'cross_company', 'derived'],
        )
    )
    comparisons.append(
        q(
            'cmp-007',
            'How much revenue did Company B earn in Europe in FY2026?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-b',
            answer=f'Company B earned ${docdata.region_value("Europe", "fy2026"):,.0f} million in Europe in FY2026.',
            numbers=[money(docdata.region_value('Europe', 'fy2026'))],
            citations=[cite(DOC_REGIONS, 1, T_REGIONS)],
            tags=['comparison', 'csv', 'region'],
        )
    )
    comparisons.append(
        q(
            'cmp-008',
            'How much revenue did Company B earn in Asia Pacific in FY2026?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-b',
            answer=f'Company B earned ${docdata.region_value("Asia Pacific", "fy2026"):,.0f} million in Asia Pacific in FY2026.',
            numbers=[money(docdata.region_value('Asia Pacific', 'fy2026'))],
            citations=[cite(DOC_REGIONS, 1, T_REGIONS)],
            tags=['comparison', 'csv', 'region'],
        )
    )
    americas_share = margin(docdata.region_value('Americas', 'fy2026'), b['revenue'])
    comparisons.append(
        q(
            'cmp-009',
            'What share of Company B FY2026 revenue came from the Americas?',
            category='metrics',
            difficulty='hard',
            role='executive_leadership',
            company='company-b',
            answer=f'The Americas contributed {americas_share:.1f}% of Company B FY2026 revenue (${docdata.region_value("Americas", "fy2026"):,.0f} million of ${b["revenue"]:,.0f} million).',
            numbers=[pct(americas_share)],
            citations=[cite(DOC_REGIONS, 1, T_REGIONS), cite(DOC_B, 4, T_INCOME_B)],
            tags=['comparison', 'csv', 'region', 'derived'],
        )
    )
    region_increase = docdata.region_value('Americas', 'fy2026') - docdata.region_value(
        'Americas', 'fy2024'
    )
    comparisons.append(
        q(
            'cmp-010',
            'How much did Americas revenue increase between FY2024 and FY2026?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-b',
            answer=f'Americas revenue increased by ${region_increase:,.0f} million, from ${docdata.region_value("Americas", "fy2024"):,.0f} million to ${docdata.region_value("Americas", "fy2026"):,.0f} million.',
            numbers=[money(region_increase)],
            citations=[cite(DOC_REGIONS, 1, T_REGIONS)],
            tags=['comparison', 'csv', 'region', 'derived'],
        )
    )
    groups['comparisons'] = comparisons

    # --- citations ----------------------------------------------------------
    citations: list[dict[str, Any]] = []
    citations.append(
        q(
            'cit-001',
            'On which page of the annual report is the consolidated statement of cash flows?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The consolidated statement of cash flows is on page 6 of the FY2025 annual report.',
            numbers=[count(6)],
            citations=[cite(DOC_A, 6, T_CF_A)],
            tags=['citation', 'page_number'],
        )
    )
    citations.append(
        q(
            'cit-002',
            'Which document contains the FY2025 consolidated balance sheet?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The FY2025 annual report contains the consolidated balance sheet on page 5.',
            numbers=[count(5)],
            citations=[cite(DOC_A, 5, T_BS_A)],
            tags=['citation', 'document_selection'],
        )
    )
    citations.append(
        q(
            'cit-003',
            'Which page of the interim report states the revenue outlook for fiscal 2026?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The revenue outlook is in note 2 on page 6 of the interim report.',
            numbers=[count(6)],
            citations=[cite(DOC_A_Q3, 6, T_Q3_OUTLOOK)],
            tags=['citation', 'page_number'],
        )
    )
    citations.append(
        q(
            'cit-004',
            'Which sheet of the budget workbook holds the assumptions?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The assumptions are on sheet 2 of 2, the sheet named Assumptions.',
            numbers=[count(2)],
            citations=[cite(DOC_BUDGET, 1, T_ASSUMPTIONS)],
            tags=['citation', 'sheet_name'],
        )
    )
    citations.append(
        q(
            'cit-005',
            'Which table on page 4 of the annual report reports earnings per share?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The Earnings per share table on page 4 reports basic and diluted earnings per share and the weighted-average share counts.',
            numbers=[],
            citations=[cite(DOC_A, 4, T_EPS_A)],
            tags=['citation', 'table_name'],
        )
    )
    citations.append(
        q(
            'cit-006',
            'Where in the annual report is the quarterly dividend disclosed?',
            category='documents',
            difficulty='medium',
            role='audit_compliance',
            company='company-a',
            answer='The dividend is disclosed under Subsequent events on page 8 of the annual report.',
            numbers=[count(8)],
            citations=[cite(DOC_A, 8, T_SUBSEQUENT_A)],
            tags=['citation', 'page_number', 'cross_document'],
        )
    )
    citations.append(
        q(
            'cit-007',
            'Which document reports revenue by region for Company B?',
            category='documents',
            difficulty='medium',
            role='audit_compliance',
            company='company-b',
            answer='The revenue-by-region CSV for Company B reports FY2024 to FY2026 regional revenue.',
            numbers=[],
            citations=[cite(DOC_REGIONS, 1, T_REGIONS)],
            tags=['citation', 'document_selection', 'csv'],
        )
    )
    citations.append(
        q(
            'cit-008',
            'Which document is the superseded version of the FY2025 annual report?',
            category='documents',
            difficulty='medium',
            role='audit_compliance',
            company='company-a',
            answer='The draft annual report dated October 2, 2025 is the superseded version.',
            numbers=[],
            citations=[cite(DOC_A_DRAFT, 2, T_DRAFT_REVISIONS)],
            tags=['citation', 'versioning'],
        )
    )
    groups['citations'] = citations

    # --- insufficient data --------------------------------------------------
    insufficient = [
        _insufficient('ins-001', 'What was total net revenue in FY2022?', tags=['missing_period']),
        _insufficient('ins-002', 'What was marketing spend in 2022?', tags=['missing_period']),
        _insufficient(
            'ins-003',
            'How many employees does Company A have?',
            tags=['not_in_documents', 'headcount'],
        ),
        _insufficient(
            'ins-004',
            'What was Company A reported full-year FY2026 revenue?',
            tags=['missing_period', 'incomplete_year'],
            notes='Only nine months of fiscal 2026 have been reported at the balance sheet date.',
        ),
        _insufficient(
            'ins-005',
            'What was Company B revenue in the second quarter of fiscal 2026?',
            company='company-b',
            tags=['missing_period', 'quarterly'],
        ),
        _insufficient(
            'ins-006',
            'How much did Company A pay in dividends during FY2024?',
            tags=['not_in_documents'],
        ),
        _insufficient(
            'ins-007', 'What is Company A share price?', tags=['not_in_documents', 'market_data']
        ),
        _insufficient(
            'ins-008',
            'What was total net revenue in euros?',
            tags=['wrong_unit'],
            notes='The documents report in US dollars only.',
        ),
        _insufficient(
            'ins-009',
            'What did the Company B board decide about dividends?',
            company='company-b',
            tags=['missing_document', 'cross_company'],
        ),
        _insufficient(
            'ins-010',
            'What was Company A revenue in April 2026?',
            tags=['missing_period', 'monthly'],
        ),
        _insufficient(
            'ins-011',
            'Which customers are listed in the general ledger?',
            tags=['not_in_documents', 'anonymized'],
            notes='The ledger is anonymized and contains no customer names.',
        ),
        _insufficient(
            'ins-012',
            'How accurate was the FY2024 forecast?',
            tags=['not_in_documents'],
            notes='No forecast-versus-actual accuracy report exists in the fixture set.',
        ),
        _insufficient(
            'ins-013',
            'How much did Company A spend on cloud compute in FY2024?',
            tags=['missing_period'],
            notes='The ledger covers the fourth quarter of FY2025 only.',
        ),
        _insufficient(
            'ins-014',
            'How many people work at Company B?',
            company='company-b',
            tags=['not_in_documents', 'headcount'],
        ),
        _insufficient('ins-015', 'What was the gross margin in FY2022?', tags=['missing_period']),
        _insufficient(
            'ins-016',
            'What will Company A revenue be in FY2027?',
            tags=['future', 'no_forecast'],
            notes='Guidance covers FY2026 only.',
        ),
    ]
    groups['insufficient_data'] = insufficient

    # --- access -------------------------------------------------------------
    access = [
        _denied(
            'acc-001',
            'What was total net revenue in FY2025?',
            category='financials',
            role='system_admin',
            tags=['access', 'denied', 'role_matrix'],
            notes='system_admin has configure only on financials, never read, so the request is refused before retrieval.',
        ),
        _denied(
            'acc-002',
            'Show me the FY2025 net income.',
            category='financials',
            role='system_admin',
            tags=['access', 'denied', 'role_matrix'],
            notes='Same rule as acc-001: no read access to financial content.',
        ),
        _denied(
            'acc-003',
            'Show me the audit trail for last quarter.',
            category='audit',
            role='corporate_finance_planners',
            tags=['access', 'denied', 'audit_trail'],
            notes='corporate_finance_planners has an empty audit list.',
        ),
        q(
            'acc-004',
            'What was total net revenue in FY2025?',
            category='financials',
            difficulty='easy',
            role='executive_leadership',
            company='company-a',
            answer=f'Total net revenue in FY2025 was ${a["revenue"]:,.0f} million.',
            numbers=[money(a['revenue'])],
            citations=[cite(DOC_A, 4, T_INCOME_A)],
            tags=['access', 'allowed', 'executive_leadership'],
        ),
        q(
            'acc-005',
            'What quarterly dividend per share did the finance committee recommend?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The committee recommended $0.26 per share.',
            numbers=[money(0.26, '1', 2)],
            citations=[cite(DOC_BOARD, 1, T_CAPITAL)],
            tags=['access', 'allowed', 'audit_compliance'],
        ),
        q(
            'acc-006',
            'What was the largest single debit in the general ledger?',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'The largest single debit was ${largest_debit[5]:,.2f} for {largest_debit[4]}.',
            numbers=[money(largest_debit[5], '1', 2)],
            citations=[cite(DOC_LEDGER, 1, T_LEDGER)],
            tags=['access', 'allowed', 'corporate_finance_planners'],
        ),
        q(
            'acc-007',
            'What was net income in FY2025?',
            category='financials',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'Net income in FY2025 was ${a["net_income"]:,.0f} million.',
            numbers=[money(a['net_income'])],
            citations=[cite(DOC_A, 4, T_INCOME_A)],
            tags=['access', 'allowed', 'audit_compliance'],
        ),
        _denied(
            'acc-008',
            'How many documents are loaded for Company A?',
            category='documents',
            role='system_admin',
            tags=['access', 'denied', 'documents'],
            notes='system_admin may configure storage but may not read document content or counts.',
        ),
    ]
    groups['access'] = access

    # --- messy phrasing -----------------------------------------------------
    messy: list[dict[str, Any]] = []
    messy.append(
        q(
            'msy-001',
            'how much did we pull in last year?',
            category='financials',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=f'Total net revenue in FY2025 was ${a["revenue"]:,.0f} million.',
            numbers=[money(a['revenue'])],
            citations=[cite(DOC_A, 4, T_INCOME_A)],
            tags=['messy', 'revenue', 'colloquial'],
        )
    )
    messy.append(
        q(
            'msy-002',
            'whats our net income fy25',
            category='financials',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'Net income in FY2025 was ${a["net_income"]:,.0f} million.',
            numbers=[money(a['net_income'])],
            citations=[cite(DOC_A, 4, T_INCOME_A)],
            tags=['messy', 'net_income', 'lowercase'],
        )
    )
    messy.append(
        q(
            'msy-003',
            'gm % fy25?',
            category='metrics',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'Gross margin in FY2025 was {gm25:.1f}%.',
            numbers=[pct(gm25)],
            citations=[cite(DOC_A, 3, T_RATIOS_A)],
            tags=['messy', 'margin', 'abbreviation'],
        )
    )
    messy.append(
        q(
            'msy-004',
            'did revenue go up or down vs 2024 and by how much',
            category='metrics',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'Revenue went up by ${a["revenue"] - a_prior["revenue"]:,.0f} million, or '
                f'{growth(a["revenue"], a_prior["revenue"]):.1f}%, from ${a_prior["revenue"]:,.0f} million to '
                f'${a["revenue"]:,.0f} million.'
            ),
            numbers=[money(a['revenue'] - a_prior['revenue'])],
            citations=[cite(DOC_A, 2, T_SELECTED_A)],
            tags=['messy', 'revenue', 'comparison'],
        )
    )
    messy.append(
        q(
            'msy-005',
            'cash at bank end of sept 2025',
            category='financials',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'Cash and cash equivalents at 27 September 2025 were ${bs["cash"]:,.0f} million.',
            numbers=[money(bs['cash'])],
            citations=[cite(DOC_A, 5, T_BS_A)],
            tags=['messy', 'cash', 'colloquial'],
        )
    )
    messy.append(
        q(
            'msy-006',
            'how much did we spend on R&D',
            category='financials',
            difficulty='easy',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'Research and development expense in FY2025 was ${a["research_development"]:,.0f} million.',
            numbers=[money(a['research_development'])],
            citations=[cite(DOC_A, 4, T_INCOME_A)],
            tags=['messy', 'opex', 'abbreviation'],
        )
    )
    messy.append(
        q(
            'msy-007',
            'whats the dividend',
            category='decisions',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer='The quarterly dividend was raised to $0.26 per share, payable on 14 November 2025.',
            numbers=[money(0.26, '1', 2)],
            citations=[cite(DOC_A, 8, T_SUBSEQUENT_A), cite(DOC_BOARD, 1, T_CAPITAL)],
            tags=['messy', 'dividend'],
        )
    )
    messy.append(
        q(
            'msy-008',
            'biggest payment out of the operating account',
            category='financials',
            difficulty='medium',
            role='audit_compliance',
            company='company-a',
            answer=f'The largest payment out was ${abs(min(docdata.BANK_TRANSACTIONS, key=lambda row: row[2])[2]):,.2f}, for supplier payments.',
            numbers=[money(abs(min(docdata.BANK_TRANSACTIONS, key=lambda row: row[2])[2]), '1', 2)],
            citations=[cite(DOC_BANK, 1, T_BANK_TXNS)],
            tags=['messy', 'bank_statement', 'max'],
        )
    )
    messy.append(
        q(
            'msy-009',
            'are we making more profit than last yr',
            category='financials',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=(
                f'Yes. Net income rose to ${a["net_income"]:,.0f} million in FY2025 from '
                f'${a_prior["net_income"]:,.0f} million in FY2024, an increase of '
                f'{growth(a["net_income"], a_prior["net_income"]):.1f}%.'
            ),
            numbers=[pct(growth(a['net_income'], a_prior['net_income']))],
            citations=[cite(DOC_A, 2, T_SELECTED_A), cite(DOC_A, 4, T_INCOME_A)],
            tags=['messy', 'net_income', 'comparison'],
        )
    )
    messy.append(
        q(
            'msy-010',
            'invoice total pls',
            category='financials',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer=f'The invoice total due is ${docdata.invoice_total():,.2f}.',
            numbers=[money(docdata.invoice_total(), '1', 2)],
            citations=[cite(DOC_INVOICE, 1, T_INVOICE_TOTAL)],
            tags=['messy', 'invoice', 'ocr'],
        )
    )
    messy.append(
        q(
            'msy-011',
            'europe revenue for the software co',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-b',
            answer=f'Company B earned ${docdata.region_value("Europe", "fy2026"):,.0f} million in Europe in FY2026.',
            numbers=[money(docdata.region_value('Europe', 'fy2026'))],
            citations=[cite(DOC_REGIONS, 1, T_REGIONS)],
            tags=['messy', 'region', 'company-b'],
        )
    )
    messy.append(
        q(
            'msy-012',
            'how much cash did ops generate 9m',
            category='financials',
            difficulty='medium',
            role='corporate_finance_planners',
            company='company-a',
            answer=f'Operating activities generated ${q3_cf["cash_from_operations"]:,.0f} million in the first nine months of fiscal 2026.',
            numbers=[money(q3_cf['cash_from_operations'])],
            citations=[cite(DOC_A_Q3, 5, T_Q3_CF)],
            tags=['messy', 'cash_flow', 'quarterly'],
        )
    )
    groups['messy_phrasing'] = messy

    # --- versioning ---------------------------------------------------------
    versioning: list[dict[str, Any]] = []
    versioning.append(
        q(
            'ver-001',
            'What preliminary total net revenue did the October 2 draft report?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The October 2 draft reported preliminary total net revenue of $414,800 million.',
            numbers=[money(414_800.0)],
            citations=[cite(DOC_A_DRAFT, 1, T_DRAFT_HEADLINE)],
            tags=['versioning', 'draft'],
        )
    )
    versioning.append(
        q(
            'ver-002',
            'What was the final reported total net revenue for FY2025?',
            category='financials',
            difficulty='medium',
            role='executive_leadership',
            company='company-a',
            answer=f'The final reported total net revenue for FY2025 was ${a["revenue"]:,.0f} million.',
            numbers=[money(a['revenue'])],
            citations=[cite(DOC_A, 4, T_INCOME_A)],
            tags=['versioning', 'final', 'latest_version'],
            notes='The draft says $414,800 million. The latest final version must win.',
        )
    )
    versioning.append(
        q(
            'ver-003',
            'By how much did revenue change between the draft and the final annual report?',
            category='documents',
            difficulty='medium',
            role='audit_compliance',
            company='company-a',
            answer=f'Revenue increased by ${a["revenue"] - 414_800.0:,.0f} million, from $414,800 million in the draft to ${a["revenue"]:,.0f} million in the final report.',
            numbers=[money(a['revenue'] - 414_800.0)],
            citations=[cite(DOC_A_DRAFT, 2, T_DRAFT_REVISIONS)],
            tags=['versioning', 'derived'],
        )
    )
    versioning.append(
        q(
            'ver-004',
            'Which document is authoritative for FY2025 reported revenue?',
            category='documents',
            difficulty='easy',
            role='audit_compliance',
            company='company-a',
            answer='The final FY2025 annual report is authoritative; the October 2 draft was superseded on October 31, 2025.',
            numbers=[],
            citations=[cite(DOC_A_DRAFT, 2, T_DRAFT_REVISIONS)],
            tags=['versioning', 'superseded'],
        )
    )
    groups['versioning'] = versioning

    return groups


FILE_HEADER = """# Generated by `uv run python scripts/fixture_builder`. Do not edit by hand.
#
# Expected values are computed from the same model that renders the documents.
# See tests/golden/questions/README.md for coverage and scoring rules.
"""


def write_questions(groups: dict[str, list[dict[str, Any]]], out_dir: Path = OUTPUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, questions in groups.items():
        body = yamlout.dump({'version': 1, 'questions': questions})
        (out_dir / f'{name}.yaml').write_text(FILE_HEADER + body, encoding='utf-8')


THRESHOLDS_HEADER = """# Release gate for the golden set.
# Generated by `uv run python scripts/fixture_builder`. Do not edit by hand.
#
# Values are fractions: 0.95 means 95%. The runner compares the measured rate
# against these numbers and blocks a release when either one drops.
"""

THRESHOLDS = {
    'numeric_accuracy': 0.95,
    'citation_accuracy': 1.0,
    'answer_coverage': 1.0,
    'minimum_questions': 100,
    'minimum_numeric_questions': 20,
    'minimum_insufficient_cases': 10,
}


def write_thresholds(out_dir: Path = OUTPUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = yamlout.dump(THRESHOLDS)
    (out_dir / 'thresholds.yaml').write_text(THRESHOLDS_HEADER + body, encoding='utf-8')
