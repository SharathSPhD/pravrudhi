"""Parses the policy's raw completion into a structured ModelOutput.

Expected output schema (this is the format finetune_candidate should
already have been trained to produce -- the RL step reinforces adherence
to it rather than introducing it from scratch):

    <trace>
    fact:1 -> IPC:319
    </trace>
    <citation>IPC:319</citation>
    <answer>The act constitutes hurt under IPC 319.</answer>

or, when the graph does not support an answer:

    <abstain>I don't know -- the graph does not establish this.</abstain>

This parser is deliberately lenient (missing tags degrade gracefully to
empty fields rather than raising) since a malformed-but-plausible
completion during early RL rollouts must still be scorable -- and scoring
it as "no grounded citation, no trace" is itself the correct reward signal
for malformed output.
"""
from __future__ import annotations

import re

from data_contracts import ModelOutput

_TRACE_RE = re.compile(r"<trace>(.*?)</trace>", re.DOTALL)
_CITATION_RE = re.compile(r"<citation>(.*?)</citation>", re.DOTALL)
_ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)
_ABSTAIN_RE = re.compile(r"<abstain>(.*?)</abstain>", re.DOTALL)
_EDGE_RE = re.compile(r"([^\s\->]+)\s*->\s*([^\s\->]+)")


def parse_model_output(raw_text: str) -> ModelOutput:
    abstain_match = _ABSTAIN_RE.search(raw_text)
    if abstain_match:
        return ModelOutput(
            raw_text=raw_text,
            answer=None,
            citations=[],
            trace_node_ids=[],
            trace_edges=[],
            abstained=True,
        )

    trace_match = _TRACE_RE.search(raw_text)
    trace_edges: list[tuple[str, str]] = []
    trace_nodes: list[str] = []
    if trace_match:
        for line in trace_match.group(1).strip().splitlines():
            line = line.strip()
            if not line:
                continue
            edge_match = _EDGE_RE.match(line)
            if edge_match:
                src, dst = edge_match.group(1), edge_match.group(2)
                trace_edges.append((src, dst))
                trace_nodes.extend([src, dst])
            else:
                trace_nodes.append(line)
    # De-duplicate while preserving order.
    trace_nodes = list(dict.fromkeys(trace_nodes))

    citations = [c.strip() for c in _CITATION_RE.findall(raw_text) if c.strip()]

    answer_match = _ANSWER_RE.search(raw_text)
    answer = answer_match.group(1).strip() if answer_match else None

    return ModelOutput(
        raw_text=raw_text,
        answer=answer,
        citations=citations,
        trace_node_ids=trace_nodes,
        trace_edges=trace_edges,
        abstained=False,
    )
