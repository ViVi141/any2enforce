"""Language-neutral intermediate representation (IR) for any2enforce.

Frontends (Python ast, later tree-sitter grammars) produce IR.Module trees.
Backends (EnforceScript emitter) consume them. No EnforceScript-specific
decisions live in the frontends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


# --------------------------------------------------------------------------
# Source spans
# --------------------------------------------------------------------------

@dataclass
class Span:
    file: str = "<unknown>"
    line: int = 0
    col: int = 0


@dataclass(kw_only=True)
class Node:
    """All IR nodes carry a source span. kw_only keeps leaf constructors
    positional-first while allowing `span=` as a keyword."""
    span: Optional[Span] = None


# --------------------------------------------------------------------------
# Types (IR-level; rendered by backends)
# --------------------------------------------------------------------------

class Type:
    def render(self) -> str:
        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.render()}>"


@dataclass
class ScalarType(Type):
    name: str  # int | float | bool | string

    def render(self) -> str:
        return self.name


@dataclass
class ArrayType(Type):
    elem: Type

    def render(self) -> str:
        return f"array<{self.elem.render()}>"


@dataclass
class MapType(Type):
    k: Type
    v: Type

    def render(self) -> str:
        return f"map<{self.k.render()}, {self.v.render()}>"


@dataclass
class SetType(Type):
    elem: Type

    def render(self) -> str:
        return f"set<{self.elem.render()}>"


@dataclass
class ClassType(Type):
    """User class reference. EnforceScript requires `ref` for class-typed
    declarations / generic arguments (verified against Reforger scripts:
    `ref SCR_TimerEntryBase`, `array<ref SampleObject>`)."""
    name: str

    def render(self) -> str:
        return f"ref {self.name}"


@dataclass
class AutoType(Type):
    """Compiler-inferred local (`auto` in EnforceScript)."""

    def render(self) -> str:
        return "auto"


@dataclass
class VoidType(Type):
    def render(self) -> str:
        return "void"


@dataclass
class ErrorType(Type):
    """No faithful mapping exists. Always paired with an error diagnostic."""

    fallback: str = "float"

    def render(self) -> str:
        return self.fallback


VOID = VoidType()
AUTO = AutoType()
INT = ScalarType("int")
FLOAT = ScalarType("float")
BOOL = ScalarType("bool")
STRING = ScalarType("string")


# --------------------------------------------------------------------------
# Expressions
# --------------------------------------------------------------------------

@dataclass(kw_only=True)
class Expr(Node):
    pass


@dataclass
class NameExpr(Expr):
    name: str


@dataclass
class ConstExpr(Expr):
    value: Union[str, int, float, bool, None]


@dataclass
class BinOpExpr(Expr):
    """op in {+, -, *, /, //, %, **}"""
    op: str
    left: Expr
    right: Expr


@dataclass
class BoolOpExpr(Expr):
    """op in {and, or}"""
    op: str
    values: List[Expr]


@dataclass
class CompareExpr(Expr):
    """Python chained comparison: left op1 mid op2 right ..."""
    left: Expr
    ops: List[str]  # == != < <= > >= is
    comparators: List[Expr]


@dataclass
class UnaryOpExpr(Expr):
    """op in {- (neg), not}"""
    op: str
    operand: Expr


@dataclass
class CallExpr(Expr):
    func: Expr  # NameExpr or AttributeExpr
    args: List[Expr]
    kwargs: List["KwArg"] = field(default_factory=list)


@dataclass
class KwArg(Node):
    name: str
    value: Expr


@dataclass
class AttributeExpr(Expr):
    value: Expr
    attr: str


@dataclass
class SubscriptExpr(Expr):
    value: Expr
    index: Expr


@dataclass
class ListExpr(Expr):
    items: List[Expr]


@dataclass
class DictExpr(Expr):
    items: List[tuple]  # (key_expr, value_expr)


@dataclass
class JoinedStrExpr(Expr):
    """f-string: parts are either plain str literals or (is_expr=True, node)."""
    parts: List[tuple]


@dataclass
class TernaryExpr(Expr):
    cond: Expr
    if_true: Expr
    if_false: Expr


@dataclass
class UnsupportedExpr(Expr):
    """Rendered as a marked 0 placeholder; always paired with an error diagnostic."""
    reason: str


# --------------------------------------------------------------------------
# Statements
# --------------------------------------------------------------------------

@dataclass(kw_only=True)
class Stmt(Node):
    pass


@dataclass
class AssignStmt(Stmt):
    target: Expr  # NameExpr | AttributeExpr
    value: Expr


@dataclass
class AnnAssignStmt(Stmt):
    target: Expr  # NameExpr | AttributeExpr
    type_ann: Optional[str]   # raw annotation text, resolved by sema
    type: Optional[Type] = None
    value: Optional[Expr] = None


@dataclass
class AugAssignStmt(Stmt):
    target: Expr
    op: str
    value: Expr


@dataclass
class ExprStmt(Stmt):
    expr: Expr


@dataclass
class ReturnStmt(Stmt):
    value: Optional[Expr] = None


@dataclass
class IfStmt(Stmt):
    branches: List[tuple]  # [(cond: Expr, body: List[Stmt]), ...]
    orelse: List[Stmt]


@dataclass
class WhileStmt(Stmt):
    cond: Expr
    body: List[Stmt]


@dataclass
class RangeForStmt(Stmt):
    """for i in range(lo, hi[, step]) -> counter loop"""
    target: NameExpr
    lo: Expr
    hi: Expr
    step: Optional[Expr]
    body: List[Stmt]


@dataclass
class ForStmt(Stmt):
    """for x in iterable -> foreach. elem_type resolved by sema."""
    target: NameExpr
    iterable: Expr
    body: List[Stmt]
    elem_type: Optional[Type] = None


@dataclass
class BreakStmt(Stmt):
    pass


@dataclass
class ContinueStmt(Stmt):
    pass


@dataclass
class PassStmt(Stmt):
    pass


@dataclass
class ImportStmt(Stmt):
    module: str
    names: List[str] = field(default_factory=list)


@dataclass
class UnsupportedStmt(Stmt):
    """Emitted as a comment marker; always paired with a diagnostic."""
    reason: str
    source_text: str = ""
    level: str = "error"  # error | warning | info


# --------------------------------------------------------------------------
# Declarations
# --------------------------------------------------------------------------

@dataclass
class Param(Node):
    name: str
    type_ann: Optional[str]
    type: Optional[Type] = None
    default: Optional[ConstExpr] = None


@dataclass
class Field(Node):
    name: str
    type: Type
    default: Optional[ConstExpr] = None  # None -> type default (0 / "" / null)


@dataclass
class MethodDef(Node):
    name: str
    params: List[Param]
    return_ann: Optional[str]
    return_type: Optional[Type] = None
    body: List[Stmt] = field(default_factory=list)
    is_static: bool = False
    is_constructor: bool = False
    visibility: str = "protected"
    doc: Optional[str] = None
    todos: List[str] = field(default_factory=list)


@dataclass
class ClassDef(Node):
    name: str
    bases: List[str]
    fields: List[Field] = field(default_factory=list)
    methods: List[MethodDef] = field(default_factory=list)
    doc: Optional[str] = None
    todos: List[str] = field(default_factory=list)


@dataclass
class FunctionDef(Node):
    name: str
    params: List[Param]
    return_ann: Optional[str]
    return_type: Optional[Type] = None
    body: List[Stmt] = field(default_factory=list)
    doc: Optional[str] = None
    todos: List[str] = field(default_factory=list)


@dataclass
class Module(Node):
    name: str  # source stem
    doc: Optional[str] = None
    imports: List[ImportStmt] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    globals: List[Stmt] = field(default_factory=list)  # module-level executable stmts (v0.1: markers only)
