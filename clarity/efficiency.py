"""Prompt projections and honest, provider-aware usage accounting. No model calls."""
import math

from .guardrails import canonical

AUTHOR_STAGES = {'intake', 'draft', 'revise'}
STAGES = AUTHOR_STAGES | {'review'}


def compact_checks(checked):
    """The original feature already contains every example; don't expand it again."""
    if checked is None:
        return None
    return {k: v for k, v in checked.items() if k != 'scenario_index'}


def prompt_content(payload):
    """Native transports receive the schema once, through their schema parameter."""
    return {k: v for k, v in payload.items() if k != 'response_schema'}


def prompt_parts(payload):
    """Put immutable evidence ahead of changing drafts and feedback for prefix reuse."""
    content = prompt_content(payload)
    context = content.pop('context', None)
    return canonical({'context': context}), canonical(content)


def budget(system, payload, *, output_tokens=8192, context_tokens=0):
    # A portable estimate, not a tokenizer or proof of server capacity. Include
    # the native schema and leave space for provider chat/schema wrappers.
    size = len(system.encode()) + len(canonical(payload).encode())
    estimated = math.ceil(size / 3) + 512
    remaining = context_tokens - estimated - output_tokens if context_tokens else None
    return {'request_bytes': size, 'estimated_input_tokens': estimated,
            'output_limit_tokens': output_tokens, 'context_limit_tokens': context_tokens,
            'remaining_estimated_tokens': remaining,
            'fits_estimated_context': remaining is None or remaining >= 0}


def usage_metrics(usage):
    if not isinstance(usage, dict): return {}
    allowed = {'input_tokens', 'output_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens',
               'cache_read_input_tokens', 'cache_creation_input_tokens'}
    result = {k: v for k, v in usage.items() if k in allowed and type(v) is int and 0 <= v < 10**10}
    for field, mapping in (
        ('input_tokens_details', {'cached_tokens': 'cache_read_input_tokens', 'cache_write_tokens': 'cache_creation_input_tokens'}),
        ('prompt_tokens_details', {'cached_tokens': 'cache_read_input_tokens'}),
        ('output_tokens_details', {'reasoning_tokens': 'reasoning_tokens'}),
        ('completion_tokens_details', {'reasoning_tokens': 'reasoning_tokens'}),
    ):
        details = usage.get(field, {})
        if isinstance(details, dict):
            for source, target in mapping.items():
                value = details.get(source)
                if type(value) is int and 0 <= value < 10**10:
                    result[target] = value
    return result


def scorecard(calls, run, events):
    """Unknown usage stays unknown. Failed/cancelled calls still contribute usage."""
    stages = {}
    measured = 0
    for call in calls:
        stage = stages.setdefault(call.get('stage', 'unknown'), {'attempts': 0, 'succeeded': 0,
                                  'elapsed_seconds': 0, 'input_tokens': 0, 'output_tokens': 0,
                                  'cached_input_tokens': 0, 'cache_measured_attempts': 0, 'measured_attempts': 0})
        stage['attempts'] += 1
        stage['succeeded'] += int(call['succeeded'])
        stage['elapsed_seconds'] = round(stage['elapsed_seconds'] + call['elapsed_seconds'], 3)
        m = call.get('metrics', {})
        incoming = m.get('input_tokens', m.get('prompt_tokens', m.get('prompt_eval_count')))
        outgoing = m.get('output_tokens', m.get('completion_tokens', m.get('eval_count')))
        cached = m.get('cache_read_input_tokens', m.get('prompt_eval_cached_count'))
        if incoming is not None and outgoing is not None:
            # Claude input_tokens excludes reads/writes; OpenAI input_tokens includes them.
            if call.get('provider') == 'anthropic':
                incoming += (cached or 0) + m.get('cache_creation_input_tokens', 0)
            stage['input_tokens'] += incoming
            stage['output_tokens'] += outgoing
            if cached is not None:
                stage['cached_input_tokens'] += cached
                stage['cache_measured_attempts'] += 1
            stage['measured_attempts'] += 1
            measured += 1
    cache_measured = sum(s['cache_measured_attempts'] for s in stages.values())
    for stage in stages.values():
        if not stage['measured_attempts']: stage['input_tokens'] = stage['output_tokens'] = None
        if not stage['cache_measured_attempts']: stage['cached_input_tokens'] = None
    reserved = max(len(calls), sum(e['kind'] == 'model_call_started' for e in events))
    return {'attempts': len(calls), 'reserved_attempts': reserved, 'unfinished_attempts': reserved - len(calls), 'measured_attempts': measured,
            'input_tokens': sum(s['input_tokens'] or 0 for s in stages.values()) if measured else None,
            'output_tokens': sum(s['output_tokens'] or 0 for s in stages.values()) if measured else None,
            'cached_input_tokens': sum(s['cached_input_tokens'] or 0 for s in stages.values()) if cache_measured else None,
            'cache_measured_attempts': cache_measured,
            'elapsed_seconds': round(sum(s['elapsed_seconds'] for s in stages.values()), 3),
            'revisions': run['revision'], 'completed': run['state'] == 'exported',
            'assistant_submissions': sum(e['kind'] == 'assistant_submission' for e in events),
            'questions_asked': sum(e['kind'] == 'question' for e in events),
            'owner_answers': sum(e['kind'] == 'answer' for e in events),
            'pending_responses': sum(e['kind'] == 'question_response' for e in events),
            'by_stage': stages, 'cost': None,
            'usage_scope': 'Provider-reported direct calls only; assistant conversation usage and unreported tokens are unknown.'}
