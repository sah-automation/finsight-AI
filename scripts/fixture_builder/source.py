"""Read real, public financial facts from SEC XBRL and hand them to the builder.

Only two things happen here: fetch a company's XBRL facts once, and pick the
value for a logical line at an exact period. Everything downstream (documents,
questions) works from those values, so a question can always be recomputed.

SEC requires a descriptive User-Agent. Their edge rejects most non-browser
agents, so the browser-shaped string below is paired with a real contact in the
From header.
"""

from __future__ import annotations

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

SEC_FACTS_URL = 'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
CONTACT = 'sah-automation@users.noreply.github.com'
REQUEST_TIMEOUT_SECONDS = 60
CACHE_DIR = Path(tempfile.gettempdir()) / 'finsight-fixtures'
CACHE_TTL_SECONDS = 24 * 60 * 60

# Candidate tags per logical line, most specific first. Filers change tags over
# the years, so the first match wins.
TAGS: dict[str, tuple[str, ...]] = {
    'revenue': (
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'Revenues',
        'SalesRevenueNet',
    ),
    'cogs': ('CostOfGoodsAndServicesSold', 'CostOfRevenue', 'CostOfGoodsSold'),
    'rnd': ('ResearchAndDevelopmentExpense',),
    'sga': ('SellingGeneralAndAdministrativeExpense', 'GeneralAndAdministrativeExpense'),
    'opex_total': ('OperatingExpenses',),
    'op_income': ('OperatingIncomeLoss',),
    'pretax': (
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
        'IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments',
    ),
    'tax': ('IncomeTaxExpenseBenefit',),
    'net_income': ('NetIncomeLoss',),
    'eps_basic': ('EarningsPerShareBasic',),
    'eps_diluted': ('EarningsPerShareDiluted',),
    'shares_basic': ('WeightedAverageNumberOfSharesOutstandingBasic',),
    'shares_diluted': ('WeightedAverageNumberOfDilutedSharesOutstanding',),
    'cash': ('CashAndCashEquivalentsAtCarryingValue',),
    'st_investments': ('ShortTermInvestments', 'MarketableSecuritiesCurrent'),
    'ar': ('AccountsReceivableNetCurrent',),
    'inventory': ('InventoryNet',),
    'other_current_assets': ('OtherAssetsCurrent',),
    'assets_current': ('AssetsCurrent',),
    'ppe': ('PropertyPlantAndEquipmentNet',),
    'goodwill': ('Goodwill',),
    'intangibles': ('FiniteLivedIntangibleAssetsNet', 'IntangibleAssetsNetExcludingGoodwill'),
    'assets_noncurrent_other': ('OtherAssetsNoncurrent',),
    'assets': ('Assets',),
    'ap': ('AccountsPayableCurrent',),
    'accrued': ('AccruedLiabilitiesCurrent',),
    'deferred_revenue': ('ContractWithCustomerLiabilityCurrent', 'DeferredRevenueCurrent'),
    'liab_current': ('LiabilitiesCurrent',),
    'lt_debt': ('LongTermDebtNoncurrent', 'LongTermDebt'),
    'other_liab_noncurrent': ('OtherLiabilitiesNoncurrent',),
    'liabilities': ('Liabilities',),
    'common_stock_apic': (
        'CommonStocksIncludingAdditionalPaidInCapital',
        'AdditionalPaidInCapitalCommonStock',
    ),
    'retained': ('RetainedEarningsAccumulatedDeficit',),
    'aoci': ('AccumulatedOtherComprehensiveIncomeLossNetOfTax',),
    'equity': ('StockholdersEquity',),
    'cfo': ('NetCashProvidedByUsedInOperatingActivities',),
    'cfi': ('NetCashProvidedByUsedInInvestingActivities',),
    'cff': ('NetCashProvidedByUsedInFinancingActivities',),
    'dep_amort': (
        'DepreciationDepletionAndAmortization',
        'DepreciationAmortizationAndAccretionNet',
    ),
    'sbc': ('ShareBasedCompensation',),
    'capex': ('PaymentsToAcquirePropertyPlantAndEquipment',),
}


@dataclass(frozen=True)
class Period:
    """An exact duration, so a value can never be picked from a nearby period."""

    label: str
    start: str
    end: str
    form: str


@dataclass(frozen=True)
class Company:
    key: str
    cik: str
    name: str


@dataclass(frozen=True)
class Fact:
    value: float
    tag: str
    unit: str
    filed: str


def fetch_company_facts(
    company: Company,
    session: requests.Session | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    """Download the company's XBRL facts, reusing a local cache for a day.

    The cache keeps repeated builds fast and makes a rebuild deterministic while
    the published facts cannot change. Pass ``refresh=True`` to refetch.
    """
    cache_file = CACHE_DIR / f'companyfacts-CIK{company.cik}.json'
    fresh_enough = (
        cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_TTL_SECONDS
    )
    if fresh_enough and not refresh:
        cached: dict[str, Any] = json.loads(cache_file.read_text(encoding='utf-8'))
        return cached

    client = session or requests.Session()
    response = client.get(
        SEC_FACTS_URL.format(cik=company.cik),
        headers={'User-Agent': USER_AGENT, 'From': CONTACT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(response.text, encoding='utf-8')
    facts: dict[str, Any] = response.json()
    return facts


def _rows(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    units = facts.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {})
    rows: list[dict[str, Any]] = []
    for unit, entries in units.items():
        for entry in entries:
            rows.append({'unit': unit, **entry})
    return rows


def duration(facts: dict[str, Any], line: str, period: Period, unit: str = 'USD') -> Fact | None:
    """Return the value for a logical line over an exact start/end duration."""
    for tag in TAGS[line]:
        matches = [
            row
            for row in _rows(facts, tag)
            if row.get('start') == period.start
            and row.get('end') == period.end
            and row.get('unit') == unit
        ]
        if matches:
            latest = max(matches, key=lambda row: row.get('filed', ''))
            return Fact(float(latest['val']), tag, unit, latest.get('filed', ''))
    return None


def instant(facts: dict[str, Any], line: str, end: str, unit: str = 'USD') -> Fact | None:
    """Return the value for a logical line at an exact instant (balance sheet)."""
    for tag in TAGS[line]:
        matches = [
            row
            for row in _rows(facts, tag)
            if row.get('end') == end and 'start' not in row and row.get('unit') == unit
        ]
        if matches:
            latest = max(matches, key=lambda row: row.get('filed', ''))
            return Fact(float(latest['val']), tag, unit, latest.get('filed', ''))
    return None


def required(fact: Fact | None, what: str) -> Fact:
    """Fail loudly instead of quietly substituting a zero."""
    if fact is None:
        msg = f'Missing SEC fact: {what}'
        raise LookupError(msg)
    return fact


def dump(company: Company, periods: list[Period], instants: list[str]) -> dict[str, Any]:
    """Extract every configured line for the given periods and instants."""
    facts = fetch_company_facts(company)
    out: dict[str, Any] = {'company': company.name, 'periods': {}, 'instants': {}}
    for period in periods:
        values: dict[str, float | None] = {}
        for line in TAGS:
            fact = duration(facts, line, period)
            values[line] = fact.value if fact else None
        out['periods'][period.label] = values
    for end in instants:
        values = {}
        for line in TAGS:
            fact = instant(facts, line, end)
            values[line] = fact.value if fact else None
        out['instants'][end] = values
    return out


if __name__ == '__main__':
    print(json.dumps({'source': 'use builder.cli'}, indent=2))
