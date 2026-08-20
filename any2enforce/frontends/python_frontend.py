"""Python frontend: stdlib `ast` -> IR.

Structure-only. Annotation strings are kept raw and resolved by the sema pass.
Anything that cannot be represented faithfully produces an Unsupported node
plus an error diagnostic — never silent guessing.
"""

from __future__ import annotations

import ast
from typing import List, Optional

from ..diagnostics import DiagnosticSink
from ..ir import (
    AnnAssignStmt, AssignStmt, AttributeExpr, AugAssignStmt, BinOpExpr,
    BoolOpExpr, BreakStmt, CallExpr, ClassDef, CompClause, CompareExpr,
    ConstExpr, ContinueStmt, DictCompExpr, DictExpr, Expr, ExprStmt, ForStmt,
    FunctionDef, IfStmt, ImportStmt, JoinedStrExpr, KwArg, ListCompExpr,
    ListExpr, MethodDef, Module, NameExpr, Node, Param, PassStmt, RangeForStmt,
    ReturnStmt, SetCompExpr, Span, Stmt, SubscriptExpr, TernaryExpr,
    UnaryOpExpr, UnsupportedExpr, UnsupportedStmt, WhileStmt,
)

_BIN_OPS = {
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
    ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
}
_CMP_OPS = {
    ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
    ast.Gt: ">", ast.GtE: ">=", ast.Is: "is", ast.IsNot: "is not",
    ast.In: "in", ast.NotIn: "not in",
}

# (ast node type, feature name)
_UNSUPPORTED_STMTS = [
    (ast.Try, "try/except"),
    (ast.With, "with statement"),
    (ast.Global, "global"),
    (ast.Nonlocal, "nonlocal"),
    (ast.Delete, "del statement"),
    (ast.Raise, "raise"),
    (ast.Assert, "assert"),
]
_UNSUPPORTED_EXPRS = [
    (ast.Lambda, "lambda/closures"),
    (ast.GeneratorExp, "generator expression"),
    (ast.Starred, "*args unpacking"),
]


class PythonFrontend:
    def __init__(self, diagnostics: DiagnosticSink) -> None:
        self.diag = diagnostics
        self.source = ""
        self.filename = "<string>"

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------
    def parse(self, source: str, filename: str = "<string>") -> Module:
        self.source = source
        self.filename = filename
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            self.diag.error(
                "syntax-error",
                f"Python syntax error: {exc.msg}",
                Span(filename, exc.lineno or 0, exc.offset or 0),
            )
            return Module(name="<error>")
        mod = Module(name=filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
        if filename.endswith(".py"):
            mod.name = mod.name[:-3]
        doc, body = self._split_docstring(tree.body)
        mod.doc = doc
        for node in body:
            self._module_stmt(mod, node)
        return mod

    # ------------------------------------------------------------------
    # Module level
    # ------------------------------------------------------------------
    def _module_stmt(self, mod: Module, node: ast.stmt) -> None:
        if isinstance(node, ast.FunctionDef):
            mod.functions.append(self._function(node))
        elif isinstance(node, ast.ClassDef):
            mod.classes.append(self._class(node))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mod.imports.append(self._import(node))
        elif isinstance(node, ast.AsyncFunctionDef):
            self._unsupported_stmt("async function")
        else:
            stmt = self._stmt(node)
            if stmt is not None:
                self.diag.warning(
                    "module-level-stmt",
                    "module-level executable statements are not emitted in v0.1 "
                    "(planned: Init() wrapper)",
                    self._span(node),
                )
                mod.globals.append(UnsupportedStmt(
                    "module-level statement",
                    ast.get_source_segment(self.source, node) or "",
                    span=self._span(node), level="warning",
                ))

    # ------------------------------------------------------------------
    # Functions / classes
    # ------------------------------------------------------------------
    def _function(self, node: ast.FunctionDef) -> FunctionDef:
        span = self._span(node)
        params, _, todos = self._params(node.args)
        fn = FunctionDef(
            name=node.name,
            params=params,
            return_ann=_unparse(node.returns),
            body=[],
            todos=todos,
            span=span,
        )
        doc, body = self._split_docstring(node.body)
        fn.doc = doc
        for d in node.decorator_list:
            self.diag.warning(
                "function-decorator",
                f"decorator on function '{node.name}' is ignored in v0.1",
                self._span(d), note="decorators must be expanded manually",
            )
        fn.body = self._body(body)
        return fn

    def _class(self, node: ast.ClassDef) -> ClassDef:
        span = self._span(node)
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(b.attr)
            else:
                self.diag.error(
                    "unsupported-base", "unsupported base expression",
                    self._span(b),
                )
        cls = ClassDef(name=node.name, bases=bases, span=span)
        doc, body = self._split_docstring(node.body)
        cls.doc = doc
        for item in body:
            if isinstance(item, ast.FunctionDef):
                cls.methods.append(self._method(item, cls.name))
            elif isinstance(item, ast.AsyncFunctionDef):
                self._unsupported_stmt("async method")
            elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                # class-level assignment -> static field (v0.2); v0.1 note
                self.diag.warning(
                    "class-attribute",
                    f"class attribute '{_target_name(item)}' -> static field (v0.2)",
                    self._span(item),
                    note="emitted as comment in v0.1",
                )
            else:
                self.diag.error(
                    "class-body-stmt",
                    "unsupported statement in class body",
                    self._span(item),
                )
        return cls

    def _method(self, node: ast.FunctionDef, cls_name: str) -> MethodDef:
        span = self._span(node)
        is_ctor = node.name == "__init__"
        is_static = False
        for d in node.decorator_list:
            if isinstance(d, ast.Name):
                if d.id == "staticmethod":
                    is_static = True
                elif d.id == "classmethod":
                    self.diag.error(
                        "classmethod",
                        "classmethod is not supported in v0.1",
                        self._span(d),
                    )
                elif d.id == "property":
                    self.diag.warning(
                        "property",
                        "@property -> getter/setter methods (v0.2); emitted as plain method",
                        self._span(d),
                    )
                else:
                    self.diag.warning(
                        "method-decorator",
                        f"decorator '@{d.id}' on method '{node.name}' ignored in v0.1",
                        self._span(d),
                    )
            else:
                self.diag.warning(
                    "method-decorator", "non-name decorator ignored in v0.1",
                    self._span(d),
                )
        params, _, todos = self._params(node.args, method=True)  # `self` stripped
        method = MethodDef(
            name=node.name,
            params=params,
            return_ann=_unparse(node.returns),
            body=[],
            is_static=is_static,
            is_constructor=is_ctor,
            todos=todos,
            span=span,
        )
        doc, body = self._split_docstring(node.body)
        method.doc = doc
        method.body = self._body(body)
        return method

    def _params(self, args: ast.arguments, method: bool = False):
        params: List[Param] = []
        has_self = False
        todos: List[str] = []
        positional = list(args.posonlyargs) + list(args.args)
        if method and positional and positional[0].arg == "self":
            has_self = True
            positional = positional[1:]
        defaults = list(args.defaults)
        n_defaults = len(defaults)
        offset = len(positional) - n_defaults
        for i, arg in enumerate(positional):
            default = None
            if i >= offset:
                dnode = defaults[i - offset]
                if isinstance(dnode, ast.Constant):
                    default = ConstExpr(dnode.value, span=self._span(dnode))
                else:
                    self.diag.error(
                        "param-default",
                        f"non-constant default for parameter '{arg.arg}'",
                        self._span(dnode),
                    )
            params.append(Param(
                name=arg.arg,
                type_ann=_unparse(arg.annotation),
                default=default,
                span=self._span(arg),
            ))
        if args.vararg:
            self.diag.error(
                "varargs", f"*{args.vararg.arg} is not supported in v0.1",
                self._span(args.vararg),
            )
            todos.append(f"varargs:*{args.vararg.arg}")
        if args.kwarg:
            self.diag.error(
                "kwargs", f"**{args.kwarg.arg} is not supported in v0.1",
                self._span(args.kwarg),
            )
            todos.append(f"kwargs:**{args.kwarg.arg}")
        if args.kwonlyargs:
            self.diag.error(
                "kwonly", "keyword-only arguments are not supported in v0.1",
                self._span(args.kwonlyargs[0]),
            )
            todos.append("kwonly-args")
        return params, has_self, todos

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------
    def _body(self, body: List[ast.stmt]) -> List[Stmt]:
        out: List[Stmt] = []
        for node in body:
            stmt = self._stmt(node)
            if stmt is not None:
                out.append(stmt)
        return out

    def _stmt(self, node: ast.stmt) -> Optional[Stmt]:
        span = self._span(node)

        if isinstance(node, ast.FunctionDef):
            self.diag.error(
                "unsupported-nested-function",
                "nested functions (closures) are not supported in v0.1",
                span,
            )
            return UnsupportedStmt(
                "nested function", self._src(node), span=span)

        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            return None  # docstring / standalone string -> comment

        if isinstance(node, ast.Expr):
            if _is_super_init(node.value):
                # settled: EnforceScript has no explicit base-ctor call syntax;
                # ctor params are implicitly forwarded by name (verified
                # SCR_TimerEntries.c + probes P01/P02). sema checks that the
                # derived ctor declares the base's required params.
                self.diag.warning(
                    "super-init-dropped",
                    "super().__init__(...) is dropped: the base ctor is called "
                    "implicitly by EnforceScript (verified)",
                    span,
                    note="ensure the derived ctor declares the base ctor's "
                         "required parameters (sema check 'ctor-forward')",
                )
                return UnsupportedStmt(
                    "super().__init__() dropped (implicit base ctor, verified)",
                    level="warning", span=span)
            expr = self._expr(node.value)
            return ExprStmt(expr, span=span)

        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                self.diag.error(
                    "multi-target-assign",
                    "chained / tuple assignments are not supported in v0.1",
                    span,
                )
                return UnsupportedStmt("multi-target assignment", self._src(node), span=span)
            target = self._target(node.targets[0])
            if target is None:
                return UnsupportedStmt("unsupported assignment target", self._src(node), span=span)
            return AssignStmt(target, self._expr(node.value), span=span)

        if isinstance(node, ast.AnnAssign):
            target = self._target(node.target)
            if target is None:
                return UnsupportedStmt("unsupported annotated target", self._src(node), span=span)
            value = self._expr(node.value) if node.value is not None else None
            return AnnAssignStmt(
                target, _unparse(node.annotation), value=value, span=span)

        if isinstance(node, ast.AugAssign):
            target = self._target(node.target)
            if target is None:
                return UnsupportedStmt("unsupported augmented target", self._src(node), span=span)
            return AugAssignStmt(
                target, _BIN_OPS.get(type(node.op), "?"), self._expr(node.value), span=span)

        if isinstance(node, ast.Return):
            value = self._expr(node.value) if node.value is not None else None
            return ReturnStmt(value, span=span)

        if isinstance(node, ast.If):
            return self._if(node)

        if isinstance(node, ast.While):
            return WhileStmt(self._expr(node.test), self._body(node.body), span=span)

        if isinstance(node, ast.For):
            return self._for(node)

        if isinstance(node, ast.Break):
            return BreakStmt(span=span)
        if isinstance(node, ast.Continue):
            return ContinueStmt(span=span)
        if isinstance(node, ast.Pass):
            return PassStmt(span=span)

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return self._import(node)

        for t, name in _UNSUPPORTED_STMTS:
            if isinstance(node, t):
                return self._unsupported_stmt(name, span, node)

        self.diag.error("unknown-stmt", f"unhandled statement {type(node).__name__}", span)
        return UnsupportedStmt(f"unhandled {type(node).__name__}", self._src(node), span=span)

    def _if(self, node: ast.If) -> IfStmt:
        # module entry guard: if __name__ == "__main__": ...
        if _is_entry_guard(node.test):
            self.diag.warning(
                "entry-guard",
                "module entry guard `if __name__ == \"__main__\":` is not mapped "
                "in v0.1; wrap the body in an addon init function",
                self._span(node),
            )
            return UnsupportedStmt(
                "module entry guard", self._src(node), span=self._span(node))
        branches = [(self._expr(node.test), self._body(node.body))]
        orelse: List[Stmt] = []
        cur = node.orelse
        while cur and len(cur) == 1 and isinstance(cur[0], ast.If):
            branches.append((self._expr(cur[0].test), self._body(cur[0].body)))
            cur = cur[0].orelse
        if cur:
            orelse = self._body(cur)
        return IfStmt(branches, orelse, span=self._span(node))

    def _for(self, node: ast.For) -> Stmt:
        span = self._span(node)
        if len(node.target.elts) if isinstance(node.target, ast.Tuple) else False:
            self.diag.error("tuple-unpack-for", "tuple unpacking in for is unsupported", span)
        target = NameExpr(node.target.id, span=span) \
            if isinstance(node.target, ast.Name) else NameExpr("_", span=span)
        body = self._body(node.body)
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) \
                and node.iter.func.id == "range":
            args = [self._expr(a) for a in node.iter.args]
            if len(args) == 1:
                lo, hi, step = ConstExpr(0, span=span), args[0], None
            elif len(args) == 2:
                lo, hi, step = args[0], args[1], None
            elif len(args) == 3:
                lo, hi, step = args[0], args[1], args[2]
            else:
                self.diag.error("range-args", "range() needs 1..3 arguments", span)
                return UnsupportedStmt("range() arity", self._src(node), span=span)
            return RangeForStmt(target, lo, hi, step, body, span=span)
        iterable = self._expr(node.iter)
        return ForStmt(target, iterable, body, span=span)

    def _import(self, node: ast.stmt) -> ImportStmt:
        if isinstance(node, ast.Import):
            return ImportStmt(node.names[0].name,
                              [a.asname or a.name for a in node.names],
                              span=self._span(node))
        module = node.module or ""
        return ImportStmt(module,
                          [a.asname or a.name for a in node.names],
                          span=self._span(node))

    def _target(self, node: ast.expr) -> Optional[Expr]:
        if isinstance(node, ast.Name):
            return NameExpr(node.id, span=self._span(node))
        if isinstance(node, ast.Attribute):
            value = self._expr(node.value)
            return AttributeExpr(value, node.attr, span=self._span(node))
        if isinstance(node, ast.Subscript):
            # map subscript write (verified: `m_mSettings[k] = v;`)
            return SubscriptExpr(self._expr(node.value), self._expr(node.slice),
                                 span=self._span(node))
        self.diag.error(
            "assign-target", f"unsupported assignment target {type(node).__name__}",
            self._span(node),
        )
        return None

    def _unsupported_stmt(self, feature: str, span: Optional[Span] = None,
                          node: Optional[ast.AST] = None) -> UnsupportedStmt:
        self.diag.error(
            f"unsupported-{feature.replace('/', '-').replace(' ', '-')}",
            f"{feature} is not supported in v0.1",
            span or (self._span(node) if node else None),
            note="rewrite manually or wait for a later roadmap version",
        )
        return UnsupportedStmt(feature, self._src(node) if node else "", span=span)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------
    def _expr(self, node: ast.expr) -> Node:
        span = self._span(node)

        if isinstance(node, ast.Name):
            name = "this" if node.id == "self" else node.id
            return NameExpr(name, span=span)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool)) or node.value is None:
                return ConstExpr(node.value, span=span)
            self.diag.error("const-type", f"unsupported constant {type(node.value).__name__}", span)
            return UnsupportedExpr("unsupported constant", span=span)

        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                self.diag.error("binop", f"unsupported operator {type(node.op).__name__}", span)
                return UnsupportedExpr("unsupported binary operator", span=span)
            return BinOpExpr(op, self._expr(node.left), self._expr(node.right), span=span)

        if isinstance(node, ast.BoolOp):
            op = "and" if isinstance(node.op, ast.And) else "or"
            return BoolOpExpr(op, [self._expr(v) for v in node.values], span=span)

        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                operand = self._expr(node.operand)
                if isinstance(operand, ConstExpr) \
                        and isinstance(operand.value, (int, float)):
                    return ConstExpr(-operand.value, span=span)
                return UnaryOpExpr("-", operand, span=span)
            if isinstance(node.op, ast.UAdd):
                return self._expr(node.operand)
            if isinstance(node.op, ast.Not):
                return UnaryOpExpr("not", self._expr(node.operand), span=span)
            self.diag.error("unop", f"unsupported unary operator {type(node.op).__name__}", span)
            return UnsupportedExpr("unsupported unary operator", span=span)

        if isinstance(node, ast.Compare):
            ops = []
            for op in node.ops:
                mapped = _CMP_OPS.get(type(op))
                if mapped is None:
                    self.diag.error("cmpop", f"unsupported comparison {type(op).__name__}", span)
                    mapped = "=="
                ops.append(mapped)
            return CompareExpr(
                self._expr(node.left), ops,
                [self._expr(c) for c in node.comparators], span=span)

        if isinstance(node, ast.Call):
            # super() is allowed here only as the base of super().attr /
            # super().method(); a truly bare super() is rejected by the backend.
            func = self._expr(node.func)
            args = [self._expr(a) for a in node.args]
            kwargs = []
            for kw in node.keywords:
                if kw.arg is None:
                    self.diag.error("kwargs", "**kwargs expansion is unsupported in v0.1", span)
                    continue
                kwargs.append(KwArg(kw.arg, self._expr(kw.value), span=span))
            return CallExpr(func, args, kwargs, span=span)

        if isinstance(node, ast.Attribute):
            return AttributeExpr(self._expr(node.value), node.attr, span=span)

        if isinstance(node, ast.Subscript):
            return SubscriptExpr(self._expr(node.value), self._expr(node.slice), span=span)

        if isinstance(node, ast.List):
            return ListExpr([self._expr(i) for i in node.elts], span=span)

        if isinstance(node, ast.Tuple):
            self.diag.error(
                "tuple", "tuple literals are not supported in v0.1 (use list or a class)",
                span,
            )
            return UnsupportedExpr("tuple literal", span=span)

        if isinstance(node, ast.Dict):
            items = []
            for k, v in zip(node.keys, node.values):
                if k is None:
                    self.diag.error("dict-unpack", "**dict unpacking is unsupported", span)
                    continue
                items.append((self._expr(k), self._expr(v)))
            return DictExpr(items, span=span)

        if isinstance(node, ast.JoinedStr):
            parts = []
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append((False, value.value))
                elif isinstance(value, ast.FormattedValue):
                    parts.append((True, self._expr(value.value)))
                    if value.format_spec is not None:
                        self.diag.warning(
                            "fstring-fmt-spec",
                            "f-string format specs are approximated in v0.1",
                            span,
                        )
                else:
                    self.diag.error("fstring", "unsupported f-string component", span)
            return JoinedStrExpr(parts, span=span)

        if isinstance(node, ast.IfExp):
            return TernaryExpr(
                self._expr(node.test),
                self._expr(node.body),
                self._expr(node.orelse),
                span=span,
            )

        if isinstance(node, ast.ListComp):
            return self._list_comp(node)

        if isinstance(node, ast.DictComp):
            return self._dict_comp(node)

        if isinstance(node, ast.SetComp):
            return self._set_comp(node)

        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            self.diag.error(
                "unsupported-yield",
                "generators (yield) are not supported in v0.1",
                span,
                note="rewrite as an explicit loop building an array, or use callbacks",
            )
            return UnsupportedExpr("generator (yield)", span=span)

        for t, name in _UNSUPPORTED_EXPRS:
            if isinstance(node, t):
                code = "unsupported-" + name.replace(" ", "-").replace("/", "-")
                self.diag.error(
                    code,
                    f"{name} is not supported in v0.1",
                    span,
                    note="rewrite manually or wait for a later roadmap version",
                )
                return UnsupportedExpr(name, span=span)

        self.diag.error("unknown-expr", f"unhandled expression {type(node).__name__}", span)
        return UnsupportedExpr(f"unhandled {type(node).__name__}", span=span)

    def _list_comp(self, node: ast.ListComp) -> Expr:
        span = self._span(node)
        clauses = self._comp_clauses(node.generators, span)
        if clauses is None:
            return UnsupportedExpr("list comprehension (bad generator)", span=span)
        return ListCompExpr(self._expr(node.elt), clauses, span=span)

    def _dict_comp(self, node: ast.DictComp) -> Expr:
        span = self._span(node)
        clauses = self._comp_clauses(node.generators, span)
        if clauses is None:
            return UnsupportedExpr("dict comprehension (bad generator)", span=span)
        return DictCompExpr(
            self._expr(node.key), self._expr(node.value), clauses, span=span)

    def _set_comp(self, node: ast.SetComp) -> Expr:
        span = self._span(node)
        clauses = self._comp_clauses(node.generators, span)
        if clauses is None:
            return UnsupportedExpr("set comprehension (bad generator)", span=span)
        return SetCompExpr(self._expr(node.elt), clauses, span=span)

    def _comp_clauses(self, generators, span: Span):
        """Parse comprehension generators into CompClause list.

        Returns None when a generator cannot be represented (tuple unpack /
        async for) — caller emits UnsupportedExpr.
        """
        clauses = []
        for gen in generators:
            if getattr(gen, "is_async", False):
                self.diag.error(
                    "comp-async",
                    "async for in comprehensions is not supported",
                    self._span(gen),
                )
                return None
            if not isinstance(gen.target, ast.Name):
                self.diag.error(
                    "comp-unpack",
                    "tuple/star unpacking in comprehension targets is not supported",
                    self._span(gen.target),
                    note="use a single name, e.g. `for x in items`",
                )
                return None
            target = NameExpr(gen.target.id, span=self._span(gen.target))
            ifs = [self._expr(i) for i in gen.ifs]
            it = gen.iter
            if (isinstance(it, ast.Call)
                    and isinstance(it.func, ast.Name)
                    and it.func.id == "range"):
                args = [self._expr(a) for a in it.args]
                if len(args) == 1:
                    lo, hi, step = ConstExpr(0, span=span), args[0], None
                elif len(args) == 2:
                    lo, hi, step = args[0], args[1], None
                elif len(args) == 3:
                    lo, hi, step = args[0], args[1], args[2]
                else:
                    self.diag.error(
                        "range-args",
                        "range() needs 1..3 arguments",
                        self._span(it),
                    )
                    return None
                clauses.append(CompClause(
                    target, ifs=ifs, is_range=True, lo=lo, hi=hi, step=step,
                    span=self._span(gen),
                ))
            else:
                clauses.append(CompClause(
                    target, ifs=ifs, iterable=self._expr(it),
                    span=self._span(gen),
                ))
        return clauses

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _span(self, node: ast.AST) -> Span:
        return Span(self.filename, getattr(node, "lineno", 0), getattr(node, "col_offset", 0))

    def _src(self, node: Optional[ast.AST]) -> str:
        if node is None:
            return ""
        try:
            return ast.get_source_segment(self.source, node) or ""
        except Exception:
            return ""

    @staticmethod
    def _split_docstring(body: List[ast.stmt]):
        if body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            return body[0].value.value, body[1:]
        return None, body


def _unparse(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _target_name(node: ast.stmt) -> str:
    t = getattr(node, "targets", None) or getattr(node, "target", None)
    if isinstance(t, list):
        t = t[0] if t else None
    if isinstance(t, ast.Name):
        return t.id
    if isinstance(t, ast.Attribute):
        return t.attr
    return "?"


def _is_entry_guard(test: ast.expr) -> bool:
    return (isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__")


def _is_super_init(node: ast.expr) -> bool:
    """True for `super().__init__(...)`."""
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "__init__"
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "super")
