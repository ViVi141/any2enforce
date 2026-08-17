"""Semantic analysis on the IR.

Responsibilities (v0.1):
  * resolve raw annotation strings -> IR Types
  * resolve function/method parameter & return types (untyped params -> error + fallback)
  * field hoisting: `this.x = ...` assignments inside methods become class fields
  * resolve `foreach` element types from the local type environment
  * light inference for unannotated locals so `auto` decisions are informed
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..diagnostics import DiagnosticSink
from ..ir import (
    AUTO, BOOL, FLOAT, INT, STRING, VOID, AnnAssignStmt, ArrayType,
    AssignStmt, AttributeExpr, AugAssignStmt, BoolOpExpr, BinOpExpr, CallExpr,
    ClassDef, CompareExpr, ConstExpr, DictExpr, ErrorType, Expr, ExprStmt,
    Field, ForStmt, FunctionDef, IfStmt, ImportStmt, JoinedStrExpr, ListExpr,
    MapType, MethodDef, Module, NameExpr, Param, RangeForStmt, ReturnStmt,
    SetType, Stmt, SubscriptExpr, TernaryExpr, Type, UnaryOpExpr, WhileStmt,
)
from .types import parse_type_annotation

BUILTIN_MODULES = {
    "math", "random", "json", "os", "sys", "re", "time", "datetime",
    "itertools", "functools", "typing", "enum", "dataclasses", "pathlib",
    "collections", "struct", "uuid",
}

BUILTIN_CALLS = {
    "print", "len", "str", "int", "float", "bool", "range",
    "min", "max", "abs", "sum",
}

_RETURN_OF_BUILTIN = {
    "len": INT, "str": STRING, "int": INT, "float": FLOAT, "bool": BOOL,
    "min": AUTO, "max": AUTO, "abs": AUTO, "sum": AUTO,
}


class Analyzer:
    def __init__(self, diagnostics: DiagnosticSink, config: dict) -> None:
        self.diag = diagnostics
        self.config = config
        self.fn_returns: Dict[str, Type] = {}
        self.class_names: set = set()

    # ------------------------------------------------------------------
    def run(self, mod: Module) -> Module:
        for fn in mod.functions:
            self.fn_returns[fn.name] = self._resolve_return(fn)
        # collect each class's required ctor params (no default value) —
        # EnforceScript implicitly forwards ctor params by name (verified
        # SCR_TimerEntries.c: SCR_WorldTimerEntry(string name, World world)
        # extends SCR_TimerEntryBase(string name); probes P01/P02)
        self.class_required_ctor: Dict[str, List[str]] = {}
        for cls in mod.classes:
            req = []
            for m in cls.methods:
                if m.is_constructor:
                    req = [p.name for p in m.params if p.default is None]
            self.class_required_ctor[cls.name] = req
        for cls in mod.classes:
            self.class_names.add(cls.name)
            self._resolve_class(cls)
        for fn in mod.functions:
            self._resolve_function(fn)
        for imp in mod.imports:
            if imp.module in BUILTIN_MODULES:
                self.diag.info(
                    "builtin-import",
                    f"import '{imp.module}' is dropped (no import system in EnforceScript)",
                    imp.span,
                )
        return mod

    # ------------------------------------------------------------------
    def _resolve_function(self, fn: FunctionDef) -> None:
        env: Dict[str, Type] = {}
        for p in fn.params:
            self._resolve_param(p, env, fn.name)
        fn.locals = self._analyze_body(fn.body, env)

    def _resolve_class(self, cls: ClassDef) -> None:
        if len(cls.bases) > 1:
            self.diag.error(
                "multiple-inheritance",
                f"class '{cls.name}' uses multiple inheritance; EnforceScript "
                "supports single inheritance only",
                cls.span,
                note="refactor to composition / mixin hierarchy",
            )
            cls.todos.append("multiple-inheritance")
        for m in cls.methods:
            env: Dict[str, Type] = {}
            for p in m.params:
                self._resolve_param(p, env, f"{cls.name}.{m.name}")
            m._param_env = env  # used for field inference below
            if m.is_constructor:
                m.return_type = VOID
            else:
                self._resolve_return(m)

        # EnforceScript has no explicit base-ctor call syntax: ctor params are
        # implicitly forwarded by name. A base with required ctor params forces
        # the derived ctor to declare them (verified: P01/P02 compile errors +
        # SCR_TimerEntries.c where SCR_WorldTimerEntry(string name, World world)
        # extends SCR_TimerEntryBase(string name)).
        for base in cls.bases:
            req = self.class_required_ctor.get(base, [])
            if not req:
                continue
            ctor = next((m for m in cls.methods if m.is_constructor), None)
            if ctor is None:
                continue  # no ctor at all compiles (SCR_RealTimerEntry precedent)
            own = {p.name for p in ctor.params}
            missing = [r for r in req if r not in own]
            if missing:
                self.diag.error(
                    "ctor-forward",
                    f"base class '{base}' constructor requires parameter(s) "
                    f"{missing}; EnforceScript implicitly forwards constructor "
                    "parameters (no super-call syntax) — declare them in "
                    f"'{cls.name}' constructor",
                    cls.span,
                    note="rename the derived ctor params to match the base's "
                         "required param names",
                )

        # field hoisting: scan all method bodies for `this.<x> = ...`
        field_map: Dict[str, Tuple[Type, Optional[ConstExpr], int]] = {}
        for m in cls.methods:
            param_env = getattr(m, "_param_env", {})
            self._collect_fields(m.body, field_map, param_env)
        for name, (typ, default, line) in field_map.items():
            if isinstance(typ, ErrorType):
                self.diag.error(
                    "field-type",
                    f"cannot determine type of field '{cls.name}.{name}' "
                    f"(first assigned at line {line})",
                    note="annotate the first self.<name> assignment, e.g. "
                         "self.name: str = ...",
                )
            cls.fields.append(Field(name, typ, default))
        # drop temp attr
        for m in cls.methods:
            if hasattr(m, "_param_env"):
                del m._param_env

        # analyze method bodies with the (now complete) field set for env types
        for m in cls.methods:
            env = {p.name: p.type for p in m.params}
            m.locals = self._analyze_body(m.body, env)

    def _resolve_param(self, p: Param, env: Dict[str, Type], owner: str) -> None:
        if p.type_ann:
            p.type = parse_type_annotation(p.type_ann)
            env[p.name] = p.type
        else:
            fallback = self.config.get("types", {}).get(
                "untyped_param_fallback", "float")
            p.type = ErrorType(fallback=fallback)
            self.diag.error(
                "untyped-param",
                f"parameter '{owner}.{p.name}' has no type annotation",
                p.span,
                note=f"emitted with fallback type '{fallback}' "
                     "(config types.untyped_param_fallback)",
            )
            env[p.name] = p.type
        if p.default is not None:
            # EnforceScript supports default parameter values
            # (verified: `void Print(string msg, LogLevel level = LogLevel.NORMAL)`)
            pass

    def _resolve_return(self, fn) -> Type:
        typ = parse_type_annotation(fn.return_ann, is_return=True) \
            if fn.return_ann else VOID
        fn.return_type = typ
        return typ

    # ------------------------------------------------------------------
    # field hoisting
    # ------------------------------------------------------------------
    def _collect_fields(self, body: List[Stmt],
                        field_map: Dict[str, Tuple[Type, Optional[ConstExpr], int]],
                        param_env: Dict[str, Type]) -> None:
        for stmt in body:
            target = _attr_target(stmt)
            if target is not None:
                attr, value = target
                if attr not in field_map:
                    typ = self._infer(value, param_env) or ErrorType()
                    default = value if isinstance(value, ConstExpr) else None
                    line = stmt.span.line if stmt.span else 0
                    field_map[attr] = (typ, default, line)
            for child in _child_stmts(stmt):
                self._collect_fields([child], field_map, param_env)

    # ------------------------------------------------------------------
    # statement walk + local env
    # ------------------------------------------------------------------
    def _analyze_body(self, body: List[Stmt], env: Dict[str, Type]) -> Dict[str, Type]:
        """Walk statements, updating `env`; returns the final local type map."""
        for stmt in body:
            if isinstance(stmt, AnnAssignStmt) and isinstance(stmt.target, NameExpr):
                stmt.type = parse_type_annotation(stmt.type_ann) if stmt.type_ann else AUTO
                env[stmt.target.name] = stmt.type
                if stmt.value:
                    self._analyze_expr(stmt.value, env)
            elif isinstance(stmt, AssignStmt) and isinstance(stmt.target, NameExpr):
                self._analyze_expr(stmt.value, env)
                if stmt.target.name not in env:
                    t = self._infer(stmt.value, env)
                    if t is not None:
                        env[stmt.target.name] = t
            elif isinstance(stmt, AssignStmt):
                # attribute / subscript targets (self.x = ..., m[k] = v)
                self._analyze_expr(stmt.target, env)
                self._analyze_expr(stmt.value, env)
            elif isinstance(stmt, AugAssignStmt):
                self._analyze_expr(stmt.target, env)
                self._analyze_expr(stmt.value, env)
            elif isinstance(stmt, ExprStmt):
                self._analyze_expr(stmt.expr, env)
            elif isinstance(stmt, ReturnStmt):
                if stmt.value:
                    self._analyze_expr(stmt.value, env)
            elif isinstance(stmt, IfStmt):
                for cond, body2 in stmt.branches:
                    self._analyze_expr(cond, env)
                    self._analyze_body(body2, dict(env))
                self._analyze_body(stmt.orelse, dict(env))
            elif isinstance(stmt, WhileStmt):
                self._analyze_expr(stmt.cond, env)
                self._analyze_body(stmt.body, dict(env))
            elif isinstance(stmt, RangeForStmt):
                self._analyze_expr(stmt.lo, env)
                self._analyze_expr(stmt.hi, env)
                if stmt.step:
                    self._analyze_expr(stmt.step, env)
                env[stmt.target.name] = INT
                self._analyze_body(stmt.body, dict(env))
            elif isinstance(stmt, ForStmt):
                self._analyze_expr(stmt.iterable, env)
                it = self._infer(stmt.iterable, env)
                if isinstance(it, (ArrayType, SetType)):
                    stmt.elem_type = it.elem
                elif it is STRING:
                    self.diag.error(
                        "foreach-string",
                        "iterating over a string is not supported in v0.1",
                        stmt.span,
                    )
                    stmt.elem_type = ErrorType(fallback="auto")
                else:
                    self.diag.error(
                        "foreach-type",
                        "cannot determine element type for 'foreach'",
                        stmt.span,
                        note="annotate the iterable variable or use range()",
                    )
                    stmt.elem_type = ErrorType(fallback="auto")
                env[stmt.target.name] = stmt.elem_type
                self._analyze_body(stmt.body, dict(env))
        return env

    # ------------------------------------------------------------------
    def _analyze_expr(self, e: Expr, env: Dict[str, Type]) -> None:
        # attach resolved types to nodes the backend needs (literals, calls)
        if isinstance(e, ConstExpr):
            e.type = self._infer(e, env)
        elif isinstance(e, ListExpr):
            e.type = self._infer(e, env)
        elif isinstance(e, DictExpr):
            e.type = self._infer(e, env)
        elif isinstance(e, JoinedStrExpr):
            e.type = STRING
        elif isinstance(e, SubscriptExpr):
            e.base_type = self._infer(e.value, env)
        elif isinstance(e, CallExpr) and isinstance(e.func, NameExpr):
            e.type = self._infer(e, env)
        if isinstance(e, CallExpr):
            for a in e.args:
                self._analyze_expr(a, env)
            if isinstance(e.func, NameExpr) and e.func.name not in env \
                    and e.func.name not in BUILTIN_CALLS \
                    and e.func.name not in self.fn_returns \
                    and e.func.name not in self.class_names:
                self.diag.warning(
                    "unknown-call",
                    f"unknown function or builtin '{e.func.name}'",
                    e.span,
                    note="add it to the builtin mapping table or define it",
                )
        elif isinstance(e, BinOpExpr):
            self._analyze_expr(e.left, env)
            self._analyze_expr(e.right, env)
        elif isinstance(e, BoolOpExpr):
            for v in e.values:
                self._analyze_expr(v, env)
            if e.op == "and" and any(
                    self._infer(v, env) is not None and self._infer(v, env) is not BOOL
                    for v in e.values):
                self.diag.warning(
                    "boolop-nonbool",
                    "and/or on non-bool operands: EnforceScript returns bool, "
                    "Python returns the operand",
                    e.span,
                )
        elif isinstance(e, CompareExpr):
            self._analyze_expr(e.left, env)
            for c in e.comparators:
                self._analyze_expr(c, env)
        elif isinstance(e, UnaryOpExpr):
            self._analyze_expr(e.operand, env)
        elif isinstance(e, AttributeExpr):
            self._analyze_expr(e.value, env)
        elif isinstance(e, SubscriptExpr):
            self._analyze_expr(e.value, env)
            self._analyze_expr(e.index, env)
        elif isinstance(e, ListExpr):
            for i in e.items:
                self._analyze_expr(i, env)
        elif isinstance(e, DictExpr):
            for k, v in e.items:
                self._analyze_expr(k, env)
                self._analyze_expr(v, env)
        elif isinstance(e, JoinedStrExpr):
            for is_expr, part in e.parts:
                if is_expr:
                    self._analyze_expr(part, env)
        elif isinstance(e, TernaryExpr):
            self._analyze_expr(e.cond, env)
            self._analyze_expr(e.if_true, env)
            self._analyze_expr(e.if_false, env)

    # ------------------------------------------------------------------
    # inference
    # ------------------------------------------------------------------
    def _infer(self, e: Expr, env: Dict[str, Type]) -> Optional[Type]:
        if isinstance(e, ConstExpr):
            if isinstance(e.value, bool):
                return BOOL
            if isinstance(e.value, int):
                return INT
            if isinstance(e.value, float):
                return FLOAT
            if isinstance(e.value, str):
                return STRING
            return None
        if isinstance(e, NameExpr):
            return env.get(e.name)
        if isinstance(e, BinOpExpr):
            l, r = self._infer(e.left, env), self._infer(e.right, env)
            if e.op == "+" and (l is STRING or r is STRING):
                return STRING
            if e.op == "/":
                return FLOAT
            if e.op == "//":
                return INT
            if e.op == "%":
                return FLOAT if (l is FLOAT or r is FLOAT) else INT
            if l is FLOAT or r is FLOAT:
                return FLOAT
            return l or r
        if isinstance(e, (CompareExpr, BoolOpExpr)):
            return BOOL
        if isinstance(e, UnaryOpExpr):
            if e.op == "not":
                return BOOL
            return self._infer(e.operand, env)
        if isinstance(e, CallExpr) and isinstance(e.func, NameExpr):
            name = e.func.name
            if name == "range":
                return ArrayType(INT)
            if name in _RETURN_OF_BUILTIN:
                return _RETURN_OF_BUILTIN[name]
            if name in self.fn_returns:
                return self.fn_returns[name]
            return None
        if isinstance(e, SubscriptExpr):
            base = self._infer(e.value, env)
            if isinstance(base, ArrayType):
                return base.elem
            if isinstance(base, MapType):
                return base.v
            if base is STRING:
                return STRING
            return None
        if isinstance(e, ListExpr):
            elem = self._infer(e.items[0], env) if e.items else None
            return ArrayType(elem or ErrorType(fallback="float"))
        if isinstance(e, DictExpr):
            k = self._infer(e.items[0][0], env) if e.items else None
            v = self._infer(e.items[0][1], env) if e.items else None
            return MapType(k or ErrorType(fallback="float"),
                           v or ErrorType(fallback="float"))
        if isinstance(e, JoinedStrExpr):
            return STRING
        if isinstance(e, TernaryExpr):
            return self._infer(e.if_true, env)
        return None


def _attr_target(stmt: Stmt):
    """Return (attr_name, value_expr) if stmt assigns to `self.<name>`."""
    if isinstance(stmt, (AssignStmt, AugAssignStmt)):
        if isinstance(stmt.target, AttributeExpr) \
                and isinstance(stmt.target.value, NameExpr) \
                and stmt.target.value.name == "this":
            return stmt.target.attr, stmt.value
    if isinstance(stmt, AnnAssignStmt):
        if isinstance(stmt.target, AttributeExpr) \
                and isinstance(stmt.target.value, NameExpr) \
                and stmt.target.value.name == "this":
            return stmt.target.attr, stmt.value
    return None


def _child_stmts(stmt: Stmt):
    if isinstance(stmt, (AssignStmt, AugAssignStmt, AnnAssignStmt,
                         ExprStmt, ReturnStmt)):
        return []
    if isinstance(stmt, IfStmt):
        out = []
        for _, body in stmt.branches:
            out.extend(body)
        out.extend(stmt.orelse)
        return out
    if isinstance(stmt, (WhileStmt, RangeForStmt, ForStmt)):
        return stmt.body
    return []
