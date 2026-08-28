"""
ah-disclosure-kit analysis JSON -> StockValuation.io external valuation input.

This module is deliberately self-contained (no imports from mcp_tools.py) so
it can be unit-tested on its own. mcp_tools.py imports from here.

Two layers:
  1. company_data_from_ah_disclosure(): pure function, ah-disclosure JSON ->
     CompanyDataDTO-shaped dict + a list of human-readable gaps.
  2. MCP-facing helpers (review token, payload builders) mirroring the
     stockvaluation.extract_prospectus / value_prospectus pattern already in
     this codebase, so ah-disclosure gets the same "extract -> human review
     gate -> value" workflow instead of silently trusting unreviewed numbers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


# ---------------------------------------------------------------------------
# Layer 1: ah-disclosure JSON -> CompanyDataDTO
# ---------------------------------------------------------------------------

def infer_a_share_suffix(symbol: str) -> str:
    if symbol.startswith(("600", "601", "603", "605", "688")):
        return "SH"
    if symbol.startswith(("000", "001", "002", "003", "300", "301")):
        return "SZ"
    if symbol.startswith(("83", "87", "88", "43")):
        return "BJ"
    raise ValueError(f"Unrecognized A-share symbol prefix: {symbol}")


def a_share_ticker(symbol: str) -> str:
    return f"{symbol}.{infer_a_share_suffix(symbol)}"


# ---------------------------------------------------------------------------
# CAPM-based initialCostCapital estimate
#
# The app's own DB-backed Damodaran industry cost-of-capital lookup
# (CostOfCapitalService / CompanyDataAssemblyService.costOfCapital via
# Helper.costOfCapital) requires seeded reference tables (cost_of_capital,
# sector_mapping, industry_averages_us/global) that are NOT populated in a
# fresh local Postgres -- confirmed empty on 2026-08-27. Rather than silently
# fall back to a guessed placeholder, or try to replicate a DB lookup we
# don't have the data for, this computes a standalone, source-cited CAPM
# estimate instead. Swap this out once the app's own reference tables are
# seeded, since that would use real per-industry Damodaran cost-of-capital
# figures rather than a single blended semiconductor-industry beta.
# ---------------------------------------------------------------------------

# Damodaran "Betas by Sector (US)", Semiconductor row, data as of Jan 2026:
# https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html
_SEMICONDUCTOR_UNLEVERED_BETA = 1.49

# App config default (valuation.assumptions.damodaran.mature-market-erp).
_MATURE_MARKET_ERP = 0.0423

# Damodaran country-risk update, July 2026: US baseline ERP 4.45%, China
# total ERP 5.18% -> country risk premium delta ~0.73pp, applied on top of
# the app's own mature-market-erp baseline for internal consistency.
# https://elitecurrensea.com/stocks/damodaran-equity-risk-premiums-july-2026/
_CHINA_COUNTRY_RISK_PREMIUM_DELTA = 0.0073

# App config default (valuation.assumptions.pre-tax-cost-of-debt).
_PRE_TAX_COST_OF_DEBT = 0.05


def estimate_initial_cost_capital(
    *,
    risk_free_rate: float,
    marginal_tax_rate: float,
    debt: float | None,
    equity: float | None,
) -> tuple[float, list[str]]:
    """
    CAPM-based WACC estimate. Returns (initial_cost_capital, notes) where
    notes explain the methodology/sources for the gaps list.
    """
    notes: list[str] = []

    debt = debt or 0.0
    equity = equity or 0.0
    de_ratio = (debt / equity) if equity > 0 else 0.0

    levered_beta = _SEMICONDUCTOR_UNLEVERED_BETA * (1 + (1 - marginal_tax_rate) * de_ratio)
    china_erp = _MATURE_MARKET_ERP + _CHINA_COUNTRY_RISK_PREMIUM_DELTA
    cost_of_equity = risk_free_rate + levered_beta * china_erp

    firm_value = debt + equity
    e_over_v = (equity / firm_value) if firm_value > 0 else 1.0
    d_over_v = (debt / firm_value) if firm_value > 0 else 0.0
    after_tax_cost_of_debt = _PRE_TAX_COST_OF_DEBT * (1 - marginal_tax_rate)

    wacc = e_over_v * cost_of_equity + d_over_v * after_tax_cost_of_debt

    notes.append(
        f"companyDriveDataDTO.initialCostCapital computed via CAPM (not the app's own DB-backed "
        f"Damodaran industry lookup, whose reference tables are unseeded locally): unlevered "
        f"semiconductor beta 1.49 (Damodaran, Jan 2026) relevered to this company's D/E={de_ratio:.4f} "
        f"and {marginal_tax_rate*100:.1f}% tax -> levered beta {levered_beta:.4f}; China ERP "
        f"{china_erp*100:.2f}% (app's {_MATURE_MARKET_ERP*100:.2f}% mature-market-erp config + "
        f"~{_CHINA_COUNTRY_RISK_PREMIUM_DELTA*100:.2f}pp China country-risk delta per Damodaran's "
        f"July 2026 update); cost of equity {cost_of_equity*100:.2f}%; weighted with "
        f"{d_over_v*100:.2f}% debt at {after_tax_cost_of_debt*100:.2f}% after-tax cost of debt "
        f"(app's 5% pre-tax-cost-of-debt config) -> WACC {wacc*100:.2f}%. Swap this out once the "
        f"app's cost_of_capital/sector_mapping/industry_averages tables are seeded with real data."
    )
    return wacc, notes


def company_data_from_ah_disclosure(
    report: dict[str, Any],
    *,
    market_data: dict[str, Any] | None = None,
    marginal_tax_rate_pct: float | None = None,
    risk_free_rate: float | None = None,
    initial_cost_capital: float | None = None,
) -> dict[str, Any]:
    """
    Build a CompanyDataDTO-shaped dict from one ah-disclosure-kit analysis JSON.
    See module docstring for the two-layer design. Returns
    {"ticker": ..., "companyData": {...}, "gaps": [...]}.

    Parameters
    ----------
    risk_free_rate, initial_cost_capital:
        Fractions (e.g. 0.025 for 2.5%), NOT percentage numbers -- unlike
        FinancialDataDTO's tax-rate fields, CompanyDriveDataDTO's fields are
        multiplied by 100 downstream in ValuationWorkflowServiceImpl, so they
        must be supplied as decimals here. If omitted, illustrative
        placeholders are used and flagged in gaps -- both matter a lot to
        WACC/valuation and should be confirmed with a real China risk-free
        rate (e.g. 10Y CGB yield) and a properly computed cost of capital
        before trusting the output.
    """
    market_data = market_data or {}
    gaps: list[str] = []

    ar = report["analysis_result"]
    facts = ar.get("facts", {})
    calc = {c["id"]: c["value"] for c in ar.get("calculations", [])}
    company = ar.get("company", {})
    rep = ar.get("report", {})

    symbol = company.get("symbol") or report.get("scope", {}).get("symbol")
    ticker = a_share_ticker(symbol) if symbol else None

    basic_info: dict[str, Any] = {
        "ticker": ticker,
        "dateOfValuation": rep.get("publish_time"),
        "companyName": company.get("english_name") or company.get("name"),
        "countryOfIncorporation": "China",
        "industryUs": None,
        "industryGlobal": company.get("industry"),
        "currency": "CNY",
        "stockCurrency": "CNY",
        "timeZoneFullName": "Asia/Shanghai",
        "marketCap": market_data.get("market_cap"),
        "beta": market_data.get("beta"),
    }
    if not company.get("industry"):
        gaps.append("industryGlobal: no industry string in report")
    if market_data.get("market_cap") is None:
        gaps.append("marketCap: needs akshare (not in ah-disclosure report)")
    if market_data.get("beta") is None:
        gaps.append("beta: needs a reliable estimate (industry bottom-up beta recommended over raw regression)")
    gaps.append("industryUs left null: no direct mapping from China industry classification to US/Yahoo taxonomy")
    gaps.append("dateOfValuation set to report.publish_time (annual report date); confirm vs 'today'")

    revenue_2025 = facts.get("revenue_2025")
    ebit_2025 = calc.get("ebit_2025")
    fv_gain_2025 = facts.get("fv_change_gain_2025")
    operating_income_adjusted = (
        ebit_2025 - fv_gain_2025 if ebit_2025 is not None and fv_gain_2025 is not None else None
    )

    cash_2025 = facts.get("cash_2025_end")
    money_fund_2025 = facts.get("money_fund_2025_end")
    cash_and_marketable_2025 = (
        (cash_2025 or 0) + (money_fund_2025 or 0) if cash_2025 is not None else None
    )

    financial_data: dict[str, Any] = {
        "revenueTTM": revenue_2025,
        "revenueLTM": facts.get("revenue_2024"),
        "operatingIncomeTTM": ebit_2025,
        "operatingIncomeLTM": None,
        "interestExpenseTTM": None,
        "interestExpenseLTM": None,
        "bookValueEqualityTTM": facts.get("parent_equity_2025_end"),
        "bookValueEqualityLTM": facts.get("parent_equity_2024_end"),
        "bookValueDebtTTM": calc.get("ibd_2025_end"),
        "bookValueDebtLTM": calc.get("ibd_2024_end"),
        "cashAndMarkablTTM": cash_and_marketable_2025,
        "cashAndMarkablLTM": None,
        "nonOperatingAssetTTM": None,
        "nonOperatingAssetLTM": None,
        "minorityInterestTTM": facts.get("minority_interest_2025"),
        "minorityInterestLTM": None,
        "noOfShareOutstanding": market_data.get("no_of_share_outstanding"),
        "basicSharesOutstanding": market_data.get("basic_shares_outstanding"),
        "dilutedSharesOutstanding": market_data.get("diluted_shares_outstanding"),
        "priorDilutedSharesOutstanding": None,
        "stockBasedCompensationTTM": facts.get("share_payment_expense_2025"),
        "stockBasedCompensationLTM": None,
        "stockPrice": market_data.get("stock_price"),
        "lowestStockPrice": market_data.get("lowest_stock_price"),
        "highestStockPrice": market_data.get("highest_stock_price"),
        "previousDayStockPrice": market_data.get("previous_day_stock_price"),
        "effectiveTaxRate": (
            calc.get("etr_2025_pct") / 100 if calc.get("etr_2025_pct") is not None else None
        ),
        "marginalTaxRate": marginal_tax_rate_pct,
        "researchAndDevelopmentMap": (
            {"2025": facts.get("rd_expense_2025")} if facts.get("rd_expense_2025") is not None else None
        ),
        "sourceProvenance": None,
    }

    gaps.append(
        "effectiveTaxRate converted to a fraction (etr_2025_pct/100) before sending -- unlike "
        "marginalTaxRate/riskFreeRate (plain percentage numbers), this field is consumed as a fraction "
        "downstream. Confirmed by a real run: leaving it as 1.7002 produced an absurd 170.02% early-year "
        "taxRate in the DCF projection instead of ~1.70%."
    )
    gaps.append(
        f"operatingIncomeTTM = raw EBIT ({ebit_2025}); ex fair-value-gain "
        f"alternative = {operating_income_adjusted}. Pick one deliberately."
    )
    gaps.append("interestExpenseTTM/LTM: not present as a discrete line item in ah-disclosure facts")
    gaps.append("bookValueEqualityLTM/bookValueDebtLTM/etc use 2024 figures; confirm TTM=current/LTM=prior convention")
    gaps.append("cashAndMarkablLTM (2024): not present in this single-year report")
    gaps.append("minorityInterestLTM (2024): not present in this single-year report")
    if marginal_tax_rate_pct is None:
        gaps.append(
            "marginalTaxRate: left null. effectiveTaxRate from report reflects an "
            "IC-industry tax incentive and is likely NOT representative of terminal-year NOPAT tax rate. "
            "Pass marginal_tax_rate_pct explicitly."
        )
    gaps.append("researchAndDevelopmentMap has only 2025; R&D capitalization needs a multi-year series")
    gaps.append("stockBasedCompensationLTM (2024): not present in this single-year report")

    # ---- CompanyDriveDataDTO ---------------------------------------------
    # Required non-null by ValuationWorkflowServiceImpl.initializeFinancialDataInput
    # (it unconditionally dereferences several of these fields -- a null
    # companyDriveDataDTO, or null revenueNextYear/operatingMarginNextYear/
    # compoundAnnualGrowth2_5/riskFreeRate/initialCostCapital, throws an NPE
    # on the Java side). This plays the same role the ticker-based path gets
    # from Yahoo Finance analyst estimates: a rough machine-derived starting
    # point meant to be refined via guided questions / overrides, not a
    # considered forecast. All fields here are FRACTIONS (0.15 = 15%), unlike
    # FinancialDataDTO's percentage-number convention -- this codebase mixes
    # both conventions across DTOs.
    revenue_growth_fraction = (
        (facts.get("rev_yoy_pct") or calc.get("rev_yoy_pct")) / 100
        if (facts.get("rev_yoy_pct") or calc.get("rev_yoy_pct")) is not None
        else None
    )
    operating_margin_fraction = (
        ebit_2025 / revenue_2025 if ebit_2025 is not None and revenue_2025 else None
    )
    equity_2025 = facts.get("parent_equity_2025_end")
    debt_2025 = calc.get("ibd_2025_end")
    invested_capital_2025 = (
        (equity_2025 or 0) + (debt_2025 or 0) - (cash_and_marketable_2025 or 0)
        if equity_2025 is not None and debt_2025 is not None
        else None
    )
    sales_to_capital = (
        revenue_2025 / invested_capital_2025
        if revenue_2025 and invested_capital_2025 and invested_capital_2025 > 0
        else None
    )

    if revenue_growth_fraction is None:
        gaps.append("companyDriveDataDTO.revenueNextYear: could not derive rev_yoy_pct from report; Java requires this non-null")
    if operating_margin_fraction is None:
        gaps.append("companyDriveDataDTO.operatingMarginNextYear: could not derive EBIT margin; Java requires this non-null")
    if sales_to_capital is None:
        gaps.append("companyDriveDataDTO.salesToCapitalYears1To5/6To10: could not derive invested capital; falling back to a generic 2.5x")

    resolved_risk_free_rate = risk_free_rate if risk_free_rate is not None else 0.020
    # resolved_cost_of_capital = initial_cost_capital if initial_cost_capital is not None else 0.09
    if risk_free_rate is None:
        gaps.append(
            "companyDriveDataDTO.riskFreeRate: no value supplied, defaulted to an ILLUSTRATIVE 2.0% placeholder. "
            "The app's own baseline-risk-free-rate config default (4.58%) is USD-denominated (10Y UST) and is "
            "almost certainly wrong for a CNY valuation -- pass an actual China 10Y government bond yield via "
            "risk_free_rate instead of trusting either default."
        )

    if initial_cost_capital is not None:
        resolved_cost_of_capital = initial_cost_capital
    else:
        resolved_cost_of_capital, wacc_notes = estimate_initial_cost_capital(
            risk_free_rate=resolved_risk_free_rate,
            marginal_tax_rate=(marginal_tax_rate_pct / 100) if marginal_tax_rate_pct is not None else 0.25,
            debt=debt_2025,
            equity=equity_2025,
        )
        gaps.extend(wacc_notes)
    gaps.append(
        "companyDriveDataDTO.compoundAnnualGrowth2_5: reused revenueNextYear as a naive flat-growth placeholder "
        "(no multi-year data to fit a fade curve); revisit via guided questions."
    )
    gaps.append(
        "companyDriveDataDTO.targetPreTaxOperatingMargin left null: Java falls back to the valuation template's "
        "normalized margin in this case, which is safe, but confirm that template default is reasonable for a "
        "China semiconductor company."
    )

    company_drive_data: dict[str, Any] = {
        "revenueNextYear": revenue_growth_fraction if revenue_growth_fraction is not None else 0.0,
        "operatingMarginNextYear": operating_margin_fraction if operating_margin_fraction is not None else 0.0,
        "compoundAnnualGrowth2_5": revenue_growth_fraction if revenue_growth_fraction is not None else 0.0,
        "riskFreeRate": resolved_risk_free_rate,
        "initialCostCapital": resolved_cost_of_capital,
        "convergenceYearMargin": None,  # unused by initializeFinancialDataInput; computed from template instead
        "salesToCapitalYears1To5": sales_to_capital if sales_to_capital is not None else 2.5,
        "salesToCapitalYears6To10": sales_to_capital if sales_to_capital is not None else 2.5,
        "targetPreTaxOperatingMargin": None,  # safely nullable: Java falls back to template default
    }

    company_data: dict[str, Any] = {
        "basicInfoDataDTO": basic_info,
        "financialDataDTO": financial_data,
        "companyDriveDataDTO": company_drive_data,
        "growthDto": None,
        "dividendDataDTO": None,
        # Not part of the Java DTO -- carried alongside for the review gate
        # below, stripped before the packet is sent to /external/valuation.
        "reviewStatus": "pending_review",
        "reviewSource": {
            "analysisId": report.get("analysis_id"),
            "symbol": symbol,
            "reportYear": report.get("scope", {}).get("report_year"),
            "calculationEngine": report.get("scope", {}).get("calculation_engine"),
        },
    }
    gaps.append("growthDto left null: needs multi-year revenue/margin history to compute mu/sigma")

    return {"ticker": ticker, "companyData": company_data, "gaps": gaps}


# ---------------------------------------------------------------------------
# Layer 2: MCP-facing review-gate helpers (mirrors prospectus_* in mcp_tools.py)
# ---------------------------------------------------------------------------

def ah_disclosure_review_token(report: dict[str, Any]) -> str | None:
    ar = report.get("analysis_result") or {}
    company = ar.get("company") or {}
    scope = report.get("scope") or {}
    basis = {
        "analysisId": report.get("analysis_id"),
        "symbol": company.get("symbol") or scope.get("symbol"),
        "reportYear": scope.get("report_year"),
    }
    if not any(basis.values()):
        return None
    raw = json.dumps(basis, sort_keys=True, default=str)
    return "ah_disclosure_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def ah_disclosure_review_status(packet: dict[str, Any]) -> str | None:
    if not isinstance(packet, dict):
        return None
    return packet.get("reviewStatus") or packet.get("review_status")


def ah_disclosure_extraction_success_payload(
    tool: str,
    ticker: str | None,
    company_data: dict[str, Any],
    gaps: list[str],
    review_reference: str | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": tool,
        "ahDisclosure": {
            "status": "requires_review",
            "reviewStatus": company_data.get("reviewStatus") or "pending_review",
            "reviewReference": review_reference,
            "ticker": ticker,
            "companyData": company_data,
            "gaps": gaps,
        },
    }
