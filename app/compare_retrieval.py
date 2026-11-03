"""Repeatable retrieval/answer worksheet with uncached network timing and usage estimates."""

import argparse
import asyncio
import contextvars
import hashlib
import json
import os
import statistics
import time
from dataclasses import asdict
from types import SimpleNamespace

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.knowledge import ROOT
from app.main import ChatRequest, MAX_OUTPUT_ATTEMPTS, ReplyRequest, generate_reply, load_system_prompt
from app.rag import FireworksEmbedder, RagConfig, Retriever, retrieval_query
from app.schemas import ChatResponse, fallback_response, out_of_scope_response
from app.search import SearchOptions

# Standard uncached USD / million tokens, verified 2026-11-03 at https://fireworks.ai/pricing.
# These are estimates, ignoring cache discounts; never presented as billed cost.
RATES = {'embedding_input': 0.10, 'chat_input': 0.30, 'chat_output': 1.20}
MODES = {
    'vector': SearchOptions(mode='vector'),
    'keyword': SearchOptions(mode='keyword'),
    'hybrid': SearchOptions(mode='hybrid'),
    'hybrid_rerank': SearchOptions(mode='hybrid', rerank=True),
    'hybrid_rewrite': SearchOptions(mode='hybrid', rewrite=True),
}
CURRENT_USAGE = contextvars.ContextVar('retrieval_evaluation_usage')


async def record_usage(response):
    await response.aread()
    try:
        body = response.json()
        usage = body.get('usage') or {}
    except (ValueError, AttributeError):
        usage = {}
    CURRENT_USAGE.get().append(dict(
        endpoint='embedding' if response.request.url.path.endswith('/embeddings') else 'chat',
        status=response.status_code, usage=usage,
    ))


def cost_estimate(calls):
    cost = 0.0
    for call in calls:
        usage = call['usage']
        if 'prompt_tokens' not in usage or (call['endpoint'] == 'chat' and 'completion_tokens' not in usage):
            return None
        if call['endpoint'] == 'embedding':
            cost += usage['prompt_tokens'] * RATES['embedding_input'] / 1_000_000
        else:
            cost += (usage['prompt_tokens'] * RATES['chat_input'] + usage['completion_tokens'] * RATES['chat_output']) / 1_000_000
    return round(cost, 8)


def recall(expected, sections):
    if not expected:
        return None
    return sum(any(label.casefold() in section.casefold() for section in sections) for label in expected) / len(expected)


def grade_answer(example, reply):
    if reply is None:
        return dict(passed=False, reason='No validated answer.')
    if example.get('must_abstain'):
        passed = reply.intent == 'unknown' and reply.requires_human
        return dict(passed=passed, abstention=passed)
    answer = reply.answer.casefold()
    matches = [any(term.casefold() in answer for term in alternatives) for alternatives in example['answer_groups']]
    passed = all(matches) and bool(reply.citations) and reply.intent in {'product', 'pricing', 'policy'}
    return dict(passed=passed, fact_groups=matches, cited=bool(reply.citations))


def summarize(rows):
    summary = {}
    for mode in MODES:
        selected = [row for row in rows if row['mode'] == mode]
        if not selected:
            continue
        labeled = [row for row in selected if row['recall_at_3'] is not None]
        graded = [row for row in selected if row.get('answer_grade') is not None]
        costs = [row['estimated_usd'] for row in selected]
        summary[mode] = dict(
            questions=len(selected),
            mean_recall_at_3=round(statistics.mean(row['recall_at_3'] for row in labeled), 4) if labeled else None,
            mean_evidence_recall=round(statistics.mean(row['evidence_recall'] for row in labeled), 4) if labeled else None,
            mean_context_characters=round(statistics.mean(row['context_characters'] for row in selected)),
            median_retrieval_ms=round(statistics.median(row['retrieval_ms'] for row in selected), 2),
            median_total_ms=round(statistics.median(row['total_ms'] for row in selected), 2),
            rubric_pass_rate=round(statistics.mean(row['answer_grade']['passed'] for row in graded), 4) if graded else None,
            estimated_total_usd=round(sum(costs), 6) if all(cost is not None for cost in costs) else None,
            failures=sum('error' in row for row in selected),
            assistant_fallbacks=sum(len(row.get('assistant_events', [])) for row in selected),
        )
    return summary


async def evaluate_case(operation):
    example, mode, retriever, state, generate_answers = operation
    calls = []
    token = CURRENT_USAGE.set(calls)
    body = ChatRequest(message=example['question'], history=example.get('history', []))
    started = time.perf_counter()
    row = dict(mode=mode, question=body.message, recall_at_3=0.0 if example['expected_sections'] else None,
               evidence_recall=0.0 if example['expected_sections'] else None, context_characters=0)
    try:
        async with asyncio.timeout(30):
            ranked = await retriever.ranked_candidates(retrieval_query(body))
            result = retriever.select(ranked)
            row['retrieval_ms'] = round((time.perf_counter() - started) * 1000, 2)
            sections = [retriever.chunks[cid].section for cid in ranked[:retriever.options.top_k]]
            context_sections = [chunk.section for chunk in result.chunks]
            row.update(recall_at_3=recall(example['expected_sections'], sections),
                       evidence_recall=recall(example['expected_sections'], context_sections),
                       context_characters=len(result.context()), sections=sections, context_sections=context_sections)
            if generate_answers:
                reply = None
                for attempt in range(MAX_OUTPUT_ATTEMPTS):
                    reply = await generate_reply(state, ReplyRequest(body, attempt, result))
                    if reply is not None:
                        break
                reply = reply or fallback_response()
                if reply.intent == 'out_of_scope':
                    reply = out_of_scope_response()
                row.update(answer=reply.model_dump(), answer_grade=grade_answer(example, reply))
    except Exception as error:
        # Save failures in the denominator instead of silently dropping hard examples.
        row['error'] = type(error).__name__
        if generate_answers:
            row['answer_grade'] = dict(passed=False, reason='Request failed.')
    finally:
        row.setdefault('retrieval_ms', round((time.perf_counter() - started) * 1000, 2))
        row['total_ms'] = round((time.perf_counter() - started) * 1000, 2)
        row['calls'] = calls
        row['estimated_usd'] = cost_estimate(calls)
        row['assistant_events'] = list(retriever.assistant.events) if retriever.assistant else []
        CURRENT_USAGE.reset(token)
    return row


def rescore(report, examples):
    by_question = {example['question']: example for example in examples}
    for row in report['results']:
        example = by_question[row['question']]
        row['recall_at_3'] = recall(example['expected_sections'], row.get('sections', []))
        row['evidence_recall'] = recall(example['expected_sections'], row.get('context_sections', []))
        if 'answer' in row:
            row['answer_grade'] = grade_answer(example, ChatResponse.model_validate(row['answer']))
    report['worksheet'] = examples
    report['worksheet_sha256'] = hashlib.sha256(json.dumps(examples, sort_keys=True).encode()).hexdigest()
    report['summary'] = summarize(report['results'])
    return report


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--answers', action='store_true', help='Also generate and rubric-check answers (paid chat calls).')
    parser.add_argument('--rescore', action='store_true', help='Recheck saved outputs against the current worksheet without API calls.')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env', override=False)
    config = RagConfig.from_environment()
    examples = json.loads((ROOT / 'steps/04-retrieval-examples.json').read_text())
    target = ROOT / '.rag/retrieval-comparison.json'
    if args.rescore:
        report = rescore(json.loads(target.read_text()), examples)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report['summary'], indent=2))
        return
    model = os.getenv('FIREWORKS_MODEL', 'accounts/fireworks/models/deepseek-v4p1-flash')
    if model != 'accounts/fireworks/models/deepseek-v4p1-flash' or config.model != 'fireworks/qwen3-embedding-8b':
        raise ValueError('Update the documented price assumptions before comparing different models.')
    embedder = FireworksEmbedder(config)
    await embedder.close()
    transport = httpx.AsyncClient(event_hooks={'response': [record_usage]})
    client = AsyncOpenAI(api_key=os.environ['FIREWORKS_API_KEY'], base_url='https://api.fireworks.ai/inference/v1',
                         timeout=30, max_retries=0, http_client=transport)
    embedder.client = client
    state = SimpleNamespace(provider='fireworks', model=model, openai=client, system_prompt=load_system_prompt())
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    semaphore = asyncio.Semaphore(2)
    report = dict(source_version=None, questions=len(examples), generate_answers=args.answers,
                  rates_usd_per_million=RATES, price_source='https://fireworks.ai/pricing', price_checked='2026-11-03',
                  worksheet=examples, worksheet_sha256=hashlib.sha256(json.dumps(examples, sort_keys=True).encode()).hexdigest(),
                  options={mode: asdict(options) for mode, options in MODES.items()},
                  limitations='Small non-held-out worksheet; section-label recall, not exhaustive chunk precision. '
                  'Fact-group/abstention rubric is a screening metric, not proof of factual correctness. '
                  'Single trial, concurrency two, uncached queries, rotated order; latency and model outputs vary. '
                  'USD estimates use reported usage and standard uncached rates, ignoring discounts, tax and retries outside this run.')

    async def run_question(index, example):
        async with semaphore:
            modes = list(MODES)
            for mode in modes[index % len(modes):] + modes[:index % len(modes)]:
                retriever = Retriever(config, embedder, MODES[mode])
                report['source_version'] = retriever.version
                row = await evaluate_case((example, mode, retriever, state, args.answers))
                rows.append(row)
                report.update(summary=summarize(rows), results=rows)
                target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            print(f'Completed {index + 1}/{len(examples)}: {example["question"]}', flush=True)

    try:
        await asyncio.gather(*(run_question(index, example) for index, example in enumerate(examples)))
        print(json.dumps(dict(report=str(target), summary=report['summary']), ensure_ascii=False, indent=2))
    finally:
        await client.close()


if __name__ == '__main__':
    asyncio.run(main())
