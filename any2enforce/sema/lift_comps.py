"""Lift nested comprehensions to temporary assignments.

Backend only expands list/dict/set comps as the direct RHS of assign/return.
Any other nesting (call args, binary ops, nested comps as iterables, …) is
rewritten here to:

    _pyLiftN = <comp>
    ... use _pyLiftN ...

so the existing assign lowering applies. Runs after the frontend, before sema.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from ..ir import (
    AnnAssignStmt, AssignStmt, AttributeExpr, AugAssignStmt, BinOpExpr,
    BoolOpExpr, CallExpr, CompClause, CompareExpr, DictCompExpr, DictExpr,
    Expr, ExprStmt, ForStmt, IfStmt, JoinedStrExpr, KwArg, ListCompExpr,
    ListExpr, Module, NameExpr, RangeForStmt, ReturnStmt, SetCompExpr, Stmt,
    SubscriptExpr, TernaryExpr, UnaryOpExpr, WhileStmt,
)


_COMP_TYPES = (ListCompExpr, DictCompExpr, SetCompExpr)


class CompLifter:
    def __init__(self) -> None:
        self._n = 0

    def run(self, mod: Module) -> Module:
        for fn in mod.functions:
            fn.body = self._lift_body(fn.body)
        for cls in mod.classes:
            for m in cls.methods:
                m.body = self._lift_body(m.body)
        return mod

    def _fresh(self) -> str:
        name = f"_pyLift{self._n}"
        self._n += 1
        return name

    def _lift_body(self, body: List[Stmt]) -> List[Stmt]:
        out: List[Stmt] = []
        for stmt in body:
            out.extend(self._lift_stmt(stmt))
        return out

    def _lift_stmt(self, stmt: Stmt) -> List[Stmt]:
        lifts: List[Tuple[str, Expr]] = []

        if isinstance(stmt, AssignStmt):
            value = self._rewrite_expr(
                stmt.value, lifts, keep_top_comp=True)
            target = self._rewrite_expr(stmt.target, lifts, keep_top_comp=False)
            new_stmt: Stmt = AssignStmt(target, value, span=stmt.span)
        elif isinstance(stmt, AnnAssignStmt):
            value = None
            if stmt.value is not None:
                value = self._rewrite_expr(
                    stmt.value, lifts, keep_top_comp=True)
            target = self._rewrite_expr(stmt.target, lifts, keep_top_comp=False)
            new_stmt = AnnAssignStmt(
                target, stmt.type_ann, type=stmt.type, value=value,
                span=stmt.span)
        elif isinstance(stmt, ReturnStmt):
            value = None
            if stmt.value is not None:
                value = self._rewrite_expr(
                    stmt.value, lifts, keep_top_comp=True)
            new_stmt = ReturnStmt(value, span=stmt.span)
        elif isinstance(stmt, AugAssignStmt):
            target = self._rewrite_expr(stmt.target, lifts, keep_top_comp=False)
            value = self._rewrite_expr(stmt.value, lifts, keep_top_comp=False)
            new_stmt = AugAssignStmt(target, stmt.op, value, span=stmt.span)
        elif isinstance(stmt, ExprStmt):
            expr = self._rewrite_expr(stmt.expr, lifts, keep_top_comp=False)
            new_stmt = ExprStmt(expr, span=stmt.span)
        elif isinstance(stmt, IfStmt):
            branches = []
            for cond, body in stmt.branches:
                c = self._rewrite_expr(cond, lifts, keep_top_comp=False)
                branches.append((c, self._lift_body(body)))
            new_stmt = IfStmt(
                branches, self._lift_body(stmt.orelse), span=stmt.span)
        elif isinstance(stmt, WhileStmt):
            cond = self._rewrite_expr(stmt.cond, lifts, keep_top_comp=False)
            new_stmt = WhileStmt(
                cond, self._lift_body(stmt.body), span=stmt.span)
        elif isinstance(stmt, RangeForStmt):
            lo = self._rewrite_expr(stmt.lo, lifts, keep_top_comp=False)
            hi = self._rewrite_expr(stmt.hi, lifts, keep_top_comp=False)
            step = None
            if stmt.step is not None:
                step = self._rewrite_expr(
                    stmt.step, lifts, keep_top_comp=False)
            new_stmt = RangeForStmt(
                stmt.target, lo, hi, step, self._lift_body(stmt.body),
                span=stmt.span)
        elif isinstance(stmt, ForStmt):
            it = self._rewrite_expr(stmt.iterable, lifts, keep_top_comp=False)
            new_stmt = ForStmt(
                stmt.target, it, self._lift_body(stmt.body),
                elem_type=stmt.elem_type, span=stmt.span)
        else:
            return [stmt]

        prefix = [
            AssignStmt(NameExpr(name, span=comp.span), comp, span=comp.span)
            for name, comp in lifts
        ]
        return prefix + [new_stmt]

    def _rewrite_expr(self, e: Expr, lifts: List[Tuple[str, Expr]],
                      *, keep_top_comp: bool) -> Expr:
        """Rewrite ``e``. If it is a comprehension and ``keep_top_comp`` is
        False, lift it to a temp and return ``NameExpr``. Nested comps inside
        any expression are always lifted."""
        if isinstance(e, _COMP_TYPES):
            rewritten = self._rewrite_comp(e, lifts)
            if keep_top_comp:
                return rewritten
            name = self._fresh()
            lifts.append((name, rewritten))
            return NameExpr(name, span=e.span)

        if isinstance(e, CallExpr):
            args = [
                self._rewrite_expr(a, lifts, keep_top_comp=False)
                for a in e.args
            ]
            kwargs = [
                KwArg(
                    kw.name,
                    self._rewrite_expr(kw.value, lifts, keep_top_comp=False),
                    span=kw.span,
                )
                for kw in e.kwargs
            ]
            func = self._rewrite_expr(e.func, lifts, keep_top_comp=False)
            return CallExpr(func, args, kwargs, span=e.span)

        if isinstance(e, BinOpExpr):
            return BinOpExpr(
                e.op,
                self._rewrite_expr(e.left, lifts, keep_top_comp=False),
                self._rewrite_expr(e.right, lifts, keep_top_comp=False),
                span=e.span,
            )
        if isinstance(e, BoolOpExpr):
            return BoolOpExpr(
                e.op,
                [self._rewrite_expr(v, lifts, keep_top_comp=False)
                 for v in e.values],
                span=e.span,
            )
        if isinstance(e, CompareExpr):
            return CompareExpr(
                self._rewrite_expr(e.left, lifts, keep_top_comp=False),
                e.ops,
                [self._rewrite_expr(c, lifts, keep_top_comp=False)
                 for c in e.comparators],
                span=e.span,
            )
        if isinstance(e, UnaryOpExpr):
            return UnaryOpExpr(
                e.op,
                self._rewrite_expr(e.operand, lifts, keep_top_comp=False),
                span=e.span,
            )
        if isinstance(e, AttributeExpr):
            return AttributeExpr(
                self._rewrite_expr(e.value, lifts, keep_top_comp=False),
                e.attr, span=e.span)
        if isinstance(e, SubscriptExpr):
            return SubscriptExpr(
                self._rewrite_expr(e.value, lifts, keep_top_comp=False),
                self._rewrite_expr(e.index, lifts, keep_top_comp=False),
                span=e.span,
            )
        if isinstance(e, ListExpr):
            return ListExpr(
                [self._rewrite_expr(i, lifts, keep_top_comp=False)
                 for i in e.items],
                span=e.span,
            )
        if isinstance(e, DictExpr):
            return DictExpr(
                [
                    (
                        self._rewrite_expr(k, lifts, keep_top_comp=False),
                        self._rewrite_expr(v, lifts, keep_top_comp=False),
                    )
                    for k, v in e.items
                ],
                span=e.span,
            )
        if isinstance(e, JoinedStrExpr):
            parts = []
            for is_expr, part in e.parts:
                if is_expr:
                    parts.append(
                        (True, self._rewrite_expr(
                            part, lifts, keep_top_comp=False)))
                else:
                    parts.append((False, part))
            return JoinedStrExpr(parts, span=e.span)
        if isinstance(e, TernaryExpr):
            return TernaryExpr(
                self._rewrite_expr(e.cond, lifts, keep_top_comp=False),
                self._rewrite_expr(e.if_true, lifts, keep_top_comp=False),
                self._rewrite_expr(e.if_false, lifts, keep_top_comp=False),
                span=e.span,
            )
        return e

    def _rewrite_comp(self, e: Expr, lifts: List[Tuple[str, Expr]]) -> Expr:
        """Rewrite nested comps inside a comprehension; keep the outer node."""
        clauses = [self._rewrite_clause(c, lifts) for c in e.clauses]
        if isinstance(e, ListCompExpr):
            return ListCompExpr(
                self._rewrite_expr(e.elt, lifts, keep_top_comp=False),
                clauses, type=e.type, span=e.span)
        if isinstance(e, DictCompExpr):
            return DictCompExpr(
                self._rewrite_expr(e.key, lifts, keep_top_comp=False),
                self._rewrite_expr(e.value, lifts, keep_top_comp=False),
                clauses, type=e.type, span=e.span)
        if isinstance(e, SetCompExpr):
            return SetCompExpr(
                self._rewrite_expr(e.elt, lifts, keep_top_comp=False),
                clauses, type=e.type, span=e.span)
        return e

    def _rewrite_clause(self, c: CompClause,
                        lifts: List[Tuple[str, Expr]]) -> CompClause:
        iterable = None
        if c.iterable is not None:
            iterable = self._rewrite_expr(
                c.iterable, lifts, keep_top_comp=False)
        lo = hi = step = None
        if c.lo is not None:
            lo = self._rewrite_expr(c.lo, lifts, keep_top_comp=False)
        if c.hi is not None:
            hi = self._rewrite_expr(c.hi, lifts, keep_top_comp=False)
        if c.step is not None:
            step = self._rewrite_expr(c.step, lifts, keep_top_comp=False)
        ifs = [
            self._rewrite_expr(i, lifts, keep_top_comp=False) for i in c.ifs
        ]
        return CompClause(
            c.target, ifs=ifs, is_range=c.is_range, iterable=iterable,
            lo=lo, hi=hi, step=step, elem_type=c.elem_type, span=c.span,
        )


def lift_comprehensions(mod: Module) -> Module:
    return CompLifter().run(mod)
