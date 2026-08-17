# any2enforce

把常用编程语言自动转换为 **EnforceScript**（Arma Reforger / Enfusion 引擎脚本语言）的转换工具。
当前版本（v0.1）实现 **Python → EnforceScript** 前端；架构为多语言预留（Java / C# / TypeScript）。

> 完整设计见 [`docs/DESIGN.md`](docs/DESIGN.md)；EnforceScript 语法细节的待实测清单见
> [`docs/VERIFY.md`](docs/VERIFY.md)。

## 快速开始

```bash
pip install -e .          # 安装 CLI（Python >= 3.11）

# 单文件
any2enforce examples/demo.py --out build/demo.c

# 目录批量
any2enforce src/ --out build/

# EnforceScript 命名惯例（方法/类 PascalCase，字段 m_ 前缀）
any2enforce examples/demo.py --out build/demo.c --naming camel --field-prefix m_

# 生成后自动部署到 addon 并用 Workbench ValidateScripts 编译验证
any2enforce examples/demo.py --out build/demo.c \
    --validate --addon-path ../MyAddon --workbench-url http://127.0.0.1:12345

# CI：有 error 诊断即非零退出
any2enforce src/ --out build/ --fail-on-error
```

无 Workbench 时 `--validate` 自动降级为提示（不阻塞生成）。

## 语料校准（重要）

v0.1 已用 **6568 个真实 Reforger `.c` 文件**（`_reforger_code_full_v2/scripts`）校准语法映射，
逐条证据见 [`docs/VERIFY.md`](docs/VERIFY.md)。关键定案：

- ❌ EnforceScript **没有三元运算符** → `a if c else b` 自动展开为 `T x = b; if (c) { x = a; }`
- `f"..."` / `"..." % x` → **`string.Format("...%1...", ...)`**（裸 `format()` 不存在）
- `print(x)` → `Print(x)`（接受任意类型）；`print(a, b)` → `PrintFormat("%1 %2", a, b)`
- 数组字面量 → `array<T> x = { ... };`；dict → `new map<K,V>()` + `x[k] = v;`（map 支持 `[]` 读写）
- `abs/min/max` 按类型分派 `Math.AbsInt/AbsFloat/MinInt/MaxInt/Min/Max`（`Math.Abs` 不存在）
- 参数默认值直接映射（`def f(x: int = 3)` → `int x = 3`）；类类型自动加 `ref`；字段裸访问 `m_x`

## 流水线

```
Python 源码 ─▶ PythonFrontend（stdlib ast）─▶ IR ─▶ Analyzer（类型解析/字段上提）
             ─▶ EnforceBackend（生成 .c）─▶ [Workbench ValidateScripts 校验闭环]
```

设计铁律：**转换成功 = 语义可信**。无法 1:1 映射的构造一律产出分级诊断
（error/warning/info）并在输出中留下 `[any2enforce:error]` / `TODO[...]` 标记，绝不静默生成错误代码。

## v0.1 支持范围（Python 子集）

| 支持 | 说明 |
|---|---|
| 模块级函数、类（单继承）、静态方法 | `__init__` → 构造函数；`self.x = v` → 字段上提（`m_` 前缀） |
| 类型注解映射 | `int/float/bool/str`、`list[T]→array<T>`、`dict[K,V]→map<K,V>`、`set[T]→set<T>`、`Optional`、用户类 |
| 控制流 | `if/elif/else`、`while`、`for i in range(...)`（含负步进）、`for x in list → foreach`、`break/continue`、三元 → if/else 展开 |
| 表达式 | 算术/比较/逻辑（`and→&&`）、`f"..."`/`%` → `string.Format`、`len()`、`print→Print/PrintFormat`、`min/max/abs` 类型分派、列表/字典字面量、map `[]` 读写 |
| 默认参数 | `def f(x: int = 3)` → `int x = 3`（实测合法） |
| 无注解局部变量 | 自动输出 `auto`（实测合法） |

| 不支持（v0.1，报错并留标记） | 说明 |
|---|---|
| `try/except`、`with`、`global/nonlocal`、`del`、`raise`、`assert` | 建议改写为返回值/错误码模式 |
| `lambda`/闭包、嵌套函数、生成器 `yield` | 后续版本用回调/`ScriptCaller` |
| `*args`/`**kwargs`、关键字实参 | 显式参数 |
| 推导式、`tuple`、多继承、`@property`、装饰器（白名单外） | 手动展开或等 v0.2 |

## 目录结构

```
any2enforce/
  docs/DESIGN.md            # 完整设计文档（架构/映射表/路线图）
  docs/VERIFY.md            # EnforceScript ⚠ 语法待实测清单
  any2enforce/
    frontends/python_frontend.py   # ast → IR
    sema/analyze.py + types.py     # 类型解析、字段上提、foreach 元素类型
    backends/enforce.py            # IR → EnforceScript 文本
    validate/workbench.py          # 部署 + ValidateScripts 校验闭环
    cli.py                         # CLI 编排
  tests/                     # 金样测试 + 负向用例 + 类型解析单测（pytest）
  examples/demo.py + demo.c  # 示例
```

## 测试

```bash
python -m pytest -q
```

金样测试（`tests/golden/`）保证输出逐字节稳定；负向用例保证每个不支持特性都产生诊断而非静默通过。

## 路线图

- **v0.2**：推导式自动展开、模块级初始化 → `Init()`、`@property`、回调、VERIFY.md ⚠ 项实测修正、`--report json` CI 集成
- **v0.3**：tree-sitter 前端框架 + TypeScript/Java 前端
- **v0.4**：双向转换（EnforceScript → Python）便于测试回环；增量/缓存

## 已知限制（诚实声明）

1. 语料校准（VERIFY.md）已定案绝大多数语法映射；仅剩 int/int 除法结果类型、`@property`
   getter/setter 惯用法、显式基类构造调用、回调/`ScriptCaller`、`\uXXXX` 转义等少量 ⚠ 项，
   需以 Workbench 编译结果为准最终校准；
2. 触碰动态特性的 Python 必然需要人工改写——工具的价值是把能自动的部分自动掉，把不能的部分精确暴露；
3. 字段上提对"仅在部分分支赋值"的字段按 EnforceScript 默认值（0/null）声明，与 Python 的 `AttributeError` 语义不同 → 会告警；
4. 无测试环境时金样只能保证文本稳定，不保证编译通过（`--validate` 可补上这一环）。
