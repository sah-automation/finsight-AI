"""Write the anonymized sample documents.

Every writer is deterministic: the same model produces byte-stable content, so a
rebuild does not create phantom diffs. Born-digital PDFs are re-read with
pdfplumber so the returned page count and section map describe the file on disk,
not what we hoped we wrote.

Units are stated on every document. Financial statements are in USD millions;
the ledger, bank statement and invoice are in whole US dollars.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import random
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pdfplumber
from docx import Document as DocxDocument
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.writer.excel import ExcelWriter
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from fixture_builder import docdata, yamlout
from fixture_builder.model import (
    BALANCE_LABELS,
    CASH_FLOW_LABELS,
    INCOME_LABELS,
    CompanyModel,
    growth,
    margin,
)

if TYPE_CHECKING:
    from reportlab.platypus import Flowable

OUTPUT_DIR = Path('tests/fixtures/documents')

FONT = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'

STYLES = {
    'cover_name': ParagraphStyle(
        'cover_name', fontName=FONT_BOLD, fontSize=26, leading=31, alignment=TA_CENTER
    ),
    'cover_kicker': ParagraphStyle(
        'cover_kicker', fontName=FONT_BOLD, fontSize=12, leading=15, alignment=TA_CENTER
    ),
    'cover_body': ParagraphStyle(
        'cover_body', fontName=FONT, fontSize=10, leading=14, alignment=TA_CENTER
    ),
    'cover_fine': ParagraphStyle(
        'cover_fine',
        fontName=FONT,
        fontSize=7.5,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#555555'),
    ),
    'h1': ParagraphStyle('h1', fontName=FONT_BOLD, fontSize=14, leading=17, spaceAfter=4),
    'h2': ParagraphStyle(
        'h2', fontName=FONT_BOLD, fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=3
    ),
    'body': ParagraphStyle('body', fontName=FONT, fontSize=9.5, leading=13, spaceAfter=5),
    'bullet': ParagraphStyle(
        'bullet',
        fontName=FONT,
        fontSize=9.5,
        leading=13,
        leftIndent=12,
        firstLineIndent=-10,
        spaceAfter=3,
    ),
    'small': ParagraphStyle(
        'small', fontName=FONT, fontSize=8, leading=10.5, textColor=colors.HexColor('#333333')
    ),
    'caption': ParagraphStyle(
        'caption',
        fontName=FONT,
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
    ),
    'warning': ParagraphStyle(
        'warning',
        fontName=FONT_BOLD,
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#a00000'),
    ),
}

INCOME_A_ORDER = (
    'revenue',
    'cost_of_revenue',
    'gross_profit',
    'research_development',
    'selling_general_admin',
    'total_operating_expenses',
    'operating_income',
    'other_income_net',
    'pretax_income',
    'income_tax',
    'net_income',
)

INCOME_B_ORDER = (
    'revenue',
    'cost_of_revenue',
    'gross_profit',
    'research_development',
    'sales_marketing',
    'general_administrative',
    'total_operating_expenses',
    'operating_income',
    'other_income_net',
    'pretax_income',
    'income_tax',
    'net_income',
)

ASSET_ORDER = (
    'cash',
    'short_term_investments',
    'accounts_receivable',
    'inventories',
    'other_current_assets',
    'total_current_assets',
    'ppe_net',
    'goodwill',
    'intangible_assets',
    'other_noncurrent_assets',
    'total_assets',
)

LIABILITY_ORDER = (
    'accounts_payable',
    'deferred_revenue',
    'accrued_liabilities',
    'total_current_liabilities',
    'long_term_debt',
    'other_noncurrent_liabilities',
    'total_liabilities',
    'common_stock_apic',
    'retained_earnings',
    'aoci',
    'treasury_stock',
    'total_equity',
)

CASH_FLOW_ORDER = (
    'net_income',
    'depreciation_amortization',
    'stock_based_compensation',
    'working_capital_change',
    'cash_from_operations',
    'capital_expenditures',
    'cash_from_investing',
    'cash_from_financing',
    'fx_effect',
    'net_change',
    'cash_beginning',
    'cash_ending',
)

# company-b does not tag property, plant and equipment, payables or inventory
# separately, so those amounts sit inside the residual lines. Name the residual
# lines for what they actually contain rather than printing a zero line.
LABEL_OVERRIDES_B = {
    'other_current_assets': 'Prepaid expenses and other current assets',
    'other_noncurrent_assets': 'Property, plant and equipment and other non-current assets',
    'accrued_liabilities': 'Accounts payable and accrued liabilities',
}

BOLD_KEYS = frozenset(
    {
        'gross_profit',
        'total_operating_expenses',
        'operating_income',
        'pretax_income',
        'net_income',
        'total_current_assets',
        'total_assets',
        'total_current_liabilities',
        'total_liabilities',
        'total_equity',
        'cash_from_operations',
        'cash_from_investing',
        'cash_from_financing',
        'net_change',
    }
)


@dataclass(frozen=True)
class DocumentMeta:
    filename: str
    file_type: str
    category: str
    company: str
    period: str
    status: str
    pages: int
    features: tuple[str, ...]
    notes: str
    source: str = ''


@dataclass(frozen=True)
class GeneratedDocument:
    meta: DocumentMeta
    path: Path
    # page number -> section and table headings that appear on that page
    sections: dict[int, tuple[str, ...]]


# --- formatting -------------------------------------------------------------


def _esc(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _para(text: str, style: str = 'body') -> Paragraph:
    return Paragraph(_esc(text), STYLES[style])


def _bullet(text: str) -> Paragraph:
    return Paragraph(f'- {_esc(text)}', STYLES['bullet'])


def _num(value: float, decimals: int = 0) -> str:
    """Statement formatting: thousands separators, parentheses for negatives."""
    text = f'{abs(value):,.{decimals}f}'
    return f'({text})' if value < 0 else text


def _usd(value: float) -> str:
    return f'{value:,.2f}'


def _pct(value: float) -> str:
    return f'{value:.1f}%'


class _Story:
    """Accumulates flowables and records which headings land on which page."""

    def __init__(self) -> None:
        self.items: list[Flowable] = []
        self.page = 1
        self.sections: dict[int, list[str]] = {1: []}

    def add(self, *flowables: Flowable) -> None:
        self.items.extend(flowables)

    def heading(self, text: str, style: str = 'h1') -> None:
        self.sections[self.page].append(text)
        self.items.append(_para(text, style))

    def label(self, text: str) -> None:
        self.sections[self.page].append(text)

    def new_page(self) -> None:
        self.items.append(PageBreak())
        self.page += 1
        self.sections[self.page] = []


def _table(
    header: tuple[str, ...],
    rows: list[tuple[str, ...]],
    widths: tuple[float, ...],
    *,
    bold_rows: frozenset[int] = frozenset(),
    indent_rows: frozenset[int] = frozenset(),
    font_size: float = 8.5,
) -> Table:
    data = [list(header), *[list(row) for row in rows]]
    table = Table(data, colWidths=[width * inch for width in widths], hAlign='LEFT')
    style = [
        ('FONT', (0, 0), (-1, 0), FONT_BOLD, font_size),
        ('FONT', (0, 1), (-1, -1), FONT, font_size),
        ('LINEBELOW', (0, 0), (-1, 0), 0.7, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 0.7, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.6),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    for index in bold_rows:
        style.append(('FONT', (0, index + 1), (-1, index + 1), FONT_BOLD, font_size))
    for index in indent_rows:
        style.append(('LEFTPADDING', (0, index + 1), (0, index + 1), 14))
    table.setStyle(TableStyle(style))
    return table


def _statement_rows(
    order: tuple[str, ...],
    labels: dict[str, str],
    columns: list[dict[str, float]],
    *,
    decimals: int = 0,
    overrides: dict[str, str] | None = None,
) -> tuple[list[tuple[str, ...]], frozenset[int]]:
    labels = {**labels, **(overrides or {})}
    rows: list[tuple[str, ...]] = []
    bold: set[int] = set()
    for key in order:
        if not any(key in column for column in columns):
            continue
        values = [column.get(key) for column in columns]
        if all(value is None for value in values):
            continue
        if all(value is None or value == 0 for value in values) and key not in BOLD_KEYS:
            continue
        rows.append(
            (
                labels[key],
                *[_num(value, decimals) if value is not None else '-' for value in values],
            )
        )
        if key in BOLD_KEYS:
            bold.add(len(rows) - 1)
    return rows, frozenset(bold)


def _pdf(path: Path, story: _Story, footer: str, subject: str) -> None:
    doc = BaseDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.75 * inch,
        title=subject,
        author='Company A, Inc.',
        subject=subject,
        creator='FinSight AI fixture builder',
        # Pin the PDF creation date and document id so a rebuild is byte-stable.
        invariant=1,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')

    def draw_footer(canvas: object, _doc: object) -> None:
        canvas.saveState()  # type: ignore[attr-defined]
        canvas.setFont(FONT, 7.5)  # type: ignore[attr-defined]
        canvas.setFillColor(colors.HexColor('#444444'))  # type: ignore[attr-defined]
        canvas.drawString(doc.leftMargin, 0.45 * inch, footer)  # type: ignore[attr-defined]
        canvas.drawRightString(  # type: ignore[attr-defined]
            LETTER[0] - doc.rightMargin,
            0.45 * inch,
            f'Page {_doc.page}',  # type: ignore[attr-defined]
        )
        canvas.restoreState()  # type: ignore[attr-defined]

    doc.addPageTemplates([PageTemplate(id='main', frames=[frame], onPage=draw_footer)])
    doc.build(story.items)


def _pdf_sections(path: Path, expected_pages: int) -> dict[int, str]:
    """Re-read the PDF and return its text per page, checking the page count."""
    with pdfplumber.open(str(path)) as pdf:
        pages = {index + 1: (page.extract_text() or '') for index, page in enumerate(pdf.pages)}
    if len(pages) != expected_pages:
        msg = f'{path.name}: wrote {len(pages)} pages, planned {expected_pages}'
        raise AssertionError(msg)
    return pages


# OOXML writers stamp each part with the current time. Pin one timestamp so a
# rebuild produces the same bytes instead of a phantom diff.
PACKAGE_TIMESTAMP = dt.datetime(2025, 10, 31, tzinfo=dt.UTC)
_PACKAGE_ZIP_TIME = (2025, 10, 31, 0, 0, 0)


def _normalise_package(path: Path) -> None:
    """Rewrite a DOCX/XLSX zip with fixed entry timestamps.

    The parts and their order are untouched; only the per-entry timestamps are
    pinned. Readers do not care about the difference, but git does.
    """
    with zipfile.ZipFile(path) as source:
        entries = [(info.filename, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=_PACKAGE_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            target.writestr(info, payload)


# --- company A annual report ------------------------------------------------


def company_a_annual(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    fy2025, fy2024, fy2023 = model.annual
    current = fy2025.income
    prior = fy2024.income
    oldest = fy2023.income
    revenue_growth = growth(current['revenue'], prior['revenue'])
    story = _Story()

    # Page 1 - cover
    story.add(Spacer(1, 1.1 * inch))
    story.add(_para('COMPANY A, INC.', 'cover_name'))
    story.add(Spacer(1, 0.25 * inch))
    story.add(_para('FORM 10-K', 'cover_kicker'))
    story.add(_para('ANNUAL REPORT', 'cover_kicker'))
    story.add(Spacer(1, 0.35 * inch))
    story.add(_para('For the fiscal year ended September 27, 2025', 'cover_body'))
    story.add(Spacer(1, 0.15 * inch))
    story.add(
        _para(
            'All amounts are in millions of United States dollars unless stated otherwise.',
            'cover_fine',
        )
    )
    story.add(Spacer(1, 0.05 * inch))
    story.add(
        _para('Registered office: 1200 Harbour Way, Wilmington, Delaware 19801', 'cover_fine')
    )
    story.add(Spacer(1, 3.0 * inch))
    story.add(
        _para(
            'Fictional training and test fixture. The issuer and all identifying details are invented.',
            'cover_fine',
        )
    )

    # Page 2 - selected financial data
    story.new_page()
    story.heading('Selected financial data')
    story.add(
        _para(
            'The table below summarises the consolidated results for the last three fiscal years. '
            'The final column shows the change between fiscal 2025 and fiscal 2024.',
            'body',
        )
    )
    highlight_rows = [
        ('Total net revenue', current['revenue'], prior['revenue'], oldest['revenue']),
        ('Gross profit', current['gross_profit'], prior['gross_profit'], oldest['gross_profit']),
        (
            'Operating income',
            current['operating_income'],
            prior['operating_income'],
            oldest['operating_income'],
        ),
        ('Net income', current['net_income'], prior['net_income'], oldest['net_income']),
    ]
    rows = [
        (label, _num(one), _num(two), _num(three), _pct(round((one - two) / two * 100, 1)))
        for label, one, two, three in highlight_rows
    ]
    rows.append(
        (
            'Diluted earnings per share (USD)',
            f'{current["eps_diluted"]:.2f}',
            f'{prior["eps_diluted"]:.2f}',
            f'{oldest["eps_diluted"]:.2f}',
            _pct(
                round(
                    (current['eps_diluted'] - prior['eps_diluted']) / prior['eps_diluted'] * 100, 1
                )
            ),
        )
    )
    rows.append(
        (
            'Cash generated by operating activities',
            _num(fy2025.cash_flow['cash_from_operations']),
            _num(fy2024.cash_flow['cash_from_operations']),
            _num(fy2023.cash_flow['cash_from_operations']),
            _pct(
                round(
                    (
                        fy2025.cash_flow['cash_from_operations']
                        - fy2024.cash_flow['cash_from_operations']
                    )
                    / fy2024.cash_flow['cash_from_operations']
                    * 100,
                    1,
                )
            ),
        )
    )
    story.label('Selected financial data')
    story.add(
        _table(
            ('USD millions', 'FY2025', 'FY2024', 'FY2023', 'Change (%)'),
            rows,
            (2.65, 1.05, 1.05, 1.05, 1.2),
        )
    )
    story.add(Spacer(1, 0.18 * inch))
    story.heading('Fiscal 2025 highlights', 'h2')
    story.add(
        _bullet(
            f'Total net revenue was ${_num(current["revenue"])} million, up {_pct(revenue_growth)} from fiscal 2024.'
        )
    )
    story.add(
        _bullet(
            f'Gross margin was {_pct(margin(current["gross_profit"], current["revenue"]))}, compared with {_pct(margin(prior["gross_profit"], prior["revenue"]))} a year earlier.'
        )
    )
    story.add(
        _bullet(
            f'Net income was ${_num(current["net_income"])} million and diluted earnings per share were ${current["eps_diluted"]:.2f}.'
        )
    )
    story.add(
        _bullet(
            f'Cash generated by operating activities was ${_num(fy2025.cash_flow["cash_from_operations"])} million.'
        )
    )

    # Page 3 - MD&A
    story.new_page()
    story.heading('Management discussion and analysis')
    story.heading('Overview', 'h2')
    story.add(
        _para(
            f'Total net revenue increased {_pct(revenue_growth)} to ${_num(current["revenue"])} million in fiscal 2025, '
            f'from ${_num(prior["revenue"])} million in fiscal 2024. Cost of revenue rose '
            f'{_pct(growth(current["cost_of_revenue"], prior["cost_of_revenue"]))} to '
            f'${_num(current["cost_of_revenue"])} million, so gross profit grew '
            f'{_pct(growth(current["gross_profit"], prior["gross_profit"]))} to '
            f'${_num(current["gross_profit"])} million.',
            'body',
        )
    )
    story.add(
        _para(
            f'Operating expenses were ${_num(current["total_operating_expenses"])} million, of which research and '
            f'development was ${_num(current["research_development"])} million and selling, general and '
            f'administrative expense was ${_num(current["selling_general_admin"])} million. Operating income was '
            f'${_num(current["operating_income"])} million, an operating margin of '
            f'{_pct(margin(current["operating_income"], current["revenue"]))}.',
            'body',
        )
    )
    story.add(
        _para(
            f'Other income, net, was ${_num(current["other_income_net"])} million. The effective tax rate was '
            f'{_pct(margin(current["income_tax"], current["pretax_income"]))} and net income was '
            f'${_num(current["net_income"])} million, a net margin of '
            f'{_pct(margin(current["net_income"], current["revenue"]))}.',
            'body',
        )
    )
    story.heading('Key ratios', 'h2')
    story.label('Key ratios')
    ratio_rows = []
    for label, key in (
        ('Gross margin', 'gross_profit'),
        ('Operating margin', 'operating_income'),
        ('Net margin', 'net_income'),
    ):
        ratio_rows.append(
            (
                f'{label} (%)',
                _pct(margin(current[key], current['revenue'])),
                _pct(margin(prior[key], prior['revenue'])),
                _pct(margin(oldest[key], oldest['revenue'])),
            )
        )
    ratio_rows.append(
        (
            'Effective tax rate (%)',
            _pct(margin(current['income_tax'], current['pretax_income'])),
            _pct(margin(prior['income_tax'], prior['pretax_income'])),
            _pct(margin(oldest['income_tax'], oldest['pretax_income'])),
        )
    )
    story.add(_table(('Ratio', 'FY2025', 'FY2024', 'FY2023'), ratio_rows, (3.6, 1.15, 1.15, 1.15)))
    story.add(Spacer(1, 0.12 * inch))
    story.add(
        _para(
            'Margins are calculated on total net revenue. The effective tax rate is the provision for income '
            'taxes divided by income before income taxes.',
            'caption',
        )
    )

    # Page 4 - income statement
    story.new_page()
    story.heading('Consolidated statements of operations')
    story.add(_para('In millions, except per-share amounts', 'caption'))
    columns = [current, prior, oldest]
    rows, bold = _statement_rows(INCOME_A_ORDER, INCOME_LABELS, columns)
    story.add(
        _table(('', 'FY2025', 'FY2024', 'FY2023'), rows, (3.4, 1.2, 1.2, 1.2), bold_rows=bold)
    )
    story.add(Spacer(1, 0.16 * inch))
    share_rows = [
        (
            'Earnings per share, basic',
            f'{current["eps_basic"]:.2f}',
            f'{prior["eps_basic"]:.2f}',
            f'{oldest["eps_basic"]:.2f}',
        ),
        (
            'Earnings per share, diluted',
            f'{current["eps_diluted"]:.2f}',
            f'{prior["eps_diluted"]:.2f}',
            f'{oldest["eps_diluted"]:.2f}',
        ),
        (
            'Weighted-average shares, basic',
            _num(current['shares_basic'], 1),
            _num(prior['shares_basic'], 1),
            _num(oldest['shares_basic'], 1),
        ),
        (
            'Weighted-average shares, diluted',
            _num(current['shares_diluted'], 1),
            _num(prior['shares_diluted'], 1),
            _num(oldest['shares_diluted'], 1),
        ),
    ]
    story.label('Earnings per share')
    story.add(
        _table(
            ('USD per share and shares in millions', 'FY2025', 'FY2024', 'FY2023'),
            share_rows,
            (3.4, 1.2, 1.2, 1.2),
        )
    )

    # Page 5 - balance sheet
    story.new_page()
    story.heading('Consolidated balance sheets')
    story.add(_para('In millions', 'caption'))
    balance_now = model.balances['2025-09-27'].lines
    balance_prior = model.balances['2024-09-28'].lines
    rows, bold = _statement_rows(ASSET_ORDER, BALANCE_LABELS, [balance_now, balance_prior])
    story.label('Consolidated balance sheets')
    story.add(
        _table(
            ('Assets', 'September 27, 2025', 'September 28, 2024'),
            rows,
            (3.4, 1.55, 1.55),
            bold_rows=bold,
        )
    )
    story.add(Spacer(1, 0.2 * inch))
    rows, bold = _statement_rows(LIABILITY_ORDER, BALANCE_LABELS, [balance_now, balance_prior])
    rows.append(
        (
            'Total liabilities and shareholders\u2019 equity',
            _num(balance_now['total_assets']),
            _num(balance_prior['total_assets']),
        )
    )
    bold = frozenset((*bold, len(rows) - 1))
    story.add(
        _table(
            (
                'Liabilities and shareholders\u2019 equity',
                'September 27, 2025',
                'September 28, 2024',
            ),
            rows,
            (3.4, 1.55, 1.55),
            bold_rows=bold,
        )
    )

    # Page 6 - cash flow
    story.new_page()
    story.heading('Consolidated statements of cash flows')
    story.add(_para('In millions', 'caption'))
    rows, bold = _statement_rows(
        CASH_FLOW_ORDER,
        CASH_FLOW_LABELS,
        [fy2025.cash_flow, fy2024.cash_flow, fy2023.cash_flow],
    )
    story.label('Consolidated statements of cash flows')
    story.add(
        _table(('', 'FY2025', 'FY2024', 'FY2023'), rows, (3.4, 1.2, 1.2, 1.2), bold_rows=bold)
    )
    story.add(Spacer(1, 0.1 * inch))
    story.add(
        _para(
            'Amounts in parentheses are cash outflows or reductions in cash. The effect of exchange rate '
            'changes is shown separately and is included in the net change in cash.',
            'caption',
        )
    )

    # Page 7 - notes
    story.new_page()
    story.heading('Notes to the consolidated financial statements')
    story.heading('1. Basis of presentation', 'h2')
    story.add(
        _para(
            'The consolidated financial statements have been prepared in accordance with accounting principles '
            'generally accepted in the United States. The fiscal year ended on September 27, 2025 and '
            'contained 52 weeks. Certain prior-period amounts have been reclassified to conform to the '
            'current presentation.',
            'body',
        )
    )
    story.heading('2. Revenue', 'h2')
    story.add(
        _para(
            f'Revenue is recognised when control of the product or service transfers to the customer. Total net '
            f'revenue for fiscal 2025 was ${_num(current["revenue"])} million (fiscal 2024: '
            f'${_num(prior["revenue"])} million).',
            'body',
        )
    )
    story.heading('3. Income taxes', 'h2')
    story.add(
        _para(
            f'The provision for income taxes was ${_num(current["income_tax"])} million on income before income '
            f'taxes of ${_num(current["pretax_income"])} million, an effective tax rate of '
            f'{_pct(margin(current["income_tax"], current["pretax_income"]))}.',
            'body',
        )
    )
    story.heading('4. Share repurchases', 'h2')
    story.add(
        _para(
            'During fiscal 2025 the company repurchased shares in the open market under programmes authorised '
            'by the Board of Directors. Repurchases are recorded as a reduction of shareholders\u2019 equity. '
            f'The total returned to shareholders through repurchases and dividends is reflected in net cash used '
            f'in financing activities of ${_num(abs(fy2025.cash_flow["cash_from_financing"]))} million.',
            'body',
        )
    )
    story.heading('5. Commitments and contingencies', 'h2')
    story.add(
        _para(
            'The company is not party to any legal proceedings that management expects to have a material '
            'adverse effect on the financial position or results of operations.',
            'body',
        )
    )

    # Page 8 - liquidity and subsequent events
    story.new_page()
    story.heading('Liquidity and capital resources')
    cash_now = balance_now['cash'] + balance_now['short_term_investments']
    story.add(
        _para(
            f'At September 27, 2025 the company held ${_num(balance_now["cash"])} million of cash and cash '
            f'equivalents and ${_num(balance_now["short_term_investments"])} million of short-term marketable '
            f'securities, a combined ${_num(cash_now)} million.',
            'body',
        )
    )
    story.add(
        _para(
            f'Long-term debt was ${_num(balance_now["long_term_debt"])} million. Net cash provided by operating '
            f'activities was ${_num(fy2025.cash_flow["cash_from_operations"])} million and capital expenditure '
            f'was ${_num(fy2025.cash_flow["capital_expenditures"])} million.',
            'body',
        )
    )
    story.heading('Subsequent events', 'h2')
    story.add(
        _para(
            'On October 14, 2025 the Board of Directors approved a quarterly dividend of $0.26 per share, '
            'payable on November 14, 2025 to shareholders of record on November 7, 2025. The Board also '
            'approved an additional share repurchase authorisation of $90 billion.',
            'body',
        )
    )
    story.heading('Critical accounting estimates', 'h2')
    story.add(
        _para(
            'Management considers the recognition of revenue, the measurement of income taxes and the '
            'assessment of impairment of long-lived assets to be the most significant estimates. Actual '
            'results may differ from those estimates.',
            'body',
        )
    )
    story.heading('Forward-looking statements', 'h2')
    story.add(
        _para(
            'This report contains forward-looking statements about future revenue, margins and capital '
            'returns. These statements are based on current expectations and are subject to risks and '
            'uncertainties that could cause actual results to differ materially.',
            'body',
        )
    )

    # Page 9 - controls and signatures
    story.new_page()
    story.heading('Controls and other information')
    story.heading('Management\u2019s report on internal control', 'h2')
    story.add(
        _para(
            'Management is responsible for establishing and maintaining adequate internal control over '
            'financial reporting. Management assessed the effectiveness of internal control over financial '
            'reporting as of September 27, 2025 and concluded that it was effective.',
            'body',
        )
    )
    story.heading('Audit', 'h2')
    story.add(
        _para(
            'The consolidated financial statements were audited by an independent registered public accounting '
            'firm. The firm also audited the effectiveness of internal control over financial reporting.',
            'body',
        )
    )
    story.heading('Shareholder information', 'h2')
    story.add(_bullet('Fiscal year end: last Saturday in September.'))
    story.add(_bullet('Transfer agent: Northbank National Association, Transfer Agency.'))
    story.add(_bullet('Annual meeting: February 24, 2026.'))
    story.add(Spacer(1, 0.35 * inch))
    story.heading('Signatures', 'h2')
    story.add(
        _para(
            'Pursuant to the requirements of Section 13 or 15(d) of the Securities Exchange Act of 1934, the registrant has duly caused this report to be signed on its behalf by the undersigned.',
            'body',
        )
    )
    story.add(Spacer(1, 0.2 * inch))
    story.add(
        _table(
            ('Signature', 'Title', 'Date'),
            [
                ('/s/ Authorised Signatory', 'Chief Executive Officer', 'October 31, 2025'),
                ('/s/ Authorised Signatory', 'Chief Financial Officer', 'October 31, 2025'),
            ],
            (2.6, 2.6, 1.5),
        )
    )

    filename = 'pdf__company-a__2025-FY__annual-report.pdf'
    path = out_dir / filename
    _pdf(
        path,
        story,
        'Company A, Inc. - Form 10-K - fiscal year ended September 27, 2025',
        'Company A, Inc. Form 10-K fiscal 2025',
    )
    pages = _pdf_sections(path, 9)
    meta = DocumentMeta(
        filename=filename,
        file_type='pdf',
        category='annual_report',
        company='company-a',
        period='FY2025',
        status='final',
        pages=len(pages),
        features=('text', 'tables', 'multi_page', 'headings'),
        notes='Born-digital Form 10-K. Income statement on page 4, balance sheet on page 5, cash flow on page 6.',
        source='SEC XBRL companyfacts, CIK 0000320193, FY2023-FY2025 (2022-09-25..2025-09-27)',
    )
    return GeneratedDocument(meta, path, _finalise_sections(story.sections))


def _finalise_sections(sections: dict[int, list[str]]) -> dict[int, tuple[str, ...]]:
    return {page: tuple(dict.fromkeys(values)) for page, values in sections.items()}


# --- company A interim report ----------------------------------------------


def company_a_interim(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    if model.interim is None:
        msg = 'company-a model has no interim period'
        raise LookupError(msg)
    interim = model.interim
    q3_now = interim.current_3m.income
    q3_prior = interim.prior_3m.income
    ytd_now = interim.current_9m.income
    ytd_prior = interim.prior_9m.income
    story = _Story()

    # Page 1 - cover
    story.add(Spacer(1, 1.1 * inch))
    story.add(_para('COMPANY A, INC.', 'cover_name'))
    story.add(Spacer(1, 0.25 * inch))
    story.add(_para('FORM 10-Q', 'cover_kicker'))
    story.add(_para('QUARTERLY REPORT', 'cover_kicker'))
    story.add(Spacer(1, 0.35 * inch))
    story.add(_para('For the quarterly period ended June 27, 2026', 'cover_body'))
    story.add(Spacer(1, 0.15 * inch))
    story.add(
        _para(
            'All amounts are in millions of United States dollars unless stated otherwise.',
            'cover_fine',
        )
    )
    story.add(
        _para('Registered office: 1200 Harbour Way, Wilmington, Delaware 19801', 'cover_fine')
    )
    story.add(Spacer(1, 3.0 * inch))
    story.add(
        _para(
            'Fictional training and test fixture. The issuer and all identifying details are invented.',
            'cover_fine',
        )
    )

    # Page 2 - MD&A
    story.new_page()
    story.heading('Management discussion and analysis')
    story.heading('Third quarter and year to date', 'h2')
    story.add(
        _para(
            f'Total net revenue for the three months ended June 27, 2026 was ${_num(q3_now["revenue"])} million, '
            f'compared with ${_num(q3_prior["revenue"])} million in the same quarter of fiscal 2025, an increase '
            f'of {_pct(growth(q3_now["revenue"], q3_prior["revenue"]))}. For the first nine months of fiscal 2026, '
            f'total net revenue was ${_num(ytd_now["revenue"])} million, up '
            f'{_pct(growth(ytd_now["revenue"], ytd_prior["revenue"]))} from ${_num(ytd_prior["revenue"])} million.',
            'body',
        )
    )
    story.add(
        _para(
            f'Net income was ${_num(q3_now["net_income"])} million for the quarter, compared with '
            f'${_num(q3_prior["net_income"])} million a year earlier. Year-to-date net income was '
            f'${_num(ytd_now["net_income"])} million, compared with ${_num(ytd_prior["net_income"])} million.',
            'body',
        )
    )
    story.add(
        _para(
            f'Research and development expense was ${_num(q3_now["research_development"])} million for the quarter '
            f'and ${_num(ytd_now["research_development"])} million year to date. Selling, general and administrative '
            f'expense was ${_num(q3_now["selling_general_admin"])} million for the quarter.',
            'body',
        )
    )
    story.heading('Quarterly ratios', 'h2')
    story.label('Quarterly ratios')
    ratio_rows = [
        (
            'Gross margin (%)',
            _pct(margin(q3_now['gross_profit'], q3_now['revenue'])),
            _pct(margin(q3_prior['gross_profit'], q3_prior['revenue'])),
            _pct(margin(ytd_now['gross_profit'], ytd_now['revenue'])),
            _pct(margin(ytd_prior['gross_profit'], ytd_prior['revenue'])),
        ),
        (
            'Operating margin (%)',
            _pct(margin(q3_now['operating_income'], q3_now['revenue'])),
            _pct(margin(q3_prior['operating_income'], q3_prior['revenue'])),
            _pct(margin(ytd_now['operating_income'], ytd_now['revenue'])),
            _pct(margin(ytd_prior['operating_income'], ytd_prior['revenue'])),
        ),
        (
            'Net margin (%)',
            _pct(margin(q3_now['net_income'], q3_now['revenue'])),
            _pct(margin(q3_prior['net_income'], q3_prior['revenue'])),
            _pct(margin(ytd_now['net_income'], ytd_now['revenue'])),
            _pct(margin(ytd_prior['net_income'], ytd_prior['revenue'])),
        ),
    ]
    story.add(
        _table(
            ('Ratio', '3M 2026', '3M 2025', '9M 2026', '9M 2025'),
            ratio_rows,
            (2.2, 1.1, 1.1, 1.1, 1.1),
        )
    )
    story.add(Spacer(1, 0.1 * inch))
    story.add(
        _para(
            'Three-month and nine-month figures are unaudited. Margins are calculated on total net revenue.',
            'caption',
        )
    )

    # Page 3 - statements of operations
    story.new_page()
    story.heading('Condensed consolidated statements of operations')
    story.add(
        _para(
            'Three and nine months ended June 27, 2026 and June 28, 2025. In millions, except per-share amounts.',
            'caption',
        )
    )
    rows, bold = _statement_rows(
        INCOME_A_ORDER, INCOME_LABELS, [q3_now, q3_prior, ytd_now, ytd_prior]
    )
    story.label('Condensed consolidated statements of operations')
    story.add(
        _table(
            ('', '3M 2026', '3M 2025', '9M 2026', '9M 2025'),
            rows,
            (2.6, 1.05, 1.05, 1.05, 1.05),
            bold_rows=bold,
        )
    )
    story.add(Spacer(1, 0.14 * inch))
    share_rows = [
        (
            'Earnings per share, basic',
            f'{q3_now["eps_basic"]:.2f}',
            f'{q3_prior["eps_basic"]:.2f}',
            f'{ytd_now["eps_basic"]:.2f}',
            f'{ytd_prior["eps_basic"]:.2f}',
        ),
        (
            'Earnings per share, diluted',
            f'{q3_now["eps_diluted"]:.2f}',
            f'{q3_prior["eps_diluted"]:.2f}',
            f'{ytd_now["eps_diluted"]:.2f}',
            f'{ytd_prior["eps_diluted"]:.2f}',
        ),
        (
            'Weighted-average shares, diluted',
            _num(q3_now['shares_diluted'], 1),
            _num(q3_prior['shares_diluted'], 1),
            _num(ytd_now['shares_diluted'], 1),
            _num(ytd_prior['shares_diluted'], 1),
        ),
    ]
    story.label('Earnings per share')
    story.add(
        _table(
            ('USD per share and shares in millions', '3M 2026', '3M 2025', '9M 2026', '9M 2025'),
            share_rows,
            (2.6, 1.05, 1.05, 1.05, 1.05),
        )
    )

    # Page 4 - balance sheet
    story.new_page()
    story.heading('Condensed consolidated balance sheets')
    story.add(_para('In millions', 'caption'))
    balance_now = model.balances['2026-06-27'].lines
    balance_prior = model.balances['2025-09-27'].lines
    rows, bold = _statement_rows(ASSET_ORDER, BALANCE_LABELS, [balance_now, balance_prior])
    story.label('Condensed consolidated balance sheets')
    story.add(
        _table(
            ('Assets', 'June 27, 2026', 'September 27, 2025'),
            rows,
            (3.4, 1.55, 1.55),
            bold_rows=bold,
        )
    )
    story.add(Spacer(1, 0.2 * inch))
    rows, bold = _statement_rows(LIABILITY_ORDER, BALANCE_LABELS, [balance_now, balance_prior])
    rows.append(
        (
            'Total liabilities and shareholders\u2019 equity',
            _num(balance_now['total_assets']),
            _num(balance_prior['total_assets']),
        )
    )
    bold = frozenset((*bold, len(rows) - 1))
    story.add(
        _table(
            ('Liabilities and shareholders\u2019 equity', 'June 27, 2026', 'September 27, 2025'),
            rows,
            (3.4, 1.55, 1.55),
            bold_rows=bold,
        )
    )

    # Page 5 - cash flow
    story.new_page()
    story.heading('Condensed consolidated statements of cash flows')
    story.add(_para('Nine months ended June 27, 2026 and June 28, 2025. In millions.', 'caption'))
    rows, bold = _statement_rows(
        CASH_FLOW_ORDER,
        CASH_FLOW_LABELS,
        [interim.current_9m.cash_flow, interim.prior_9m.cash_flow],
    )
    story.label('Condensed consolidated statements of cash flows')
    story.add(
        _table(
            ('', '9M 2026', '9M 2025'),
            rows,
            (3.9, 1.4, 1.4),
            bold_rows=bold,
        )
    )

    # Page 6 - notes and guidance
    story.new_page()
    story.heading('Notes to the condensed financial statements')
    story.heading('1. Basis of preparation', 'h2')
    story.add(
        _para(
            'The condensed consolidated financial statements are unaudited and have been prepared on the same '
            'basis as the audited annual financial statements. The results for the nine months are not '
            'necessarily indicative of the results for the full year.',
            'body',
        )
    )
    story.heading('2. Outlook', 'h2')
    story.add(
        _para(
            f'For fiscal 2026 the company expects total net revenue between ${_num(docdata.GUIDANCE["revenue_low"])} million '
            f'and ${_num(docdata.GUIDANCE["revenue_high"])} million, a gross margin between '
            f'{docdata.GUIDANCE["gross_margin_low"]:.1f}% and {docdata.GUIDANCE["gross_margin_high"]:.1f}%, and an '
            f'effective tax rate between {docdata.GUIDANCE["tax_rate_low"]:.1f}% and '
            f'{docdata.GUIDANCE["tax_rate_high"]:.1f}%.',
            'body',
        )
    )
    story.heading('3. Share repurchases', 'h2')
    story.add(
        _para(
            f'During the nine months the company used ${_num(abs(interim.current_9m.cash_flow["cash_from_financing"]))} '
            f'million in financing activities, principally for share repurchases and dividend payments.',
            'body',
        )
    )
    story.heading('4. Subsequent events', 'h2')
    story.add(
        _para(
            'No events occurred after June 27, 2026 that require adjustment to, or disclosure in, these '
            'condensed financial statements.',
            'body',
        )
    )

    filename = 'pdf__company-a__2026-Q3__interim-report.pdf'
    path = out_dir / filename
    _pdf(
        path,
        story,
        'Company A, Inc. - Form 10-Q - quarter ended June 27, 2026',
        'Company A, Inc. Form 10-Q third quarter fiscal 2026',
    )
    pages = _pdf_sections(path, 6)
    meta = DocumentMeta(
        filename=filename,
        file_type='pdf',
        category='interim_report',
        company='company-a',
        period='Q3 FY2026',
        status='final',
        pages=len(pages),
        features=('text', 'tables', 'multi_page', 'headings', 'guidance'),
        notes='Born-digital Form 10-Q. Statements of operations on page 3, balance sheet on page 4, cash flow on page 5, outlook on page 6.',
        source='SEC XBRL companyfacts, CIK 0000320193, Q3 FY2026 (2026-03-29..2026-06-27 and 2025-09-28..2026-06-27)',
    )
    return GeneratedDocument(meta, path, _finalise_sections(story.sections))


# --- company B annual report ------------------------------------------------


def company_b_annual(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    fy2026, fy2025, fy2024 = model.annual
    current = fy2026.income
    prior = fy2025.income
    oldest = fy2024.income
    story = _Story()

    # Page 1 - cover
    story.add(Spacer(1, 1.1 * inch))
    story.add(_para('COMPANY B, INC.', 'cover_name'))
    story.add(Spacer(1, 0.25 * inch))
    story.add(_para('FORM 10-K', 'cover_kicker'))
    story.add(_para('ANNUAL REPORT', 'cover_kicker'))
    story.add(Spacer(1, 0.35 * inch))
    story.add(_para('For the fiscal year ended January 31, 2026', 'cover_body'))
    story.add(Spacer(1, 0.15 * inch))
    story.add(
        _para(
            'All amounts are in millions of United States dollars unless stated otherwise.',
            'cover_fine',
        )
    )
    story.add(
        _para('Registered office: 4400 Calder Park Drive, Dover, Delaware 19901', 'cover_fine')
    )
    story.add(Spacer(1, 3.0 * inch))
    story.add(
        _para(
            'Fictional training and test fixture. The issuer and all identifying details are invented.',
            'cover_fine',
        )
    )

    # Page 2 - highlights
    story.new_page()
    story.heading('Selected financial data')
    story.add(
        _para(
            'The table below summarises the consolidated results for the last three fiscal years.',
            'body',
        )
    )
    highlight_rows = [
        ('Total net revenue', current['revenue'], prior['revenue'], oldest['revenue']),
        ('Gross profit', current['gross_profit'], prior['gross_profit'], oldest['gross_profit']),
        (
            'Operating income',
            current['operating_income'],
            prior['operating_income'],
            oldest['operating_income'],
        ),
        ('Net income', current['net_income'], prior['net_income'], oldest['net_income']),
    ]
    rows = [
        (
            label,
            _num(one),
            _num(two),
            _num(three),
            _pct(round((one - two) / two * 100, 1)),
        )
        for label, one, two, three in highlight_rows
    ]
    rows.append(
        (
            'Diluted earnings per share (USD)',
            f'{current["eps_diluted"]:.2f}',
            f'{prior["eps_diluted"]:.2f}',
            f'{oldest["eps_diluted"]:.2f}',
            _pct(
                round(
                    (current['eps_diluted'] - prior['eps_diluted']) / prior['eps_diluted'] * 100, 1
                )
            ),
        )
    )
    story.label('Selected financial data')
    story.add(
        _table(
            ('USD millions', 'FY2026', 'FY2025', 'FY2024', 'Change (%)'),
            rows,
            (2.65, 1.05, 1.05, 1.05, 1.2),
        )
    )
    story.add(Spacer(1, 0.18 * inch))
    story.heading('Fiscal 2026 highlights', 'h2')
    story.add(
        _bullet(
            f'Total net revenue was ${_num(current["revenue"])} million, up {_pct(growth(current["revenue"], prior["revenue"]))} from fiscal 2025.'
        )
    )
    story.add(
        _bullet(f'Gross margin was {_pct(margin(current["gross_profit"], current["revenue"]))}.')
    )
    story.add(
        _bullet(
            f'Operating margin was {_pct(margin(current["operating_income"], current["revenue"]))} and net margin was {_pct(margin(current["net_income"], current["revenue"]))}.'
        )
    )
    story.add(
        _bullet(
            f'Cash generated by operating activities was ${_num(fy2026.cash_flow["cash_from_operations"])} million.'
        )
    )

    # Page 3 - MD&A
    story.new_page()
    story.heading('Management discussion and analysis')
    story.heading('Overview', 'h2')
    story.add(
        _para(
            f'Total net revenue increased {_pct(growth(current["revenue"], prior["revenue"]))} to '
            f'${_num(current["revenue"])} million in fiscal 2026. Cost of revenue was '
            f'${_num(current["cost_of_revenue"])} million, giving a gross profit of '
            f'${_num(current["gross_profit"])} million and a gross margin of '
            f'{_pct(margin(current["gross_profit"], current["revenue"]))}.',
            'body',
        )
    )
    story.add(
        _para(
            f'Research and development expense was ${_num(current["research_development"])} million, sales and '
            f'marketing expense was ${_num(current["sales_marketing"])} million and general and administrative '
            f'expense was ${_num(current["general_administrative"])} million. Total operating expenses were '
            f'${_num(current["total_operating_expenses"])} million.',
            'body',
        )
    )
    story.add(
        _para(
            f'Operating income was ${_num(current["operating_income"])} million. Other income, net, contributed '
            f'${_num(current["other_income_net"])} million, and the effective tax rate was '
            f'{_pct(margin(current["income_tax"], current["pretax_income"]))}. Net income was '
            f'${_num(current["net_income"])} million.',
            'body',
        )
    )
    story.heading('Key ratios', 'h2')
    story.label('Key ratios')
    ratio_rows = []
    for label, key in (
        ('Gross margin', 'gross_profit'),
        ('Operating margin', 'operating_income'),
        ('Net margin', 'net_income'),
    ):
        ratio_rows.append(
            (
                f'{label} (%)',
                _pct(margin(current[key], current['revenue'])),
                _pct(margin(prior[key], prior['revenue'])),
                _pct(margin(oldest[key], oldest['revenue'])),
            )
        )
    ratio_rows.append(
        (
            'Effective tax rate (%)',
            _pct(margin(current['income_tax'], current['pretax_income'])),
            _pct(margin(prior['income_tax'], prior['pretax_income'])),
            _pct(margin(oldest['income_tax'], oldest['pretax_income'])),
        )
    )
    story.add(_table(('Ratio', 'FY2026', 'FY2025', 'FY2024'), ratio_rows, (3.6, 1.15, 1.15, 1.15)))
    story.heading('Revenue by region', 'h2')
    story.add(
        _para(
            'Revenue by region is presented in the companion spreadsheet for this fiscal year. The Americas '
            'remains the largest region by revenue.',
            'body',
        )
    )

    # Page 4 - income statement
    story.new_page()
    story.heading('Consolidated statements of operations')
    story.add(_para('In millions, except per-share amounts', 'caption'))
    rows, bold = _statement_rows(
        INCOME_B_ORDER, INCOME_LABELS, [current, prior, oldest], overrides=LABEL_OVERRIDES_B
    )
    story.label('Consolidated statements of operations')
    story.add(
        _table(('', 'FY2026', 'FY2025', 'FY2024'), rows, (3.4, 1.2, 1.2, 1.2), bold_rows=bold)
    )
    story.add(Spacer(1, 0.16 * inch))
    share_rows = [
        (
            'Earnings per share, basic',
            f'{current["eps_basic"]:.2f}',
            f'{prior["eps_basic"]:.2f}',
            f'{oldest["eps_basic"]:.2f}',
        ),
        (
            'Earnings per share, diluted',
            f'{current["eps_diluted"]:.2f}',
            f'{prior["eps_diluted"]:.2f}',
            f'{oldest["eps_diluted"]:.2f}',
        ),
        (
            'Weighted-average shares, diluted',
            _num(current['shares_diluted'], 1),
            _num(prior['shares_diluted'], 1),
            _num(oldest['shares_diluted'], 1),
        ),
    ]
    story.label('Earnings per share')
    story.add(
        _table(
            ('USD per share and shares in millions', 'FY2026', 'FY2025', 'FY2024'),
            share_rows,
            (3.4, 1.2, 1.2, 1.2),
        )
    )

    # Page 5 - balance sheet
    story.new_page()
    story.heading('Consolidated balance sheets')
    story.add(_para('In millions', 'caption'))
    balance_now = model.balances['2026-01-31'].lines
    balance_prior = model.balances['2025-01-31'].lines
    rows, bold = _statement_rows(
        ASSET_ORDER, BALANCE_LABELS, [balance_now, balance_prior], overrides=LABEL_OVERRIDES_B
    )
    story.label('Consolidated balance sheets')
    story.add(
        _table(
            ('Assets', 'January 31, 2026', 'January 31, 2025'),
            rows,
            (3.4, 1.55, 1.55),
            bold_rows=bold,
        )
    )
    story.add(Spacer(1, 0.2 * inch))
    rows, bold = _statement_rows(
        LIABILITY_ORDER, BALANCE_LABELS, [balance_now, balance_prior], overrides=LABEL_OVERRIDES_B
    )
    rows.append(
        (
            'Total liabilities and shareholders\u2019 equity',
            _num(balance_now['total_assets']),
            _num(balance_prior['total_assets']),
        )
    )
    bold = frozenset((*bold, len(rows) - 1))
    story.add(
        _table(
            ('Liabilities and shareholders\u2019 equity', 'January 31, 2026', 'January 31, 2025'),
            rows,
            (3.4, 1.55, 1.55),
            bold_rows=bold,
        )
    )

    # Page 6 - cash flow
    story.new_page()
    story.heading('Consolidated statements of cash flows')
    story.add(_para('In millions', 'caption'))
    rows, bold = _statement_rows(
        CASH_FLOW_ORDER, CASH_FLOW_LABELS, [fy2026.cash_flow, fy2025.cash_flow, fy2024.cash_flow]
    )
    story.label('Consolidated statements of cash flows')
    story.add(
        _table(('', 'FY2026', 'FY2025', 'FY2024'), rows, (3.4, 1.2, 1.2, 1.2), bold_rows=bold)
    )

    # Page 7 - notes and controls
    story.new_page()
    story.heading('Notes to the consolidated financial statements')
    story.heading('1. Basis of presentation', 'h2')
    story.add(
        _para(
            'The consolidated financial statements have been prepared in accordance with accounting principles '
            'generally accepted in the United States. The fiscal year ended on January 31, 2026.',
            'body',
        )
    )
    story.heading('2. Income taxes', 'h2')
    story.add(
        _para(
            f'The provision for income taxes was ${_num(current["income_tax"])} million on income before income '
            f'taxes of ${_num(current["pretax_income"])} million.',
            'body',
        )
    )
    story.heading('3. Liquidity', 'h2')
    story.add(
        _para(
            f'At January 31, 2026 the company held ${_num(balance_now["cash"])} million of cash and cash '
            f'equivalents. Net cash provided by operating activities was '
            f'${_num(fy2026.cash_flow["cash_from_operations"])} million.',
            'body',
        )
    )
    story.heading('Controls and signatures', 'h2')
    story.add(
        _para(
            'Management concluded that internal control over financial reporting was effective as of '
            'January 31, 2026. The consolidated financial statements were audited by an independent registered '
            'public accounting firm.',
            'body',
        )
    )
    story.add(Spacer(1, 0.25 * inch))
    story.add(
        _table(
            ('Signature', 'Title', 'Date'),
            [
                ('/s/ Authorised Signatory', 'Chief Executive Officer', 'March 6, 2026'),
                ('/s/ Authorised Signatory', 'Chief Financial Officer', 'March 6, 2026'),
            ],
            (2.6, 2.6, 1.5),
        )
    )

    filename = 'pdf__company-b__2026-FY__annual-report.pdf'
    path = out_dir / filename
    _pdf(
        path,
        story,
        'Company B, Inc. - Form 10-K - fiscal year ended January 31, 2026',
        'Company B, Inc. Form 10-K fiscal 2026',
    )
    pages = _pdf_sections(path, 7)
    meta = DocumentMeta(
        filename=filename,
        file_type='pdf',
        category='annual_report',
        company='company-b',
        period='FY2026',
        status='final',
        pages=len(pages),
        features=('text', 'tables', 'multi_page', 'headings'),
        notes='Second company, used for isolation and comparison questions. Income statement page 4, balance sheet page 5, cash flow page 6.',
        source='SEC XBRL companyfacts, CIK 0001108524, FY2026 (2025-02-01..2026-01-31)',
    )
    return GeneratedDocument(meta, path, _finalise_sections(story.sections))


# --- company A draft (superseded) -------------------------------------------


def company_a_draft(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    """A superseded draft that carries earlier, wrong headline numbers.

    It exists so the golden set can check that answers come from the latest
    final version of a document, not from whichever copy the retriever found.
    """
    fy2025 = model.annual[0].income
    preliminary_revenue = 414_800.0
    preliminary_net_income = 111_200.0
    preliminary_operating_income = 132_600.0
    story = _Story()

    story.add(Spacer(1, 0.9 * inch))
    story.add(_para('DRAFT - NOT FOR DISTRIBUTION', 'warning'))
    story.add(Spacer(1, 0.2 * inch))
    story.add(_para('COMPANY A, INC.', 'cover_name'))
    story.add(Spacer(1, 0.2 * inch))
    story.add(_para('Fiscal 2025 preliminary results', 'cover_kicker'))
    story.add(Spacer(1, 0.3 * inch))
    story.add(_para('Prepared October 2, 2025 for the Audit Committee', 'cover_body'))
    story.add(Spacer(1, 0.45 * inch))
    story.add(
        _para(
            'This draft was superseded by the final annual report for the fiscal year ended September 27, 2025 '
            '(document pdf__company-a__2025-FY__annual-report.pdf). The figures below are preliminary and '
            'must not be used for external reporting.',
            'body',
        )
    )
    story.heading('Preliminary headline figures')
    story.label('Preliminary headline figures')
    story.add(
        _table(
            ('USD millions', 'Preliminary'),
            [
                ('Total net revenue', _num(preliminary_revenue)),
                ('Operating income', _num(preliminary_operating_income)),
                ('Net income', _num(preliminary_net_income)),
            ],
            (3.4, 1.5),
        )
    )

    story.new_page()
    story.heading('Revision log')
    story.add(
        _para(
            'The final close adjusted three headline lines. The final annual report is authoritative.',
            'body',
        )
    )
    story.label('Revision log')
    story.add(
        _table(
            ('Line', 'Preliminary', 'Final', 'Reason for the change'),
            [
                (
                    'Total net revenue',
                    _num(preliminary_revenue),
                    _num(fy2025['revenue']),
                    'Final revenue adjustments',
                ),
                (
                    'Operating income',
                    _num(preliminary_operating_income),
                    _num(fy2025['operating_income']),
                    'Accrual release',
                ),
                (
                    'Net income',
                    _num(preliminary_net_income),
                    _num(fy2025['net_income']),
                    'Tax provision true-up',
                ),
            ],
            (2.0, 1.1, 1.1, 2.3),
        )
    )
    story.add(Spacer(1, 0.2 * inch))
    story.add(
        _para(
            'Status: superseded on October 31, 2025. Retention: keep for one fiscal year for audit trail purposes.',
            'small',
        )
    )

    filename = 'pdf__company-a__2025-FY__annual-report-draft.pdf'
    path = out_dir / filename
    _pdf(
        path,
        story,
        'Company A, Inc. - DRAFT - superseded October 31, 2025',
        'Company A, Inc. draft fiscal 2025',
    )
    pages = _pdf_sections(path, 2)
    meta = DocumentMeta(
        filename=filename,
        file_type='pdf',
        category='draft',
        company='company-a',
        period='FY2025',
        status='draft',
        pages=len(pages),
        features=('text', 'tables', 'superseded', 'multi_page'),
        notes='Superseded draft with preliminary totals. Answers must come from the final annual report.',
        source='SEC XBRL companyfacts, CIK 0000320193, FY2025 (2024-09-29..2025-09-27), preliminary values',
    )
    return GeneratedDocument(meta, path, _finalise_sections(story.sections))


# --- raster helpers ---------------------------------------------------------

FONT_REGULAR_CANDIDATES = (
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
)
FONT_BOLD_CANDIDATES = (
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/Library/Fonts/Arial Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
)


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: object) -> float:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return float(right - left)


def _right_text(
    draw: ImageDraw.ImageDraw,
    right: int,
    y: int,
    text: str,
    font: object,
    fill: tuple[int, int, int],
) -> None:
    width = _text_width(draw, text, font)
    draw.text((right - width, y), text, font=font, fill=fill)


def _scan_effect(image: Image.Image, *, seed: int = 11, angle: float = -0.5) -> Image.Image:
    """Add light speckle and a small rotation so the page looks scanned."""
    rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=(255, 255, 255))
    draw = ImageDraw.Draw(rotated)
    # Deterministic speckle for a scanning artefact, not a security primitive.
    random_source = random.Random(seed)  # noqa: S311 - speckle, not cryptography
    for _ in range(600):
        x = random_source.randrange(rotated.width)
        y = random_source.randrange(rotated.height)
        grey = random_source.randint(170, 220)
        draw.point((x, y), fill=(grey, grey, grey))
    return rotated.filter(ImageFilter.GaussianBlur(0.4))


def _image_pdf(path: Path, pages: list[Image.Image], *, dpi: float = 150.0) -> None:
    """Write a PDF that contains only the images, with no text layer.

    Pillow's PDF writer stamps the current time, so it is not byte-stable. A
    reportlab canvas with ``invariant`` keeps every rebuild identical.
    """
    pdf: pdfcanvas.Canvas | None = None
    for image in pages:
        page = (image.width * 72.0 / dpi, image.height * 72.0 / dpi)
        if pdf is None:
            pdf = pdfcanvas.Canvas(str(path), pagesize=page, invariant=1)
        pdf.setPageSize(page)
        # A scan is photographic: JPEG keeps the file small, and reportlab then
        # embeds the bytes directly instead of recompressing them.
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        buffer.seek(0)
        pdf.drawImage(ImageReader(buffer), 0, 0, width=page[0], height=page[1])
        pdf.showPage()
    if pdf is None:
        msg = 'an image-only PDF needs at least one page'
        raise ValueError(msg)
    pdf.save()


def _bank_notice_page(width: int, height: int) -> Image.Image:
    """A heavily degraded second page, used to exercise the low-confidence path.

    The text is real but the blur and speckle are strong enough that a reader
    should report low OCR confidence instead of guessing at the words.
    """
    page = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    font_title = _load_font(36, bold=True)
    font_body = _load_font(21)
    draw.text((90, 90), 'IMPORTANT INFORMATION', font=font_title, fill=(30, 30, 30))
    lines = (
        'This page is part of your statement and should be kept for your records.',
        'Rates and fees are set out in the account agreement for this account.',
        'Please check every entry and tell us about an error within thirty days.',
        'The bank may correct an entry that was posted in error.',
        'This statement is issued by the bank named on the first page.',
    )
    y = 210
    for line in lines:
        draw.text((90, y), line, font=font_body, fill=(55, 55, 55))
        y += 52
    page = page.filter(ImageFilter.GaussianBlur(3.4))
    draw = ImageDraw.Draw(page)
    source = random.Random(23)  # noqa: S311 - speckle, not cryptography
    for _ in range(2500):
        x = source.randrange(page.width)
        y = source.randrange(page.height)
        grey = source.randint(120, 210)
        draw.point((x, y), fill=(grey, grey, grey))
    return page.filter(ImageFilter.GaussianBlur(0.9))


# --- bank statement (image only) -------------------------------------------


def company_a_bank_statement(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    width, height = 1275, 1650
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    ink = (25, 25, 25)
    muted = (90, 90, 90)
    font_title = _load_font(38, bold=True)
    font_h2 = _load_font(24, bold=True)
    font_body = _load_font(20)
    font_small = _load_font(17)

    opening = docdata.bank_opening_balance(model)
    closing = docdata.bank_closing_balance(model)
    total_in = sum(amount for _, _, amount in docdata.BANK_TRANSACTIONS if amount > 0)
    total_out = sum(-amount for _, _, amount in docdata.BANK_TRANSACTIONS if amount < 0)
    if round(opening + total_in - total_out, 2) != round(closing, 2):
        msg = 'Bank statement activity does not reconcile to the closing balance'
        raise AssertionError(msg)

    left, right = 90, width - 90
    draw.text((left, 70), docdata.BANK_NAME.upper(), font=font_title, fill=ink)
    draw.text((left, 118), 'BUSINESS CHECKING STATEMENT', font=font_h2, fill=muted)
    draw.line((left, 165, right, 165), fill=ink, width=2)
    draw.text(
        (left, 190),
        f'Statement period: {docdata.BANK_STATEMENT_PERIOD[0]} to {docdata.BANK_STATEMENT_PERIOD[1]}',
        font=font_body,
        fill=ink,
    )
    draw.text((left, 220), 'Account holder: Company A, Inc.', font=font_body, fill=ink)
    draw.text(
        (left, 250),
        'Address: 1200 Harbour Way, Wilmington, Delaware 19801',
        font=font_body,
        fill=ink,
    )
    draw.text((left, 280), f'Account: {docdata.BANK_ACCOUNT_LABEL}', font=font_body, fill=ink)
    draw.text((left, 310), 'Currency: USD', font=font_body, fill=ink)

    y = 380
    draw.text((left, y), 'Account summary', font=font_h2, fill=ink)
    y += 45
    summary = (
        ('Beginning balance', opening),
        ('Total credits', total_in),
        ('Total debits', total_out),
        ('Ending balance', closing),
    )
    for label, amount in summary:
        draw.text((left, y), label, font=font_body, fill=ink)
        _right_text(draw, right, y, f'{amount:,.2f}', font_body, ink)
        y += 34
        draw.line((left, y - 4, right, y - 4), fill=(210, 210, 210), width=1)

    y += 45
    draw.text((left, y), 'Transaction detail', font=font_h2, fill=ink)
    y += 45
    draw.text((left, y), 'Date', font=font_small, fill=muted)
    draw.text((left + 180, y), 'Description', font=font_small, fill=muted)
    _right_text(draw, right, y, 'Amount (USD)', font_small, muted)
    y += 28
    draw.line((left, y, right, y), fill=ink, width=1)
    y += 12
    for date, description, amount in docdata.BANK_TRANSACTIONS:
        draw.text((left, y), date, font=font_body, fill=ink)
        draw.text((left + 180, y), description, font=font_body, fill=ink)
        _right_text(draw, right, y, f'{amount:,.2f}', font_body, ink)
        y += 36
    draw.line((left, y, right, y), fill=ink, width=1)
    y += 14
    draw.text((left, y), 'Closing balance', font=font_h2, fill=ink)
    _right_text(draw, right, y, f'{closing:,.2f}', font_h2, ink)

    draw.line((left, 1500, right, 1500), fill=(210, 210, 210), width=1)
    draw.text((left, 1520), f'{docdata.BANK_NAME}. Member FDIC.', font=font_small, fill=muted)
    _right_text(draw, right, 1520, 'Page 1 of 2', font_small, muted)

    scanned = _scan_effect(image, seed=17, angle=-0.6)
    filename = 'scan__company-a__2026-Q3__bank-statement.pdf'
    path = out_dir / filename
    _image_pdf(path, [scanned, _bank_notice_page(width, height)])

    sections = {
        1: (
            'Business checking statement',
            'Account summary',
            'Transaction detail',
        ),
        2: ('Important information',),
    }
    meta = DocumentMeta(
        filename=filename,
        file_type='scan',
        category='bank_statement',
        company='company-a',
        period='Q3 FY2026',
        status='final',
        pages=2,
        features=('ocr', 'image_only', 'slight_skew', 'speckle', 'low_confidence_page'),
        notes='Image-only PDF at 150 dpi. Page 2 is badly degraded so OCR confidence is low. No text layer on either page, so the reader must use OCR.',
    )
    return GeneratedDocument(meta, path, sections)


# --- vendor invoice (single image) -----------------------------------------


def company_a_invoice(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    del model
    width, height = 1275, 1650
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    ink = (20, 20, 20)
    muted = (95, 95, 95)
    font_big = _load_font(40, bold=True)
    font_h2 = _load_font(24, bold=True)
    font_body = _load_font(20)
    font_small = _load_font(17)

    left, right = 90, width - 90
    draw.text((left, 80), docdata.INVOICE_VENDOR.upper(), font=font_big, fill=ink)
    draw.text(
        (left, 132), '18 Cedar Ridge Road, Dover, Delaware 19901', font=font_small, fill=muted
    )
    draw.text((left, 158), 'Remit to: account ending 8842', font=font_small, fill=muted)
    _right_text(draw, right, 80, 'INVOICE', font_big, ink)
    draw.line((left, 210, right, 210), fill=ink, width=2)

    details = (
        ('Invoice number', docdata.INVOICE_NUMBER),
        ('Invoice date', docdata.INVOICE_DATE),
        ('Due date', docdata.INVOICE_DUE_DATE),
        ('Payment terms', docdata.INVOICE_TERMS),
        ('Purchase order', docdata.INVOICE_PO),
    )
    y = 240
    for label, value in details:
        draw.text((left, y), f'{label}:', font=font_body, fill=muted)
        draw.text((left + 260, y), value, font=font_body, fill=ink)
        y += 32

    y += 20
    draw.text((left, y), 'Bill to', font=font_h2, fill=ink)
    y += 36
    for line in (
        docdata.INVOICE_CUSTOMER,
        'Accounts Payable',
        '1200 Harbour Way, Wilmington, Delaware 19801',
    ):
        draw.text((left, y), line, font=font_body, fill=ink)
        y += 30

    y += 40
    draw.text((left, y), 'Description', font=font_small, fill=muted)
    _right_text(draw, right - 300, y, 'Qty', font_small, muted)
    _right_text(draw, right - 170, y, 'Unit price', font_small, muted)
    _right_text(draw, right, y, 'Amount (USD)', font_small, muted)
    y += 26
    draw.line((left, y, right, y), fill=ink, width=1)
    y += 12
    for description, quantity, price in docdata.INVOICE_LINES:
        draw.text((left, y), description, font=font_body, fill=ink)
        _right_text(draw, right - 300, y, str(quantity), font_body, ink)
        _right_text(draw, right - 170, y, f'{price:,.2f}', font_body, ink)
        _right_text(draw, right, y, f'{quantity * price:,.2f}', font_body, ink)
        y += 38
    draw.line((left, y, right, y), fill=ink, width=1)

    y += 20
    for label, value, bold in (
        ('Subtotal', docdata.invoice_subtotal(), False),
        (f'Sales tax ({docdata.INVOICE_TAX_RATE * 100:.1f}%)', docdata.invoice_tax(), False),
        ('Total due', docdata.invoice_total(), True),
    ):
        font = font_h2 if bold else font_body
        draw.text((right - 520, y), label, font=font, fill=ink)
        _right_text(draw, right, y, f'{value:,.2f}', font, ink)
        y += 40

    y += 40
    draw.text((left, y), f'Payment is due by {docdata.INVOICE_DUE_DATE}.', font=font_body, fill=ink)
    draw.text(
        (left, y + 34), 'Quote the invoice number with your payment.', font=font_body, fill=ink
    )

    draw.line((left, 1500, right, 1500), fill=(210, 210, 210), width=1)
    draw.text(
        (left, 1520),
        'Fictional training and test fixture. Vendor and payment details are invented.',
        font=font_small,
        fill=muted,
    )

    filename = 'image__company-a__2025-FY__vendor-invoice.png'
    path = out_dir / filename
    image.save(path, 'PNG', optimize=True)

    sections = {1: ('Invoice header', 'Invoice lines', 'Invoice totals')}
    meta = DocumentMeta(
        filename=filename,
        file_type='image',
        category='invoice',
        company='company-a',
        period='FY2025',
        status='final',
        pages=1,
        features=('ocr', 'image_only', 'table'),
        notes='Single-page PNG invoice. The reader must run OCR.',
    )
    return GeneratedDocument(meta, path, sections)


# --- budget vs actual workbook ---------------------------------------------


def company_a_budget(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    rows = docdata.budget_rows(model)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Budget vs Actual'

    sheet['A1'] = 'Company A, Inc. - FY2025 budget vs actual'
    sheet['A2'] = 'All amounts in USD millions'
    sheet['A4'] = 'Line item'
    sheet['B4'] = 'FY2025 budget'
    sheet['C4'] = 'FY2025 actual'
    sheet['D4'] = 'Variance'
    sheet['E4'] = 'Variance (%)'
    for offset, row in enumerate(rows, start=5):
        sheet.cell(row=offset, column=1, value=row.line)
        sheet.cell(row=offset, column=2, value=row.budget).number_format = '#,##0'
        sheet.cell(row=offset, column=3, value=row.actual).number_format = '#,##0'
        sheet.cell(row=offset, column=4, value=row.variance).number_format = '#,##0'
        sheet.cell(row=offset, column=5, value=row.variance_pct).number_format = '0.0'
    sheet['A14'] = (
        'Variance = actual minus budget. Positive is favourable for revenue and profit lines.'
    )
    sheet['A15'] = 'Variance (%) is shown as a percentage number, so 1.5 means 1.5%.'

    sheet['A1'].font = Font(bold=True, size=13)
    sheet['A2'].font = Font(italic=True, size=10)
    for cell in ('A4', 'B4', 'C4', 'D4', 'E4'):
        sheet[cell].font = Font(bold=True)
        sheet[cell].alignment = Alignment(horizontal='right' if cell != 'A4' else 'left')
    sheet.column_dimensions['A'].width = 46
    for column in ('B', 'C', 'D', 'E'):
        sheet.column_dimensions[column].width = 16

    assumptions = workbook.create_sheet('Assumptions')
    assumptions.append(['Assumption', 'Value'])
    assumptions.append(['Annual plan locked', '2024-03-15'])
    assumptions.append(['Plan approved by', 'Chief Financial Officer'])
    assumptions.append(['Budget contingency held (%)', 0.0])
    assumptions.append(['Currency', 'USD'])
    assumptions.append(['Units', 'millions'])
    assumptions['A1'].font = Font(bold=True)
    assumptions['B1'].font = Font(bold=True)
    assumptions.column_dimensions['A'].width = 34
    assumptions.column_dimensions['B'].width = 26

    filename = 'xlsx__company-a__2025-FY__budget-vs-actual.xlsx'
    path = out_dir / filename
    workbook.properties.created = PACKAGE_TIMESTAMP
    workbook.properties.modified = PACKAGE_TIMESTAMP
    workbook.properties.creator = 'FinSight AI fixture builder'
    workbook.properties.lastModifiedBy = 'FinSight AI fixture builder'
    # Workbook.save() stamps the current time into docProps/core.xml, so write
    # through the writer directly and then pin the zip timestamps.
    archive = zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True)
    ExcelWriter(workbook, archive).save()
    _normalise_package(path)

    sections = {
        1: ('Budget vs Actual sheet', 'Assumptions sheet'),
    }
    meta = DocumentMeta(
        filename=filename,
        file_type='xlsx',
        category='budget',
        company='company-a',
        period='FY2025',
        status='final',
        pages=1,
        features=('tables', 'two_sheets', 'units_in_header'),
        notes='Two sheets. Values are USD millions; variance (%) is stored as a percentage number.',
    )
    return GeneratedDocument(meta, path, sections)


# --- general ledger extract -------------------------------------------------


def company_a_ledger(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    del model
    filename = 'csv__company-a__2025-FY__q4-ledger.csv'
    path = out_dir / filename
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, delimiter=';', lineterminator='\n')
        writer.writerow(docdata.LEDGER_COLUMNS)
        for row in docdata.LEDGER_ROWS:
            date, code, name, centre, description, debit, credit = row
            writer.writerow(
                [date, code, name, centre, description, f'{debit:.2f}', f'{credit:.2f}']
            )

    sections = {1: ('General ledger extract',)}
    meta = DocumentMeta(
        filename=filename,
        file_type='csv',
        category='ledger',
        company='company-a',
        period='Q4 FY2025',
        status='final',
        pages=1,
        features=('semicolon_delimiter', 'header_row', 'no_totals'),
        notes='Semicolon-delimited expense extract for 2025-06-29 to 2025-09-27. Amounts in USD, not millions.',
    )
    return GeneratedDocument(meta, path, sections)


# --- company B revenue by region -------------------------------------------


def company_b_regions(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    rows = docdata.region_rows(model)
    filename = 'csv__company-b__2026-FY__revenue-by-region.csv'
    path = out_dir / filename
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(docdata.REGION_COLUMNS)
        for row in rows:
            writer.writerow([row[0], *[f'{value:,.1f}' for value in row[1:]]])
        writer.writerow(
            [
                'Total',
                *[f'{sum(row[index] for row in rows):,.1f}' for index in (1, 2, 3)],
            ]
        )

    sections = {1: ('Revenue by region',)}
    meta = DocumentMeta(
        filename=filename,
        file_type='csv',
        category='revenue_by_region',
        company='company-b',
        period='FY2026',
        status='final',
        pages=1,
        features=('comma_delimiter', 'header_row', 'total_row'),
        notes='Regional revenue in USD millions for FY2024 to FY2026. The total row matches the annual report.',
    )
    return GeneratedDocument(meta, path, sections)


# --- board minutes ----------------------------------------------------------


def company_a_board_notes(model: CompanyModel, out_dir: Path) -> GeneratedDocument:
    document = DocxDocument()
    document.core_properties.title = 'Company A, Inc. finance committee minutes'
    document.core_properties.author = 'Company A, Inc.'
    document.core_properties.comments = 'Fictional training and test fixture.'

    document.add_heading('Company A, Inc. - Finance Committee of the Board', level=1)
    document.add_paragraph('Minutes of the meeting held on 14 October 2025')
    document.add_paragraph('Location: 1200 Harbour Way, Wilmington, Delaware 19801')

    document.add_heading('Attendance', level=2)
    for attendee in docdata.BOARD_ATTENDEES:
        document.add_paragraph(attendee, style='List Bullet')
    document.add_paragraph('Apologies: ' + ', '.join(docdata.BOARD_APOLOGIES))
    document.add_paragraph(docdata.BOARD_QUORUM)

    document.add_heading('1. Fiscal 2025 results', level=2)
    document.add_paragraph(
        f'The Chief Financial Officer presented the fiscal 2025 result. Total net revenue was '
        f'${_num(docdata.board_headline_revenue(model))} million and net income was '
        f'${_num(docdata.board_headline_net_income(model))} million. The Committee noted that the '
        f'audit is complete and that no material weaknesses were identified.'
    )

    document.add_heading('2. Capital return', level=2)
    document.add_paragraph(
        'The Committee reviewed the capital return framework and recommended the following decisions '
        'to the full Board.'
    )
    decision_table = document.add_table(rows=1, cols=3)
    decision_table.style = 'Table Grid'
    for index, title in enumerate(('Decision', 'Owner', 'Effective date')):
        decision_table.rows[0].cells[index].text = title
    for decision, owner, effective in docdata.BOARD_DECISIONS:
        cells = decision_table.add_row().cells
        cells[0].text = decision
        cells[1].text = owner
        cells[2].text = effective

    document.add_heading('3. Principal risks', level=2)
    for risk in (
        'Foreign exchange volatility affecting reported revenue.',
        'Concentration of manufacturing partners in a single region.',
        'Reliance on third-party logistics providers during the peak quarter.',
        'Changes in income tax rules in the company\u2019s main markets.',
    ):
        document.add_paragraph(risk, style='List Number')

    document.add_heading('4. Fiscal 2026 plan', level=2)
    document.add_paragraph(
        'The Committee approved the planning timetable. The operating plan is due on 28 November 2025 '
        'and the capital plan on 12 December 2025. General and administrative headcount is held flat '
        'through the first half of the year.'
    )

    document.add_heading('5. Actions', level=2)
    action_table = document.add_table(rows=1, cols=3)
    action_table.style = 'Table Grid'
    for index, title in enumerate(('Action', 'Owner', 'Due date')):
        action_table.rows[0].cells[index].text = title
    for action, owner, due in (
        ('Circulate the revised capital return policy', 'Chief Financial Officer', '2025-10-31'),
        ('Confirm the peak-season logistics capacity plan', 'Head of Internal Audit', '2025-11-21'),
        ('Present the fiscal 2026 operating plan', 'Chief Executive Officer', '2025-11-28'),
    ):
        cells = action_table.add_row().cells
        cells[0].text = action
        cells[1].text = owner
        cells[2].text = due

    document.add_heading('Next meeting', level=2)
    document.add_paragraph(f'The next meeting is scheduled for {docdata.BOARD_NEXT_MEETING}.')

    filename = 'docx__company-a__2025-FY__board-notes.docx'
    path = out_dir / filename
    document.core_properties.created = PACKAGE_TIMESTAMP
    document.core_properties.modified = PACKAGE_TIMESTAMP
    document.core_properties.last_modified_by = 'FinSight AI fixture builder'
    document.core_properties.author = 'Company A, Inc.'
    document.core_properties.revision = 1
    document.save(path)
    _normalise_package(path)

    sections = {
        1: (
            'Attendance',
            '1. Fiscal 2025 results',
            '2. Capital return',
            '3. Principal risks',
            '4. Fiscal 2026 plan',
            '5. Actions',
            'Next meeting',
        )
    }
    meta = DocumentMeta(
        filename=filename,
        file_type='docx',
        category='board_notes',
        company='company-a',
        period='FY2025',
        status='final',
        pages=2,
        features=('paragraphs', 'bullets', 'numbered_list', 'tables', 'headers'),
        notes='Finance committee minutes. Two tables (decisions, actions). Page count is approximate because DOCX pagination is renderer-dependent.',
    )
    return GeneratedDocument(meta, path, sections)


# --- assembly ---------------------------------------------------------------


def build_all(
    model_a: CompanyModel, model_b: CompanyModel, out_dir: Path = OUTPUT_DIR
) -> list[GeneratedDocument]:
    """Write every sample document and return their metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    return [
        company_a_annual(model_a, out_dir),
        company_a_interim(model_a, out_dir),
        company_a_draft(model_a, out_dir),
        company_b_annual(model_b, out_dir),
        company_a_bank_statement(model_a, out_dir),
        company_a_invoice(model_a, out_dir),
        company_a_budget(model_a, out_dir),
        company_a_ledger(model_a, out_dir),
        company_a_board_notes(model_a, out_dir),
        company_b_regions(model_b, out_dir),
    ]


MANIFEST_HEADER = """# Sample document manifest.
# Every file in this folder has one entry. Tests use this to find documents by
# type, company and feature instead of hard-coding file names.
#
# Generated by `uv run python scripts/fixture_builder`. Do not edit by hand.
#
# status is `final` or `draft`. A draft is kept for the audit trail only: answers
# must come from the latest final version of a document.
"""


def write_manifest(docs: list[GeneratedDocument], path: Path) -> None:
    entries = []
    for doc in docs:
        entry: dict[str, object] = {
            'path': doc.meta.filename,
            'file_type': doc.meta.file_type,
            'category': doc.meta.category,
            'company': doc.meta.company,
            'period': doc.meta.period,
            'status': doc.meta.status,
            'pages': doc.meta.pages,
            'features': list(doc.meta.features),
            'anonymized': True,
        }
        if doc.meta.source:
            entry['source'] = doc.meta.source
        entry['notes'] = doc.meta.notes
        entries.append(entry)
    body = yamlout.dump({'version': 1, 'documents': entries})
    path.write_text(MANIFEST_HEADER + body, encoding='utf-8')
