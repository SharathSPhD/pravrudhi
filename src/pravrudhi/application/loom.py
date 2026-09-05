"""A compiled intent plan and a Loom program had no way to check each other, so drift between them was invisible.

This module is milestone 1 of Loom in Pravrudhi: a tokenizer and recursive-descent parser for the subset of the
Loom language defined in GRAMMAR.md, plus a lossy but order-preserving bridge to and from an `IntentPlanProposal`.
`lower` renders a compiled plan as Loom source naming exactly the resources and capabilities the plan proposed,
never a quantity the plan did not carry. `lift` parses that source (or any program in the grammar's subset) back
into a typed AST. `to_plan_steps` reads the ordered capability of each stage back out of that AST, so a round trip
through source can be checked rather than assumed. Nothing here executes a model, reads a filesystem, or touches
the kernel; it is pure text in, typed tree out, and typed tree in, text out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pravrudhi.application.intent import IntentPlanProposal, IntentStepProposal

# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?:%|[KMBT])?")
_UNIT_SCALE = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
_PUNCT_MULTI = ("<=", ">=", "==")
_PUNCT_SINGLE = ("=", ";", "{", "}", "(", ")", ",", ".", "+", "*", "<", ">")


class ParseError(Exception):
    """A malformed program used to fail somewhere the author could not find, with no line to look at."""

    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(f"{message} at line {line}, column {col}")
        self.message = message
        self.line = line
        self.col = col


@dataclass(frozen=True)
class Token:
    kind: str  # "IDENT" | "NUMBER" | "STRING" | "PUNCT" | "EOF"
    text: str
    line: int
    col: int
    value: float | str | None = None


def _number_value(raw: str) -> float:
    """A literal like `800M` or `2%` used to be typed as a plain number and misread by a factor of a million."""
    body = raw
    suffix = ""
    if body.endswith("%"):
        suffix, body = "%", body[:-1]
    elif body and body[-1] in _UNIT_SCALE:
        suffix, body = body[-1], body[:-1]
    numeric = float(body)
    if suffix == "%":
        return numeric / 100.0
    return numeric * _UNIT_SCALE.get(suffix, 1.0)


def tokenize(source: str) -> list[Token]:
    """The grammar's lexical rules: ident, unit-suffixed number, string, `//` comment."""
    tokens: list[Token] = []
    i, line, col, n = 0, 1, 1, len(source)

    def step(count: int) -> None:
        nonlocal i, line, col
        for _ in range(count):
            if source[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = source[i]
        if ch in " \t\r\n":
            step(1)
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                step(1)
            continue
        if ch == '"':
            start_line, start_col = line, col
            j = i + 1
            while j < n and source[j] not in ('"', "\n"):
                j += 1
            if j >= n or source[j] != '"':
                raise ParseError("unterminated string literal", start_line, start_col)
            value = source[i + 1 : j]
            tokens.append(Token("STRING", source[i : j + 1], start_line, start_col, value))
            step(j + 1 - i)
            continue
        if ch.isdigit():
            match = _NUMBER_RE.match(source, i)
            assert match is not None
            raw = match.group(0)
            tokens.append(Token("NUMBER", raw, line, col, _number_value(raw)))
            step(len(raw))
            continue
        if ch.isalpha() or ch == "_":
            match = _IDENT_RE.match(source, i)
            assert match is not None
            raw = match.group(0)
            tokens.append(Token("IDENT", raw, line, col))
            step(len(raw))
            continue
        symbol = next((s for s in _PUNCT_MULTI + _PUNCT_SINGLE if source.startswith(s, i)), None)
        if symbol is None:
            raise ParseError(f"unexpected character {ch!r}", line, col)
        tokens.append(Token("PUNCT", symbol, line, col))
        step(len(symbol))
    tokens.append(Token("EOF", "", line, col))
    return tokens


# ---------------------------------------------------------------------------
# AST -- frozen dataclasses, every node carrying the position it started at.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ident:
    line: int
    col: int
    name: str


@dataclass(frozen=True)
class NumberLit:
    line: int
    col: int
    raw: str
    value: float


@dataclass(frozen=True)
class StringLit:
    line: int
    col: int
    value: str


@dataclass(frozen=True)
class Member:
    line: int
    col: int
    target: Expr
    name: str


@dataclass(frozen=True)
class Arg:
    line: int
    col: int
    name: str | None
    value: Expr


@dataclass(frozen=True)
class BlockAssign:
    line: int
    col: int
    name: str
    value: Expr


@dataclass(frozen=True)
class Block:
    line: int
    col: int
    assigns: tuple[BlockAssign, ...]


@dataclass(frozen=True)
class Call:
    line: int
    col: int
    callee: Expr
    args: tuple[Arg, ...]
    block: Block | None


@dataclass(frozen=True)
class BinOp:
    line: int
    col: int
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Compare:
    line: int
    col: int
    op: str
    left: Expr
    right: Expr


Expr = Ident | NumberLit | StringLit | Member | Call | BinOp | Compare


@dataclass(frozen=True)
class Decl:
    line: int
    col: int
    type_: str
    name: str
    value: Expr


@dataclass(frozen=True)
class Assign:
    line: int
    col: int
    name: str
    value: Expr


@dataclass(frozen=True)
class Assert:
    line: int
    col: int
    left: Expr
    op: str
    right: Expr


@dataclass(frozen=True)
class Export:
    line: int
    col: int
    name: str
    path: str


@dataclass(frozen=True)
class Import:
    line: int
    col: int
    path: str


Stmt = Decl | Assign | Assert | Export | Import


@dataclass(frozen=True)
class LoomProgram:
    stmts: tuple[Stmt, ...]


# ---------------------------------------------------------------------------
# Parser -- recursive descent over GRAMMAR.md's EBNF, no more.
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS = frozenset({"target", "corpus", "tokenizer", "model", "evalset", "unit"})
_CMP_OPS = frozenset({"<", ">", "<=", ">=", "=="})


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self, offset: int = 0) -> Token:
        idx = min(self._pos + offset, len(self._tokens) - 1)
        return self._tokens[idx]

    def _advance(self) -> Token:
        tok = self._peek()
        if tok.kind != "EOF":
            self._pos += 1
        return tok

    def _expect_punct(self, symbol: str) -> Token:
        tok = self._peek()
        if not (tok.kind == "PUNCT" and tok.text == symbol):
            raise ParseError(f"expected {symbol!r}, found {tok.text or 'end of input'!r}", tok.line, tok.col)
        return self._advance()

    def _expect_ident(self) -> Token:
        tok = self._peek()
        if tok.kind != "IDENT":
            raise ParseError(f"expected an identifier, found {tok.text or 'end of input'!r}", tok.line, tok.col)
        return self._advance()

    def _expect_ident_text(self, text: str) -> Token:
        tok = self._expect_ident()
        if tok.text != text:
            raise ParseError(f"expected {text!r}, found {tok.text!r}", tok.line, tok.col)
        return tok

    def _expect_string(self) -> Token:
        tok = self._peek()
        if tok.kind != "STRING":
            raise ParseError(f"expected a string literal, found {tok.text or 'end of input'!r}", tok.line, tok.col)
        return self._advance()

    def parse_program(self) -> LoomProgram:
        stmts: list[Stmt] = []
        while self._peek().kind != "EOF":
            stmts.append(self._parse_stmt())
        return LoomProgram(tuple(stmts))

    def _parse_stmt(self) -> Stmt:
        tok = self._peek()
        if tok.kind != "IDENT":
            raise ParseError(f"expected a statement, found {tok.text or 'end of input'!r}", tok.line, tok.col)
        if tok.text in _TYPE_KEYWORDS:
            return self._parse_decl()
        if tok.text == "assert":
            return self._parse_assert()
        if tok.text == "export":
            return self._parse_export()
        if tok.text == "import":
            return self._parse_import()
        return self._parse_assign()

    def _parse_decl(self) -> Decl:
        type_tok = self._advance()
        name_tok = self._expect_ident()
        self._expect_punct("=")
        value = self._parse_expr()
        self._expect_punct(";")
        return Decl(type_tok.line, type_tok.col, type_tok.text, name_tok.text, value)

    def _parse_assign(self) -> Assign:
        name_tok = self._advance()
        self._expect_punct("=")
        value = self._parse_expr()
        self._expect_punct(";")
        return Assign(name_tok.line, name_tok.col, name_tok.text, value)

    def _parse_assert(self) -> Assert:
        kw = self._advance()
        expr = self._parse_expr()
        self._expect_punct(";")
        if not isinstance(expr, Compare):
            raise ParseError("assert requires a comparison (expr cmp expr)", kw.line, kw.col)
        return Assert(kw.line, kw.col, expr.left, expr.op, expr.right)

    def _parse_export(self) -> Export:
        kw = self._advance()
        name_tok = self._expect_ident()
        self._expect_ident_text("to")
        path_tok = self._expect_string()
        self._expect_punct(";")
        assert isinstance(path_tok.value, str)
        return Export(kw.line, kw.col, name_tok.text, path_tok.value)

    def _parse_import(self) -> Import:
        kw = self._advance()
        path_tok = self._expect_string()
        self._expect_punct(";")
        assert isinstance(path_tok.value, str)
        return Import(kw.line, kw.col, path_tok.value)

    def _parse_expr(self) -> Expr:
        left = self._parse_additive()
        tok = self._peek()
        if tok.kind == "PUNCT" and tok.text in _CMP_OPS:
            op = self._advance().text
            right = self._parse_additive()
            return Compare(left.line, left.col, op, left, right)
        return left

    def _parse_additive(self) -> Expr:
        left = self._parse_multiplicative()
        while self._peek().kind == "PUNCT" and self._peek().text == "+":
            self._advance()
            right = self._parse_multiplicative()
            left = BinOp(left.line, left.col, "+", left, right)
        return left

    def _parse_multiplicative(self) -> Expr:
        left = self._parse_postfix()
        while self._peek().kind == "PUNCT" and self._peek().text == "*":
            self._advance()
            right = self._parse_postfix()
            left = BinOp(left.line, left.col, "*", left, right)
        return left

    def _parse_postfix(self) -> Expr:
        node = self._parse_atom()
        while self._peek().kind == "PUNCT" and self._peek().text == ".":
            dot = self._advance()
            name_tok = self._expect_ident()
            member = Member(dot.line, dot.col, node, name_tok.text)
            if self._peek().kind == "PUNCT" and self._peek().text == "(":
                args = self._parse_args_paren()
                block = self._parse_block_opt()
                node = Call(dot.line, dot.col, member, args, block)
            else:
                node = member
        return node

    def _parse_atom(self) -> Expr:
        tok = self._peek()
        if tok.kind == "NUMBER":
            self._advance()
            assert isinstance(tok.value, float)
            return NumberLit(tok.line, tok.col, tok.text, tok.value)
        if tok.kind == "STRING":
            self._advance()
            assert isinstance(tok.value, str)
            return StringLit(tok.line, tok.col, tok.value)
        if tok.kind == "IDENT":
            self._advance()
            node: Expr = Ident(tok.line, tok.col, tok.text)
            if self._peek().kind == "PUNCT" and self._peek().text == "(":
                args = self._parse_args_paren()
                block = self._parse_block_opt()
                node = Call(tok.line, tok.col, node, args, block)
            return node
        raise ParseError(f"unexpected token {tok.text or 'end of input'!r} in expression", tok.line, tok.col)

    def _parse_args_paren(self) -> tuple[Arg, ...]:
        self._expect_punct("(")
        args: list[Arg] = []
        if not (self._peek().kind == "PUNCT" and self._peek().text == ")"):
            args.append(self._parse_arg())
            while self._peek().kind == "PUNCT" and self._peek().text == ",":
                self._advance()
                args.append(self._parse_arg())
        self._expect_punct(")")
        return tuple(args)

    def _parse_arg(self) -> Arg:
        tok = self._peek()
        if tok.kind == "IDENT" and self._peek(1).kind == "PUNCT" and self._peek(1).text == "=":
            name_tok = self._advance()
            self._advance()
            value = self._parse_expr()
            return Arg(name_tok.line, name_tok.col, name_tok.text, value)
        value = self._parse_expr()
        return Arg(value.line, value.col, None, value)

    def _parse_block_opt(self) -> Block | None:
        if not (self._peek().kind == "PUNCT" and self._peek().text == "{"):
            return None
        brace = self._advance()
        assigns: list[BlockAssign] = []
        while not (self._peek().kind == "PUNCT" and self._peek().text == "}"):
            name_tok = self._expect_ident()
            self._expect_punct("=")
            value = self._parse_expr()
            self._expect_punct(";")
            assigns.append(BlockAssign(name_tok.line, name_tok.col, name_tok.text, value))
        self._expect_punct("}")
        return Block(brace.line, brace.col, tuple(assigns))


def lift(source: str) -> LoomProgram:
    """Parse Loom source -- hand-written or produced by `lower` -- into the typed AST."""
    return _Parser(tokenize(source)).parse_program()


# ---------------------------------------------------------------------------
# Plan -> source. Every name in the output is a resource or capability the plan already carries.
# ---------------------------------------------------------------------------

# The stage name a capability lowers to when it is not one of the specially-rendered forms
# (corpus, evaluate). Kept distinct from the capability string only where the language's own
# vocabulary differs (`rl` -> `align`); every other capability names its own stage.
_CAPABILITY_CALL: dict[str, str] = {
    "pretrain": "pretrain",
    "finetune": "finetune",
    "rl": "align",
    "performance": "performance",
    "retrieval": "retrieval",
    "safety": "safety",
    "agents": "agents",
    "evaluate": "evaluate",
}
_CALL_CAPABILITY: dict[str, str] = {call: capability for capability, call in _CAPABILITY_CALL.items()}
_CORPUS_CONSUMING = frozenset({"pretrain", "finetune", "rl", "retrieval"})

_UNSAFE_IDENT_CHARS = re.compile(r"[^A-Za-z0-9_]")


def _ident_safe(text: str) -> str:
    safe = _UNSAFE_IDENT_CHARS.sub("_", text)
    return safe if safe and not safe[0].isdigit() else f"_{safe}"


def _quantity_comments(step: IntentStepProposal, indent: str) -> list[str]:
    """A missing budget used to disappear silently; here it disappears into a comment instead of a guess."""
    lines: list[str] = []
    for q in step.quantities:
        if q.value is None:
            lines.append(f"{indent}// {q.name} unspecified")
        else:
            lines.append(f"{indent}{q.name} = {q.value};")
    return lines


def _lower_evaluate(step: IntentStepProposal) -> list[str]:
    """A benchmark score with nothing to compare against is not an improvement, so it never gets an `assert`.

    When the step consumes a prior baseline, each benchmark becomes a real comparison. Otherwise the step still
    has to appear in the source -- something is about to be measured -- so it renders as a call carrying only
    comments, which keeps it visible to `to_plan_steps` without asserting a comparison that cannot yet be made.
    """
    if "baseline_results" in step.consumes:
        lines = [
            f"assert {_ident_safe(b.id)}(m, evalset) > baseline;  // {b.metric}" for b in step.check.benchmarks
        ]
        lines.extend(_quantity_comments(step, indent=""))
        return lines
    lines = ["m = evaluate(m) {"]
    for benchmark in step.check.benchmarks:
        metric_ident = _ident_safe(benchmark.id)
        lines.append(f"    // {metric_ident} unmeasured: no baseline recorded yet for {benchmark.metric!r}")
    lines.extend(_quantity_comments(step, indent="    "))
    lines.append("};")
    return lines


def lower(plan: IntentPlanProposal) -> str:
    """Render a compiled plan as Loom source, naming nothing the plan did not itself propose.

    The substrate is always `load("base_model")`, because a plan never invents which base model it started
    from. A `corpus` step becomes a `corpus` decl named after the resource the plan says it produces. `finetune`
    and `rl` become `finetune`/`align` calls rebinding `m`. `evaluate` becomes one `assert` per declared benchmark
    when the step consumes a prior baseline, and a comment saying the benchmark is unmeasured otherwise. Every
    quantity the plan left unresolved is a comment, never a number, and no algorithm choice the plan never made
    (an RL `algo`, an optimizer) is written in as if it had been decided.
    """
    lines: list[str] = [
        f"// objective: {plan.objective.id} (track {plan.objective.track})",
        "// provenance: agama -- nothing below has executed",
    ]
    for note in plan.assumptions:
        lines.append(f"// assumption: {note}")
    lines.append("")
    lines.append('target arch = load("base_model");')
    lines.append("model m = arch;")
    lines.append("")

    corpus_name: str | None = None
    for step in plan.steps:
        capability = step.capability
        if capability == "evaluate":
            lines.extend(_lower_evaluate(step))
        elif capability == "corpus":
            corpus_name = _ident_safe(step.produces[0]) if step.produces else "prepared_corpus"
            lines.append(f'corpus {corpus_name} = data.text("{corpus_name}") {{')
            lines.extend(_quantity_comments(step, indent="    "))
            lines.append("};")
        else:
            call_name = _CAPABILITY_CALL.get(capability, capability)
            call_args = ["m"]
            if capability in _CORPUS_CONSUMING and corpus_name is not None:
                call_args.append(corpus_name)
            lines.append(f"m = {call_name}({', '.join(call_args)}) {{")
            lines.extend(_quantity_comments(step, indent="    "))
            lines.append("};")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Source -> ordered capability steps.
# ---------------------------------------------------------------------------


def _statement_capability(stmt: Stmt) -> str | None:
    if isinstance(stmt, Assert):
        return "evaluate"
    if isinstance(stmt, Decl) and stmt.type_ == "corpus":
        return "corpus"
    if isinstance(stmt, Assign) and isinstance(stmt.value, Call) and isinstance(stmt.value.callee, Ident):
        return _CALL_CAPABILITY.get(stmt.value.callee.name)
    return None


def to_plan_steps(program: LoomProgram) -> tuple[str, ...]:
    """The ordered capability of each stage in `program`, recovered from its calls, decls and asserts.

    A run of consecutive statements sharing one capability -- most often the several `assert` lines an
    `evaluate` step emits, one per benchmark -- is a single step recovered once, because compiling a plan never
    schedules the same capability twice back to back; only one proposed step ever renders that way.
    """
    capabilities: list[str] = []
    for stmt in program.stmts:
        capability = _statement_capability(stmt)
        if capability is None or (capabilities and capabilities[-1] == capability):
            continue
        capabilities.append(capability)
    return tuple(capabilities)
