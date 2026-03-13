"""Live BullBearGPT tool registry and execution helpers."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Optional

from models.notebook_session import NotebookSession
from services.python_sandbox_service import get_python_sandbox_service
from services.valuation_client import get_valuation_client

logger = logging.getLogger(__name__)

LIVE_AGENT_TOOLS = [
    "valuation_loader",
    "python_interpreter",
    "dcf_recalculator",
    "get_industry_comparables",
]
TOP_LEVEL_DCF_OVERRIDE_KEYS = (
    "revenue_growth",
    "operating_margin",
    "sales_to_capital",
    "wacc",
    "terminal_growth",
)


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_ratio(value: Any) -> Optional[float]:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    if abs(parsed) > 1.0:
        parsed = parsed / 100.0
    return parsed


def _extract_company_metrics(payload: Dict[str, Any]) -> Dict[str, Optional[float]]:
    company_dto = (
        payload.get("companyDTO")
        or payload.get("java_valuation_output", {}).get("companyDTO", {})
        or {}
    )
    fair_value = company_dto.get("estimatedValuePerShare")
    current_price = company_dto.get("price")
    upside = company_dto.get("upside")
    if upside is None and fair_value not in (None, "") and current_price not in (None, "", 0):
        try:
            upside = ((float(fair_value) - float(current_price)) / float(current_price)) * 100.0
        except Exception:
            upside = None
    return {
        "fair_value": _safe_float(fair_value),
        "current_price": _safe_float(current_price),
        "upside_percentage": _safe_float(upside),
    }


def _extract_assumption_transparency(session: NotebookSession) -> Dict[str, Any]:
    candidates = [
        session.valuation_output_json,
        (session.base_analysis_json or {}).get("java_valuation_output"),
        session.base_analysis_json,
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        transparency = candidate.get("assumptionTransparency")
        if isinstance(transparency, dict) and transparency:
            return transparency
        nested = candidate.get("java_valuation_output")
        if isinstance(nested, dict):
            transparency = nested.get("assumptionTransparency")
            if isinstance(transparency, dict) and transparency:
                return transparency
    return {}


class AgentToolService:
    """Small execution layer for the live BullBearGPT tool set."""

    def get_live_tools(self) -> List[str]:
        return list(LIVE_AGENT_TOOLS)

    def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        session: NotebookSession,
        recent_theses: Iterable[Dict[str, Any]],
        auth_header: Optional[str] = None,
        user_message: str = "",
        llm_service: Any = None,
        notebook_service: Any = None,
    ) -> Dict[str, Any]:
        start_time = time.time()
        try:
            if tool_name == "valuation_loader":
                data = self._load_current_valuation(session, recent_theses)
                status = "success"
            elif tool_name == "python_interpreter":
                if llm_service is None:
                    raise RuntimeError("LLM service is required for python_interpreter")
                code = llm_service.generate_code(
                    message=user_message,
                    context={
                        "valuation_data": session.base_analysis_json or {},
                        "valuation_input": session.valuation_input_json or {},
                        "valuation_output": session.valuation_output_json or {},
                        "recent_theses": [self._thesis_tool_snapshot(item) for item in recent_theses],
                    },
                )
                if not code:
                    return {
                        "tool_name": tool_name,
                        "status": "skipped",
                        "data": {"reason": "No code generation was needed for this question."},
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                    }
                sandbox = get_python_sandbox_service()
                data = sandbox.execute(
                    code=code,
                    valuation=session.base_analysis_json or {},
                    valuation_input=session.valuation_input_json or {},
                    valuation_output=session.valuation_output_json or {},
                    recent_theses=[self._thesis_tool_snapshot(item) for item in recent_theses],
                )
                data["code"] = code
                status = "success"
            elif tool_name == "dcf_recalculator":
                data = self._recalculate_dcf(
                    params=params,
                    session=session,
                    auth_header=auth_header,
                    notebook_service=notebook_service,
                )
                status = "success"
            elif tool_name == "get_industry_comparables":
                data = self._get_industry_comparables(params, session)
                status = "success"
            else:
                raise RuntimeError(f"Unsupported tool: {tool_name}")

            return {
                "tool_name": tool_name,
                "status": status,
                "data": data,
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }
        except Exception as exc:
            logger.error("Tool execution failed for %s: %s", tool_name, exc, exc_info=True)
            return {
                "tool_name": tool_name,
                "status": "error",
                "error": str(exc),
                "execution_time_ms": int((time.time() - start_time) * 1000),
            }

    def _load_current_valuation(
        self,
        session: NotebookSession,
        recent_theses: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "valuation_data": session.base_analysis_json or {},
            "input_json": session.valuation_input_json or {},
            "output_json": session.valuation_output_json or {},
            "metrics": _extract_company_metrics(session.valuation_output_json or session.base_analysis_json or {}),
            "recent_theses": [self._thesis_tool_snapshot(item) for item in recent_theses],
        }

    def _recalculate_dcf(
        self,
        params: Dict[str, Any],
        session: NotebookSession,
        auth_header: Optional[str],
        notebook_service: Any,
    ) -> Dict[str, Any]:
        if not session.valuation_id:
            raise RuntimeError("This session has no valuation_id to recalculate.")

        top_level_overrides = {
            key: value
            for key, value in (params or {}).items()
            if key in TOP_LEVEL_DCF_OVERRIDE_KEYS and value is not None
        }
        if not top_level_overrides and params.get("metric") and params.get("value") is not None:
            top_level_overrides[str(params.get("metric"))] = params.get("value")
        if not top_level_overrides:
            raise RuntimeError("No supported DCF override was provided.")

        sector_overrides = params.get("sector_overrides") or []
        before_metrics = _extract_company_metrics(session.valuation_output_json or session.base_analysis_json or {})

        valuation_client = get_valuation_client()
        response = valuation_client.recalculate_valuation_by_id(
            valuation_id=session.valuation_id,
            top_level_overrides=top_level_overrides,
            sector_overrides=sector_overrides,
            persist=True,
            auth_header=auth_header,
        )
        if not response:
            raise RuntimeError("valuation-agent recalc failed")

        valuation_data = response.get("valuation_data") or {}
        input_json = response.get("input_json") or {}
        output_json = response.get("output_json") or {}
        updated_metrics = _extract_company_metrics(output_json or valuation_data)

        session.base_analysis_json = valuation_data
        session.valuation_input_json = input_json
        session.valuation_output_json = output_json
        session.valuation_id = response.get("id") or session.valuation_id
        session.company_name = response.get("company_name") or session.company_name
        if notebook_service is not None:
            notebook_service.update_session_valuation_context(
                session_id=session.id,
                valuation_data=valuation_data,
                valuation_input_json=input_json,
                valuation_output_json=output_json,
                valuation_id=session.valuation_id,
                company_name=session.company_name,
                currency=(valuation_data.get("currency") or output_json.get("currency")),
            )

        return {
            "valuation_id": session.valuation_id,
            "top_level_overrides": top_level_overrides,
            "sector_overrides": sector_overrides,
            "comparison": {
                "before": before_metrics,
                "after": updated_metrics,
            },
            "valuation_data": valuation_data,
            "input_json": input_json,
            "output_json": output_json,
        }

    def _get_industry_comparables(self, params: Dict[str, Any], session: NotebookSession) -> Dict[str, Any]:
        transparency = _extract_assumption_transparency(session)
        operating = transparency.get("operatingAssumptions") if isinstance(transparency.get("operatingAssumptions"), dict) else {}
        discount_rate = transparency.get("discountRate") if isinstance(transparency.get("discountRate"), dict) else {}
        anchor = transparency.get("growthAnchor") if isinstance(transparency.get("growthAnchor"), dict) else {}
        rationales = transparency.get("adjustmentRationales") if isinstance(transparency.get("adjustmentRationales"), dict) else {}

        metric_aliases = {
            "revenue_growth": "revenue_cagr",
            "revenue_cagr": "revenue_cagr",
            "operating_margin": "operating_margin",
            "sales_to_capital": "sales_to_capital",
            "wacc": "wacc",
            "terminal_growth": "terminal_growth",
        }
        metric = metric_aliases.get(str(params.get("metric") or "revenue_cagr").strip().lower(), "revenue_cagr")

        if metric == "revenue_cagr":
            selected_value = _normalize_ratio(
                params.get("user_value")
                if params.get("user_value") is not None
                else operating.get("revenueGrowthRateYears2To5")
            )
            band = {
                "p25": _normalize_ratio(anchor.get("p25")),
                "p50": _normalize_ratio(anchor.get("p50")),
                "p75": _normalize_ratio(anchor.get("p75")),
            }
            confidence_score = _safe_float(anchor.get("confidenceScore")) or 0.0
            confidence = "HIGH" if confidence_score >= 0.8 else "MEDIUM" if confidence_score >= 0.5 else "LOW"
            explanation = "Growth anchor data is unavailable for this valuation."
            entity_name = anchor.get("entityDisplay") or anchor.get("entity") or "industry"
            if band["p50"] is not None and selected_value is not None:
                if band["p75"] is not None and selected_value > band["p75"]:
                    explanation = f"Selected growth is above the 75th percentile for {entity_name}."
                elif band["p25"] is not None and selected_value < band["p25"]:
                    explanation = f"Selected growth is below the 25th percentile for {entity_name}."
                else:
                    explanation = f"Selected growth sits within the historical {entity_name} band."
            return {
                "metric": metric,
                "selected_value": selected_value,
                "industry_band": band,
                "confidence": confidence,
                "entity": entity_name,
                "peer_band_available": band["p50"] is not None,
                "explanation": explanation,
            }

        selected_value = None
        rationale = None
        if metric == "operating_margin":
            selected_value = _normalize_ratio(operating.get("targetOperatingMargin"))
            rationale = rationales.get("operatingMargin") or operating.get("operatingMarginSource")
        elif metric == "sales_to_capital":
            selected_value = _safe_float(operating.get("salesToCapitalYears1To5"))
            rationale = rationales.get("salesToCapital") or operating.get("salesToCapitalSource")
        elif metric == "wacc":
            selected_value = _normalize_ratio(discount_rate.get("initialCostOfCapital"))
            rationale = rationales.get("costOfCapital") or discount_rate.get("initialCostOfCapitalSource")
        elif metric == "terminal_growth":
            terminal_value_dto = session.valuation_output_json.get("terminalValueDTO", {}) if isinstance(session.valuation_output_json, dict) else {}
            selected_value = _normalize_ratio(terminal_value_dto.get("growthRate"))
            rationale = "No peer band is available in the growth-anchor path for terminal growth."

        if not rationale:
            rationale = f"No peer band is available in the current growth-anchor path for {metric}."

        return {
            "metric": metric,
            "selected_value": selected_value,
            "industry_band": None,
            "peer_band_available": False,
            "rationale": rationale,
        }

    @staticmethod
    def _thesis_tool_snapshot(thesis: Dict[str, Any]) -> Dict[str, Any]:
        preview = thesis.get("preview_json") if isinstance(thesis.get("preview_json"), dict) else {}
        return {
            "id": thesis.get("id"),
            "session_id": thesis.get("session_id"),
            "ticker": thesis.get("ticker"),
            "title": preview.get("title") or thesis.get("title"),
            "summary": preview.get("summary") or thesis.get("summary"),
            "conviction": preview.get("conviction"),
            "fair_value": preview.get("fair_value"),
            "current_price": preview.get("current_price"),
            "upside": preview.get("upside"),
            "timeframe": preview.get("timeframe"),
            "key_assumptions": preview.get("key_assumptions") or [],
            "risks": preview.get("risks") or [],
            "created_at": thesis.get("created_at"),
        }


_agent_tool_service: Optional[AgentToolService] = None


def get_agent_tool_service() -> AgentToolService:
    global _agent_tool_service
    if _agent_tool_service is None:
        _agent_tool_service = AgentToolService()
    return _agent_tool_service
