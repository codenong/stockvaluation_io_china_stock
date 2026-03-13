"""
Notebook Routes - REST API endpoints for Jupyter-style notebook cells.
Unified API that combines chat features with notebook cell management.
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime
from flask import Blueprint, jsonify, request, Response, stream_with_context

from services.notebook_service import get_notebook_service
from services.chat_context_builder import build_full_valuation_context
from services.agent_tool_service import get_agent_tool_service
from services.opening_question_generator import generate_opening_question, generate_opening_suggestions
from models.notebook_cell import NotebookCell

logger = logging.getLogger(__name__)

notebook_bp = Blueprint('notebook', __name__)


def generate_session_id(user_id: str, valuation_id: str) -> str:
    """
    Generate a deterministic session ID from user_id + valuation_id.
    This enables session persistence across page reloads.
    
    Args:
        user_id: The authenticated user's ID
        valuation_id: The valuation ID
        
    Returns:
        A 32-character hex string that is deterministic for the same inputs
    """
    combined = f"{user_id}:{valuation_id}"
    return hashlib.sha256(combined.encode()).hexdigest()[:32]


def _sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"


def _resolve_user_id(req, session=None) -> str:
    return (
        (req.get_json(silent=True) or {}).get('user_id')
        or req.headers.get('X-Local-User')
        or req.headers.get('X-User-ID')
        or getattr(session, 'user_id', None)
        or 'local'
    )


def _build_conversation_messages(cells, include_current_message: str = ""):
    messages = []
    for existing_cell in cells:
        if existing_cell.user_input:
            messages.append({"role": "user", "content": existing_cell.user_input})
        if existing_cell.ai_output:
            ai_content = existing_cell.ai_output.get('content') or existing_cell.ai_output.get('message', '')
            if ai_content:
                messages.append({"role": "assistant", "content": ai_content})
    if include_current_message:
        messages.append({"role": "user", "content": include_current_message})
    return messages


def _parse_tool_approval(message: str):
    normalized = (message or "").strip().lower()
    if normalized in {"yes", "y", "approve", "approved", "run it", "do it"}:
        return True
    if normalized in {"no", "n", "deny", "denied", "cancel", "skip"}:
        return False
    return None


def _build_tool_plan_message(tool_name: str, tool_input: dict, reason: str) -> str:
    return (
        f"I can run `{tool_name}` with {json.dumps(tool_input or {}, ensure_ascii=True)}.\n\n"
        f"Plan: {reason or 'Use the live valuation tool path for this question.'}\n\n"
        "Reply `yes` to run it or `no` to skip."
    )


# ===== SESSION ENDPOINTS =====

@notebook_bp.route('/sessions', methods=['POST'])
def create_session():
    """
    Create a new notebook session with welcome cell and opening question.
    
    Request Body:
        {
            "ticker": str,
            "company_name": str (optional),
            "valuation_data": dict (optional),
            "valuation_id": str (optional - fetches from yfinance),
            "currency": str (optional)
        }
    
    Returns:
        Created session with opening message and suggestions
    """
    try:
        data = request.get_json() or {}
        service = get_notebook_service()
        
        user_id = data.get('user_id', 'local')
        ticker = data.get('ticker', '')
        company_name = data.get('company_name')
        valuation_data = data.get('valuation_data', {})
        valuation_id = data.get('valuation_id')
        valuation_input_json = data.get('valuation_input_json') or {}
        valuation_output_json = data.get('valuation_output_json') or {}
        currency = data.get('currency')
        
        # Fetch valuation data if ID provided
        if valuation_id and not valuation_data:
            try:
                from services.valuation_client import get_valuation_client
                client = get_valuation_client()
                fetched = client.get_valuation_by_id(
                    valuation_id,
                    auth_header=request.headers.get('Authorization')
                )
                if fetched:
                    valuation_data = fetched.get('valuation_data', {})
                    valuation_input_json = fetched.get('input_json') or {}
                    valuation_output_json = fetched.get('output_json') or {}
                    if not ticker:
                        ticker = fetched.get('ticker', '')
                    if not company_name:
                        company_name = fetched.get('company_name')
                    currency = valuation_data.get('currency')
            except Exception as e:
                logger.warning(f"Could not fetch valuation {valuation_id}: {e}")
        
        # Use deterministic session ID if both user_id and valuation_id are available
        # This enables session persistence across page reloads
        session_id = None
        if user_id and valuation_id:
            session_id = generate_session_id(user_id, valuation_id)
            
            # Check if session already exists - return it if so
            existing_session = service.get_session(session_id)
            if existing_session:
                logger.info(f"Found existing session {session_id} for user {user_id} + valuation {valuation_id}")
                
                # Get all cells for this session
                cells = service.get_cells(session_id)
                
                result = existing_session.to_dict()
                result['cells'] = [c.to_dict() for c in cells]
                result['is_existing'] = True  # Flag to indicate this is a resumed session
                
                return jsonify(result), 200
        
        # Create new session with deterministic ID if available
        session = service.create_session(
            ticker=ticker,
            company_name=company_name,
            user_id=user_id,
            valuation_data=valuation_data,
            valuation_input_json=valuation_input_json,
            valuation_output_json=valuation_output_json,
            currency=currency,
            valuation_id=valuation_id,
            session_id=session_id  # Pass deterministic ID if available
        )
        
        # Generate opening question
        opening_message = ""
        suggestions = []
        try:
            opening_message = generate_opening_question(
                ticker=ticker,
                valuation_data=valuation_data,
                company_name=company_name
            )
            # generate_opening_suggestions returns {"primary_question": ..., "suggestions": [...]}
            suggestions_result = generate_opening_suggestions(
                ticker=ticker,
                valuation_data=valuation_data
            )
            # Extract just the suggestions array
            suggestions = suggestions_result.get('suggestions', []) if isinstance(suggestions_result, dict) else []
        except Exception as e:
            logger.warning(f"Could not generate opening question: {e}")
            opening_message = f"Welcome! Let's analyze **{company_name or ticker}**. What would you like to explore about this valuation?"
        
        # Create welcome system cell
        welcome_cell = NotebookCell.create_system_cell(
            session_id=session.id,
            sequence=0,
            message=opening_message,
            system_type='welcome',
            dcf_summary=_extract_dcf_summary(valuation_data)
        )
        service.add_cell(welcome_cell)
        
        logger.info(f"Created notebook session {session.id} for {ticker} with welcome cell")
        
        result = session.to_dict()
        result['opening_message'] = opening_message
        result['suggestions'] = [s.to_dict() if hasattr(s, 'to_dict') else s for s in suggestions]
        result['cells'] = [welcome_cell.to_dict()]
        
        return jsonify(result), 201
        
    except Exception as e:
        logger.error(f"Error creating notebook session: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create session'}), 500


def _extract_dcf_summary(valuation_data: dict) -> dict:
    """Extract DCF summary from valuation data for welcome cell."""
    if not valuation_data:
        return {}
    
    company = valuation_data.get('companyDTO', {})
    return {
        'fair_value': company.get('estimatedValuePerShare'),
        'current_price': company.get('price'),
        'upside_pct': company.get('upside'),
        'currency': valuation_data.get('currency'),
        'ticker': valuation_data.get('ticker', ''),
    }



@notebook_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Get a notebook session with all cells."""
    try:
        service = get_notebook_service()

        session = service.get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        cells = service.get_cells(session_id)
        scenarios = service.get_scenarios(session_id)
        
        result = session.to_dict()
        result['cells'] = [c.to_dict() for c in cells]
        result['scenarios'] = scenarios
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        return jsonify({'error': 'Failed to get session'}), 500


@notebook_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a notebook session (cascades to cells)."""
    try:
        service = get_notebook_service()
        
        if service.delete_session(session_id):
            return jsonify({'message': 'Session deleted', 'session_id': session_id}), 200
        else:
            return jsonify({'error': 'Session not found'}), 404
        
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        return jsonify({'error': 'Failed to delete session'}), 500


@notebook_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List notebook sessions.
    
    Query Parameters:
        user_id: Filter by user ID
        ticker: Filter by ticker
        limit: Max results (default 50)
    """
    try:
        service = get_notebook_service()
        
        user_id = request.args.get('user_id', 'local')
        ticker = request.args.get('ticker')
        limit = int(request.args.get('limit', 50))
        
        sessions = service.list_sessions(user_id=user_id, ticker=ticker, limit=limit)
        
        return jsonify({
            'sessions': [s.to_dict() for s in sessions],
            'count': len(sessions)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({'error': 'Failed to list sessions'}), 500


# ===== CELL ENDPOINTS =====

@notebook_bp.route('/sessions/<session_id>/cells', methods=['POST'])
def add_cell(session_id: str):
    """
    Add a cell to a session.
    
    Request Body:
        {
            "cell_type": str (reasoning, calibration, system, visualization),
            "user_input": str (for reasoning cells),
            "content": dict (optional additional content),
            "ai_output": dict (optional)
        }
    """
    try:
        data = request.get_json() or {}
        service = get_notebook_service()
        
        # Get next sequence number
        sequence = service.get_next_sequence_number(session_id)
        
        cell_type = data.get('cell_type', 'reasoning')
        
        if cell_type == 'reasoning':
            cell = NotebookCell.create_reasoning_cell(
                session_id=session_id,
                user_input=data.get('user_input', ''),
                sequence=sequence,
                ai_output=data.get('ai_output')
            )
        elif cell_type == 'calibration':
            cell = NotebookCell.create_calibration_cell(
                session_id=session_id,
                changes=data.get('content', {}).get('changes', {}),
                dcf_snapshot_id=data.get('dcf_snapshot_id'),
                sequence=sequence,
                rationale=data.get('content', {}).get('rationale', '')
            )
        elif cell_type == 'system':
            cell = NotebookCell.create_system_cell(
                session_id=session_id,
                sequence=sequence,
                message=data.get('content', {}).get('message', ''),
                system_type=data.get('content', {}).get('type', 'info'),
                dcf_summary=data.get('content', {}).get('dcf_summary')
            )
        elif cell_type == 'visualization':
            cell = NotebookCell.create_visualization_cell(
                session_id=session_id,
                sequence=sequence,
                chart_type=data.get('content', {}).get('chart_type', 'bar'),
                chart_data=data.get('content', {}).get('chart_data', {})
            )
        else:
            cell = NotebookCell(
                session_id=session_id,
                sequence_number=sequence,
                cell_type=cell_type,
                user_input=data.get('user_input'),
                ai_output=data.get('ai_output'),
                content=data.get('content', {})
            )
        
        cell = service.add_cell(cell)
        
        logger.info(f"Added {cell.cell_type} cell {cell.id} to session {session_id}")
        
        return jsonify(cell.to_dict()), 201
        
    except Exception as e:
        logger.error(f"Error adding cell to session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to add cell'}), 500


@notebook_bp.route('/sessions/<session_id>/cells', methods=['GET'])
def get_cells(session_id: str):
    """Get all cells for a session."""
    try:
        service = get_notebook_service()
        cells = service.get_cells(session_id)
        
        return jsonify({
            'cells': [c.to_dict() for c in cells],
            'count': len(cells)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting cells for session {session_id}: {e}")
        return jsonify({'error': 'Failed to get cells'}), 500


@notebook_bp.route('/cells/<cell_id>', methods=['PUT', 'PATCH'])
@notebook_bp.route('/sessions/<session_id>/cells/<cell_id>', methods=['PUT', 'PATCH'])
def update_cell(cell_id: str, session_id: str = None):
    """
    Update a cell.
    
    Request Body:
        {
            "user_input": str (optional),
            "ai_output": dict (optional),
            "user_notes": str (optional),
            "content": dict (optional)
        }
    """
    try:
        data = request.get_json() or {}
        service = get_notebook_service()
        
        # Fetch the cell from SQLite via notebook service
        cell = service.get_cell(cell_id)
        if not cell:
            return jsonify({'error': 'Cell not found'}), 404
        
        # Update fields
        if 'user_input' in data:
            cell.user_input = data['user_input']
        if 'ai_output' in data:
            cell.ai_output = data['ai_output']
        if 'user_notes' in data:
            cell.user_notes = data['user_notes']
        if 'content' in data:
            if cell.content:
                cell.content.update(data['content'])
            else:
                cell.content = data['content']
        
        if service.update_cell(cell):
            return jsonify({'success': True, 'cell': cell.to_dict()}), 200
        else:
            return jsonify({'error': 'Failed to update cell'}), 500
        
    except Exception as e:
        logger.error(f"Error updating cell {cell_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update cell'}), 500


@notebook_bp.route('/cells/<cell_id>', methods=['DELETE'])
@notebook_bp.route('/sessions/<session_id>/cells/<cell_id>', methods=['DELETE'])
def delete_cell(cell_id: str, session_id: str = None):
    """Delete a cell."""
    try:
        service = get_notebook_service()
        
        if service.delete_cell(cell_id):
            return jsonify({'success': True, 'message': 'Cell deleted', 'cell_id': cell_id}), 200
        else:
            return jsonify({'error': 'Cell not found or deletion failed'}), 404
        
    except Exception as e:
        logger.error(f"Error deleting cell {cell_id}: {e}")
        return jsonify({'error': 'Failed to delete cell'}), 500


# ===== SCENARIO ENDPOINTS =====

@notebook_bp.route('/sessions/<session_id>/scenarios', methods=['POST'])
def save_scenario(session_id: str):
    """
    Save a scenario.
    
    Request Body:
        {
            "name": str,
            "description": str (optional),
            "cell_id": str (optional),
            "dcf_snapshot_id": str (optional),
            "assumptions_summary": dict (optional)
        }
    """
    try:
        data = request.get_json() or {}
        service = get_notebook_service()
        
        scenario = service.save_scenario(
            session_id=session_id,
            name=data.get('name', 'Custom Scenario'),
            cell_id=data.get('cell_id'),
            dcf_snapshot_id=data.get('dcf_snapshot_id'),
            assumptions_summary=data.get('assumptions_summary'),
            description=data.get('description')
        )
        
        if scenario:
            return jsonify(scenario), 201
        else:
            return jsonify({'error': 'Failed to save scenario'}), 500
        
    except Exception as e:
        logger.error(f"Error saving scenario for session {session_id}: {e}")
        return jsonify({'error': 'Failed to save scenario'}), 500


@notebook_bp.route('/sessions/<session_id>/scenarios', methods=['GET'])
def get_scenarios(session_id: str):
    """Get all scenarios for a session."""
    try:
        service = get_notebook_service()
        scenarios = service.get_scenarios(session_id)
        
        return jsonify({
            'scenarios': scenarios,
            'count': len(scenarios)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting scenarios for session {session_id}: {e}")
        return jsonify({'error': 'Failed to get scenarios'}), 500


# ===== DCF SNAPSHOT ENDPOINTS =====

@notebook_bp.route('/sessions/<session_id>/recalculate-dcf', methods=['POST'])
def recalculate_dcf(session_id: str):
    """[REMOVED] DCF recalculation removed. Use valuation-agent instead."""
    return jsonify({
        'success': False,
        'session_id': session_id,
        'message': 'DCF recalculation is disabled in notebook local-first mode. Use valuation workflow.'
    }), 200



@notebook_bp.route('/sessions/<session_id>/dcf-snapshots', methods=['GET'])
def get_dcf_snapshots(session_id: str):
    """[REMOVED] DCF snapshots removed. Use valuation-agent persistence instead."""
    return jsonify({'snapshots': [], 'count': 0}), 200


# ===== MESSAGE ENDPOINT (SSE Streaming) =====

@notebook_bp.route('/sessions/<session_id>/messages', methods=['POST'])
def send_message(session_id: str):
    """
    Send a message and get streaming AI response.
    Creates a reasoning cell with user input and streams AI output.
    
    Request Body:
        {
            "message": str,
            "model": str (optional),
            "temperature": float (optional),
            "max_tokens": int (optional)
        }
    
    Returns:
        SSE stream with cell updates
    """
    data = request.get_json() or {}
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'message is required'}), 400
    
    def generate():
        try:
            service = get_notebook_service()
            tool_service = get_agent_tool_service()
            start_time = time.time()
            
            # Get session for context
            session = service.get_session(session_id)
            if not session:
                yield _sse('error', {'error': 'Session not found'})
                return

            user_id = (
                data.get('user_id')
                or request.headers.get('X-Local-User')
                or request.headers.get('X-User-ID')
                or session.user_id
                or 'local'
            )
            
            # Create reasoning cell
            sequence = service.get_next_sequence_number(session_id)
            cell = NotebookCell.create_reasoning_cell(
                session_id=session_id,
                user_input=message,
                sequence=sequence
            )
            cell = service.add_cell(cell)
            
            # Emit cell created
            yield _sse('cell_start', {'cell_id': cell.id, 'type': 'reasoning'})
            
            # Build context from session's valuation data
            valuation_data = session.base_analysis_json or {}
            recent_theses = service.list_recent_theses_for_ticker(
                user_id=user_id,
                ticker=session.ticker,
                limit=2,
                exclude_session_id=session_id,
            )
            try:
                system_context = build_full_valuation_context(
                    valuation_data=valuation_data,
                    ticker=session.ticker,
                    name=session.company_name,
                    valuation_input_json=session.valuation_input_json or {},
                    valuation_output_json=session.valuation_output_json or {},
                    recent_theses=recent_theses,
                )
            except Exception as e:
                logger.error(f"Context build failed: {e}", exc_info=True)
                system_context = f"Analyzing {session.company_name or session.ticker}."
            
            from services.llm_service import get_llm_service
            llm_service = get_llm_service()
            context = {
                'ticker': session.ticker,
                'company_name': session.company_name,
                'valuation_data': valuation_data,
                'valuation_input_json': session.valuation_input_json or {},
                'valuation_output_json': session.valuation_output_json or {},
                'recent_theses': recent_theses,
            }
            approval_decision = _parse_tool_approval(message)
            pending_plan = service.get_latest_pending_tool_plan(session_id)

            if pending_plan and approval_decision is not None:
                if approval_decision:
                    service.update_tool_plan_status(pending_plan['id'], 'approved')
                    tool_result = tool_service.execute_tool(
                        tool_name=pending_plan['tool_name'],
                        params=pending_plan.get('tool_input_json') or {},
                        session=session,
                        recent_theses=recent_theses,
                        auth_header=request.headers.get('Authorization'),
                        user_message=message,
                        llm_service=llm_service,
                        notebook_service=service,
                    )
                    recent_theses = service.list_recent_theses_for_ticker(
                        user_id=user_id,
                        ticker=session.ticker,
                        limit=2,
                        exclude_session_id=session_id,
                    )
                    context = {
                        'ticker': session.ticker,
                        'company_name': session.company_name,
                        'valuation_data': session.base_analysis_json or {},
                        'valuation_input_json': session.valuation_input_json or {},
                        'valuation_output_json': session.valuation_output_json or {},
                        'recent_theses': recent_theses,
                    }
                    yield _sse('tool_result', {
                        'cell_id': cell.id,
                        'tool_name': tool_result.get('tool_name'),
                        'status': tool_result.get('status'),
                        'data': tool_result.get('data'),
                        'error': tool_result.get('error'),
                        'execution_time_ms': tool_result.get('execution_time_ms'),
                    })

                    original_cell = service.get_cell(pending_plan['cell_id'])
                    original_message = (
                        original_cell.user_input
                        if original_cell and original_cell.user_input
                        else message
                    )
                    rewritten_query = llm_service.rewrite_query(original_message, context)
                    full_response = ""
                    if tool_result.get('status') == 'error':
                        full_response = f"I couldn't run `{pending_plan['tool_name']}`: {tool_result.get('error')}"
                        yield _sse('stream', {'cell_id': cell.id, 'chunk': full_response})
                        service.update_tool_plan_status(pending_plan['id'], 'failed')
                    else:
                        for chunk in llm_service.synthesize_response(
                            original_message=original_message,
                            rewritten_query=rewritten_query,
                            tool_results=[tool_result],
                            context=context,
                        ):
                            full_response += chunk
                            yield _sse('stream', {'cell_id': cell.id, 'chunk': chunk})
                        service.update_tool_plan_status(pending_plan['id'], 'completed')

                    cell.ai_output = {
                        'content': full_response,
                        'model': data.get('model', 'default'),
                        'rewritten_query': rewritten_query,
                        'tool_results': [tool_result],
                    }
                else:
                    service.update_tool_plan_status(pending_plan['id'], 'denied')
                    full_response = f"Not running `{pending_plan['tool_name']}`. I can keep working from the current valuation context if you want."
                    yield _sse('stream', {'cell_id': cell.id, 'chunk': full_response})
                    cell.ai_output = {
                        'content': full_response,
                        'model': data.get('model', 'default'),
                        'tool_results': [],
                    }

                cell.content['ai_output'] = cell.ai_output
                cell.execution_time_ms = int((time.time() - start_time) * 1000)
                service.update_cell(cell)
                yield _sse('cell_complete', {'cell_id': cell.id, 'cell': cell.to_dict()})
                yield _sse('done', {'status': 'complete'})
                return
            
            existing_cells = service.get_cells(session_id)
            history_cells = [existing_cell for existing_cell in existing_cells if existing_cell.id != cell.id]
            messages = _build_conversation_messages(history_cells, include_current_message=message)
            rewritten_query = llm_service.rewrite_query(message, context)
            selected_tools = llm_service.select_tools(
                message=rewritten_query,
                context=context,
                available_tools=tool_service.get_live_tools(),
            )
            selected_tool = None
            for candidate in selected_tools:
                if candidate.get('tool') in tool_service.get_live_tools():
                    selected_tool = candidate
                    break

            if selected_tool:
                tool_name = selected_tool.get('tool')
                tool_input = selected_tool.get('params') or {}
                plan_text = _build_tool_plan_message(
                    tool_name=tool_name,
                    tool_input=tool_input,
                    reason=selected_tool.get('reason', ''),
                )
                saved_plan = service.save_tool_plan(
                    session_id=session_id,
                    cell_id=cell.id,
                    tool_name=tool_name,
                    tool_input_json=tool_input,
                    plan_text=plan_text,
                    status='pending',
                )
                cell.ai_output = {
                    'content': plan_text,
                    'model': data.get('model', 'default'),
                    'rewritten_query': rewritten_query,
                    'tool_results': [],
                }
                cell.content['ai_output'] = cell.ai_output
                cell.execution_time_ms = int((time.time() - start_time) * 1000)
                service.update_cell(cell)
                yield _sse('tool_plan', {
                    'cell_id': cell.id,
                    'tool_id': saved_plan.get('id') if saved_plan else None,
                    'tool_name': tool_name,
                    'tool_input': tool_input,
                    'plan': plan_text,
                    'awaiting_response': True,
                })
                yield _sse('cell_complete', {'cell_id': cell.id, 'cell': cell.to_dict()})
                yield _sse('done', {'status': 'awaiting_tool_approval'})
                return
            
            full_response = ""
            for chunk in llm_service.stream_chat(
                messages=messages,
                system_prompt=system_context,
                model=data.get('model'),
                temperature=data.get('temperature', 0.7),
                max_tokens=data.get('max_tokens', 2048)
            ):
                full_response += chunk
                yield f"event: stream\ndata: {json.dumps({'cell_id': cell.id, 'chunk': chunk})}\n\n"
            
            # Update cell with AI response
            execution_time_ms = int((time.time() - start_time) * 1000)
            cell.ai_output = {
                'content': full_response,
                'model': data.get('model', 'default'),
                'rewritten_query': rewritten_query,
                'tool_results': [],
            }
            cell.content['ai_output'] = cell.ai_output
            cell.execution_time_ms = execution_time_ms
            service.update_cell(cell)
            
            # Emit complete
            yield _sse('cell_complete', {'cell_id': cell.id, 'cell': cell.to_dict()})
            yield _sse('done', {'status': 'complete'})
            
        except Exception as e:
            logger.error(f"Error in message stream: {e}", exc_info=True)
            yield _sse('error', {'error': str(e)})
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@notebook_bp.route('/sessions/<session_id>/cells/<cell_id>/regenerate', methods=['POST'])
def regenerate_cell(session_id: str, cell_id: str):
    """
    Regenerate AI output for a cell with SSE streaming.
    """
    data = request.get_json() or {}
    
    def generate():
        try:
            service = get_notebook_service()
            start_time = time.time()
            
            # Get cell from SQLite via notebook service
            cell = service.get_cell(cell_id)
            if not cell:
                yield f"event: error\ndata: {{'error': 'Cell not found'}}\n\n"
                return
            
            if not cell.user_input:
                yield f"event: error\ndata: {{'error': 'No user input to regenerate'}}\n\n"
                return
            
            import json
            yield f"event: cell_start\ndata: {json.dumps({'cell_id': cell.id, 'status': 'regenerating'})}\n\n"
            
            # Get session for context
            session = service.get_session(session_id)
            valuation_data = session.base_analysis_json or {} if session else {}
            
            try:
                system_context = build_full_valuation_context(
                    valuation_data=valuation_data,
                    ticker=session.ticker if session else '',
                    name=session.company_name if session else ''
                )
            except Exception as e:
                logger.error(f"Context build failed in regenerate: {e}", exc_info=True)
                system_context = ""
            
            # Stream regenerated response - BYPASS message_handler to avoid session lookup
            # Build conversation history from notebook cells (up to this cell)
            from services.llm_service import get_llm_service
            llm_service = get_llm_service()
            
            # Get cells up to (but not including) this cell's position
            existing_cells = service.get_cells(session_id)
            messages = []
            for existing_cell in existing_cells:
                if existing_cell.id == cell_id:
                    break  # Stop before the cell being regenerated
                if existing_cell.user_input:
                    messages.append({"role": "user", "content": existing_cell.user_input})
                if existing_cell.ai_output:
                    ai_content = existing_cell.ai_output.get('content') or existing_cell.ai_output.get('message', '')
                    if ai_content:
                        messages.append({"role": "assistant", "content": ai_content})
            
            # Add this cell's user input
            messages.append({"role": "user", "content": cell.user_input})
            
            full_response = ""
            for chunk in llm_service.stream_chat(
                messages=messages,
                system_prompt=system_context,
                model=data.get('model'),
                temperature=data.get('temperature', 0.7),
                max_tokens=data.get('max_tokens', 2048)
            ):
                full_response += chunk
                yield f"event: stream\ndata: {json.dumps({'cell_id': cell.id, 'chunk': chunk})}\n\n"
            
            # Update cell
            execution_time_ms = int((time.time() - start_time) * 1000)
            cell.ai_output = {
                'content': full_response,
                'model': data.get('model', 'default'),
                'regenerated': True
            }
            cell.content['ai_output'] = cell.ai_output
            cell.execution_time_ms = execution_time_ms
            service.update_cell(cell)
            
            yield f"event: cell_complete\ndata: {json.dumps({'cell_id': cell.id, 'cell': cell.to_dict()})}\n\n"
            yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Error regenerating cell: {e}", exc_info=True)
            import json
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ===== HEALTH CHECK =====


@notebook_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for notebook service."""
    try:
        db_path = os.path.join(os.getenv('LOCAL_DATA_DIR', 'local_data'), 'bullbeargpt.db')
        return jsonify({
            'status': 'healthy',
            'service': 'notebook',
            'storage': 'sqlite',
            'db_exists': os.path.exists(db_path)
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'service': 'notebook',
            'error': str(e)
        }), 503


@notebook_bp.route('/assumption-rationale/<valuation_id>', methods=['GET'])
def get_assumption_rationale(valuation_id: str):
    """
    CHAT-1: Growth skill explainability endpoint.
    Returns the rationale for growth assumptions using historical anchor data
    specifically for a given valuation ID.
    
    Returns:
        Structured JSON with assumption rationale.
    """
    try:
        from services.valuation_client import ValuationClient
        client = ValuationClient()
        
        # 1. Fetch valuation record from valuation-agent.
        valuation_record = client.get_valuation_by_id(valuation_id)
        if not valuation_record:
            return jsonify({'error': f'Valuation {valuation_id} not found'}), 404

        payload = valuation_record.get('valuation_data') if isinstance(valuation_record, dict) else {}
        if not isinstance(payload, dict):
            payload = {}

        java_output = payload.get('java_valuation_output') if isinstance(payload.get('java_valuation_output'), dict) else {}
        transparency = java_output.get('assumptionTransparency') if isinstance(java_output.get('assumptionTransparency'), dict) else {}
        if not transparency:
            transparency = payload.get('assumptionTransparency') if isinstance(payload.get('assumptionTransparency'), dict) else {}

        anchor = (
            transparency.get('growthAnchor')
            or java_output.get('growthSkillContext')
            or payload.get('growthSkillContext')
        )
        
        if not anchor:
            return jsonify({'error': 'No growth anchor data found for this valuation'}), 404

        operating = transparency.get('operatingAssumptions') if isinstance(transparency.get('operatingAssumptions'), dict) else {}
        selected_growth_pct = operating.get('revenueGrowthRateYears2To5')
        selected_growth = float(selected_growth_pct) / 100.0 if selected_growth_pct is not None else 0.0

        def _to_ratio(value):
            if value is None:
                return None
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                return None
            return parsed / 100.0 if abs(parsed) > 1.0 else parsed

        band_p25 = _to_ratio(anchor.get('p25'))
        band_p50 = _to_ratio(anchor.get('p50'))
        band_p75 = _to_ratio(anchor.get('p75'))
        entity_name = anchor.get('entityDisplay') or anchor.get('entity', 'Unknown')
        
        confidence = "HIGH" if anchor.get('confidenceScore', 0) > 0.8 else "MEDIUM" if anchor.get('confidenceScore', 0) > 0.5 else "LOW"
        
        # Build explanation
        explanation = f"Selected value ({selected_growth:.1%}) "
        if band_p50 is not None:
            if selected_growth > band_p75:
                explanation += f"is above the 75th percentile ({band_p75:.1%}) for {entity_name}."
            elif selected_growth < band_p25:
                explanation += f"is below the 25th percentile ({band_p25:.1%}) for {entity_name}."
            else:
                explanation += f"sits near the median ({band_p50:.1%}) within the {entity_name} industry band."
        else:
            explanation += f"was chosen, but specific historical bands for {entity_name} are unavailable."

        return jsonify({
            "assumption": "revenue_cagr",
            "selected_value": selected_growth,
            "industry_band": {
                "p25": band_p25,
                "p50": band_p50,
                "p75": band_p75
            },
            "damodaran_entity": entity_name,
            "confidence": confidence,
            "explanation": explanation
        }), 200

    except Exception as e:
        logger.error(f"Error fetching assumption rationale: {e}")
        return jsonify({'error': str(e)}), 500


# ===== THESIS ENDPOINTS =====

@notebook_bp.route('/sessions/<session_id>/generate-thesis-stream', methods=['POST'])
def generate_thesis_stream(session_id: str):
    """
    Generate a thesis preview with SSE streaming.
    Events:
      - stream: { chunk: "..." }
      - done: { full_response: "...", session_id: "...", ticker: "..." }
      - error: { error: "..." }
    """
    try:
        service = get_notebook_service()
        session = service.get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        cells = service.get_cells(session_id)
        cells_dicts = [c.to_dict() for c in cells]
        dcf_data = session.base_analysis_json or {}

        def generate():
            import json
            from services.thesis_generator import get_thesis_generator

            generator = get_thesis_generator()
            full_response = ""

            try:
                for chunk in generator.generate_thesis_preview_stream(
                    cells=cells_dicts,
                    dcf_data=dcf_data,
                    ticker=session.ticker,
                    company_name=session.company_name or session.ticker
                ):
                    full_response += chunk
                    yield f"event: stream\ndata: {json.dumps({'chunk': chunk})}\n\n"

                yield f"event: done\ndata: {json.dumps({'full_response': full_response, 'session_id': session_id, 'ticker': session.ticker})}\n\n"
            except Exception as e:
                logger.error(f"Error streaming thesis: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            }
        )
    except Exception as e:
        logger.error(f"Error setting up thesis stream for session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate thesis'}), 500


@notebook_bp.route('/sessions/<session_id>/generate-thesis', methods=['POST'])
def generate_thesis(session_id: str):
    """
    Generate a thesis preview from session data without saving it.
    """
    try:
        service = get_notebook_service()
        session = service.get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        cells = service.get_cells(session_id)
        cells_dicts = [c.to_dict() for c in cells]
        dcf_data = session.base_analysis_json or {}

        from services.thesis_generator import get_thesis_generator
        generator = get_thesis_generator()

        preview = generator.generate_thesis_preview(
            cells=cells_dicts,
            dcf_data=dcf_data,
            ticker=session.ticker,
            company_name=session.company_name or session.ticker
        )

        return jsonify({
            'preview': preview.to_dict(),
            'session_id': session_id,
            'ticker': session.ticker
        }), 200
    except Exception as e:
        logger.error(f"Error generating thesis for session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate thesis'}), 500


@notebook_bp.route('/sessions/<session_id>/save-thesis', methods=['POST'])
def save_thesis(session_id: str):
    """
    Save thesis (finalize notebook state snapshot for local history).
    """
    try:
        data = request.get_json() or {}
        service = get_notebook_service()

        session = service.get_session(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        user_id = (
            data.get('user_id')
            or request.headers.get('X-Local-User')
            or request.headers.get('X-User-ID')
            or session.user_id
            or 'local'
        )

        cells = service.get_cells(session_id)
        cells_snapshot = [c.to_dict() for c in cells]
        scenarios_snapshot = service.get_scenarios(session_id)
        dcf_snapshot = session.base_analysis_json or {}

        title = data.get('title')
        summary = data.get('summary')

        # Local-first behavior: save conversation snapshot directly.
        # If title/summary are not provided, use deterministic defaults.
        if not title:
            title = f"{session.ticker} Snapshot {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        if not summary:
            summary = f"Saved conversation snapshot for {session.company_name or session.ticker}."

        thesis = service.save_thesis(
            session_id=session_id,
            ticker=session.ticker,
            company_name=session.company_name or session.ticker,
            title=title,
            summary=summary,
            cells_snapshot=cells_snapshot,
            dcf_snapshot=dcf_snapshot,
            user_id=user_id,
            scenarios_snapshot=scenarios_snapshot,
            valuation_id=session.valuation_id,
            preview_json=data.get('preview_json'),
        )

        if not thesis:
            return jsonify({'error': 'Failed to save thesis'}), 500

        return jsonify({'thesis': thesis, 'success': True}), 201
    except Exception as e:
        logger.error(f"Error saving thesis for session {session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to save thesis'}), 500


@notebook_bp.route('/theses', methods=['GET'])
def list_theses():
    """
    List theses for local user, grouped by ticker/month by default.
    Query params:
      - user_id (optional; default local)
      - ticker (optional)
      - grouped (optional; default true)
    """
    try:
        service = get_notebook_service()
        user_id = (
            request.args.get('user_id')
            or request.headers.get('X-Local-User')
            or request.headers.get('X-User-ID')
            or 'local'
        )
        ticker = request.args.get('ticker')
        grouped = request.args.get('grouped', 'true').lower() == 'true'

        theses = service.list_user_theses(user_id=user_id, ticker=ticker)
        if grouped:
            grouped_theses = service.get_grouped_theses(user_id=user_id)
            return jsonify({'theses': theses, 'grouped': grouped_theses, 'count': len(theses)}), 200

        return jsonify({'theses': theses, 'count': len(theses)}), 200
    except Exception as e:
        logger.error(f"Error listing theses: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list theses'}), 500


@notebook_bp.route('/theses/<thesis_id>', methods=['GET'])
def get_thesis(thesis_id: str):
    """Get a single thesis by ID."""
    try:
        service = get_notebook_service()
        thesis = service.get_thesis(thesis_id)

        if not thesis:
            return jsonify({'error': 'Thesis not found'}), 404

        return jsonify({'thesis': thesis}), 200
    except Exception as e:
        logger.error(f"Error getting thesis {thesis_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get thesis'}), 500
