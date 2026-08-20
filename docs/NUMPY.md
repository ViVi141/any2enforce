# NumPy Subset Mapper — any2enforce 设计文档

> **项目**: any2enforce — Python → EnforceScript transpiler for Arma Reforger  
> **文档目标**: 定义内置 "in-tool numpy subset mapper" 的设计，将 `import numpy as np` / `np.xxx` 映射到 EnforceScript 内置数值类型（`array<float>` + Math 运算），无需外部依赖。  
> **语言**: 中文 + English (关键术语保留英文)

---

## 1. 目标与范围 (Goal & Scope)

### 1.1 总目标

当用户代码中出现 `import numpy as np` 以及对 `np.xxx` 的调用时，transpiler **不依赖外部 CPython numpy**，而是直接在 EnforceScript 中生成等价的 **内联数值操作**。对于无法映射的用法，输出明确的诊断错误（"honesty rule"），绝不生成错误但静默的代码。

### 1.2 IN — 支持的 NumPy 特性

| 类别 | 具体项 |
|------|--------|
| **构造** | `np.array(list)` — 1D / 2D float32 |
| | `np.zeros(shape)` / `np.ones(shape)` / `np.full(shape, val)` / `np.empty(shape)` |
| | `np.zeros_like(a)` / `np.ones_like(a)` / `np.full_like(a, val)` |
| **逐元素算术** | `+` `-` `*` `/` `//` `%` `**` (element-wise, same-shape) |
| **规约** | `np.sum` / `np.mean` / `np.std` / `np.max` / `np.min` / `np.abs` / `np.sqrt` / `np.pow` / `np.exp` |
| **矩阵运算** | `np.dot(a, b)` (1D & 2D) / `np.matmul(a, b)` (2D × 2D) |
| **索引** | `a[i]` / `a[i][j]` get & set |
| **属性** | `.shape` / `.ndim` / `.size` |
| **转换** | `.item()` / `.tolist()` |

### 1.3 OUT — 明确不支持（将产生诊断错误）

- Broadcasting different shapes (e.g. `(3,1) + (3,)`)
- Fancy indexing / integer array indexing (`a[[0,2]]`)
- Boolean masks (`a[a > 0]`)
- Views / strides / slicing except simple `a[i]` / `a[i][j]`
- Complex numbers (`np.complex64`)
- In-place operations on non-contiguous arrays
- `np.linalg` beyond dot/matmul
- `np.random` beyond the listed subset; random with explicit seed is supported
- 任何其他无法通过 EnforceScript `array<float>` + `Math.*` 实现的功能

> **Honesty Rule**: 当检测到 OUT 范围内的用法时，transpiler 必须抛出清晰的诊断错误，指出原因和推荐的替代方案，绝不可静默生成错误代码。

---

## 2. 表示映射 (Representation Mapping)

### 2.1 EnforceScript 事实回顾

- `float` = IEEE-754 **float32** (single precision)
- **无 ternary operator**；必须用 `if-else`
- 数学函数位于 `Math` 命名空间：`Math.Pow` / `Math.Min` / `Math.Max` / `Math.Sqrt` / `Math.AbsFloat` / `Math.AbsInt` / `Math.Floor` / `Math.Ceil` / `Math.Round` / `Math.Mod`
- `Math.Abs` **不存在**——必须用 `Math.AbsFloat` 或 `Math.AbsInt`
- `array<T>` 支持读写：`arr[index]` get / `arr[index] = val` set

### 2.2 推荐表示方案

> **方案 A：1D-only `array<float>`（推荐）**

**理由**：EnforceScript 的 `array<T>` **不支持多维形状**。`array<array<float>>` 是语法合法的，但不是连续存储的二维数组，且无法保证所有内层数组长度一致。鉴于 this project 的目标是 **轻量且可预测**，我们选择：

1. **所有 ndarray 表示为 `array<float>`**，shape / ndim / size 作为附加属性。
2. **2D 数组按行展平**（row-major order），shape 记录为 `(rows, cols)`。
3. 构造时立即摊平，所有运算在摊平后的 `array<float>` 上执行。
4. 索引 `a[i][j]` 翻译为 `a[i * cols + j]`。

**为什么不是生成的 class？** EnforceScript 不支持用户定义类内的运算符重载，也不支持模板泛型。手写一个 wrapper class 会增加复杂性和运行时开销，而 `array<float>` + 纯函数组合已经够用。

### 2.3 核心类型签名（伪代码）

```enforce
// 构建
array<float> np_array(list<float> data, {int rows=0, int cols=0})
array<float> np_zeros(int size)                                   // 1D
array<float> np_zeros_2d(int rows, int cols)                      // 2D flat
array<float> np_ones(int size)
array<float> np_full(int size, float val)

// 属性
int ndim(array<float> a)     // 从关联 shape 推断
int size(array<float> a)     // a.Length()
array<int> shape(array<float> a)  // 返回 [rows, cols] 或 [len]

// 索引
float get(array<float> a, int i)            // a[i]
float get2d(array<float> a, int r, int c)   // a[r * cols + c]
void set(array<float> a, int i, float v)
void set2d(array<float> a, int r, int c, float v)

// 转换
float item(array<float> a)        // 仅当 size == 1
array<float> tolist(array<float> a)  // 已经是 array<float>

// 运算（所有参数 same-shape，返回新 array<float>）
array<float> elem_add(array<float> a, array<float> b)
array<float> elem_sub(array<float> a, array<float> b)
array<float> elem_mul(array<float> a, array<float> b)
array<float> elem_div(array<float> a, array<float> b)
array<float> elem_floor_div(array<float> a, array<float> b)
array<float> elem_mod(array<float> a, array<float> b)
array<float> elem_pow(array<float> a, array<float> b)

// 规约
float sum(array<float> a)
float mean(array<float> a)
float std(array<float> a)
float max(array<float> a)
float min(array<float> a)
array<float> abs(array<float> a)
array<float> sqrt(array<float> a)
array<float> pow(array<float> a, float exp)
array<float> exp(array<float> a)

// 线性代数
float dot(array<float> a, array<float> b)           // 1D inner product
array<float> matmul(float* a, float* b, int m, int n, int p)  // (m×n) · (n×p) flat
```

> **注意**: 这些函数并不直接暴露在 EnforceScript 命名空间中；transpiler 在代码生成时将它们**内联展开**为适当的 `array` + `Math.*` 调用。

---

## 3. API 映射表 (API Mapping Table)

以下列举 **IN** 范围内的常见 numpy API 及其在 EnforceScript 中的生成形式。

| NumPy 调用 | Emitted EnforceScript | 备注 |
|------------|----------------------|------|
| `np.array([1,2,3])` | `{1.0, 2.0, 3.0}` (array<float> literal) | **float32**: 所有 Python int 字面量转为 `.0` |
| `np.array([[1,2],[3,4]])` | `{1.0, 2.0, 3.0, 4.0}` + shape (2,2) 元数据 | 展平存储 |
| `np.zeros(5)` | `float[] arr = new float[5];` + 填充 0.0 | - |
| `np.ones((3,4))` | `new float[12]` + 填充 1.0 + shape(3,4) | 展平 |
| `np.full((2,3), 7.0)` | `new float[6]` + 填充 7.0 + shape(2,3) | - |
| `np.empty(10)` | `new float[10]` | 值未初始化（符合 numpy 语义） |
| `a + b` | 内联 `elem_add` 循环 | 前提 `a.shape == b.shape` |
| `a * b` | 内联 `elem_mul` 循环 | 逐元素乘法，非矩阵乘法 |
| `a // b` | `Math.Floor(a[i] / b[i])` | 整数除法 |
| `a % b` | `Math.Mod(a[i], b[i])` | - |
| `a ** b` | `Math.Pow(a[i], b[i])` | - |
| `np.sum(a)` | 循环累加 `float sum = 0; for (...) sum += a[i];` | - |
| `np.mean(a)` | `sum(a) / a.Length()` | float32 除法 |
| `np.std(a)` | `Math.Sqrt(mean((a - mean)^2))` | 总体标准差 (ddof=0) |
| `np.max(a)` | `float m = a[0]; for (...) if (a[i] > m) m = a[i];` | - |
| `np.min(a)` | 对称循环 | - |
| `np.abs(a)` | 循环 `Math.AbsFloat(a[i])` | - |
| `np.sqrt(a)` | 循环 `Math.Sqrt(a[i])` | - |
| `np.pow(a, 2)` | 循环 `Math.Pow(a[i], 2.0)` | - |
| `np.exp(a)` | 循环 `Math.Pow(2.718281828, a[i])` | 近似 `e^x` |
| `np.dot(a, b)` | 1D: `float d = 0; for (...) d += a[i] * b[i];` | 2D: 暂不支持 |
| `np.matmul(A, B)` | 展平后的三重循环 (m×n × n×p) | 仅 2D × 2D |
| `a[0]` | `a[0]` | 直接 array 索引 |
| `a[1][2]` (2D) | `a[1 * cols + 2]` | 需已知 cols |
| `a.shape` | `{rows, cols}` (array<int>) | 元数据随 array 传递 |
| `a.ndim` | `shape.Length()` | 或硬编码 1/2 |
| `a.size` | `a.Length()` | - |
| `a.item()` | `a[0]` | 仅当 `a.Length() == 1` |
| `a.tolist()` | 对 `array<float>` 无需转换 | 已是等价结构 |

> **float32 精度警告**: EnforceScript `float` = float32。所有映射产生的代码应在注释中标注 `// float32 precision`，提醒用户 numpy float64 默认值在此处降级为 float32。

---

## 4. 验证策略 (Verification Strategy)

### 4.1 双轨验证架构

```
┌─────────────────────────────────────────────┐
│  Python Reference Emulator (CI 主环)          │
│  numpy 2.4.4 IS installed                    │
│  Emu: 用 Python 纯函数模拟 EnforceScript     │
│  输出 → 与 real numpy float64 比 tolerance   │
│  通过 → CI green                             │
│  失败 → 打印 diff + 阈值                     │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  EnforceScript .c 编译验证 (Optional / Dev)  │
│  transpiler 输出 → .c file                   │
│  人肉检查 + Workbench 编译测试               │
│  不阻塞 CI                                   │
└─────────────────────────────────────────────┘
```

### 4.2 表驱动 Harness (table-driven)

在 `tests/` 目录（由另一个 agent 维护）中，我们预期一个 CSV / JSON 测试表，每行包含：

- **名称** (e.g. `test_sum_1d`)
- **输入** (Python code snippet)
- **预期 Emu 输出** (float32 近似)
- **tolerance** (默认 `1e-5`，float32 eps ≈ 1.19e-7，但运算累积误差后放宽)

Harness 伪代码：

```python
# any2enforce/tests/numpy_harness.py (概念性)
import numpy as np

def emu_sum(a: list) -> float:
    s = 0.0
    for x in a:
        s += x
    return s  # float32 semantics via np.float32 cast

def test_row(row):
    real = np.float64(row["numpy_expr"])
    emu  = np.float32(emu_impl(row["input"]))
    assert abs(real - emu) < row["tolerance"]
```

### 4.3 float32 精度说明

- `float32 epsilon ≈ 1.19e-7`
- 但多次运算后累积误差可达 **~1e-5 ~ 1e-6**
- 均值、标准差等涉及除法的运算误差更大
- **建议 tolerance**: `1e-4` 安全，`1e-5` 严格
- Harness 中通过 `np.float32(...)` 显式模拟 float32 截断

### 4.4 无需 Workbench 的 CI

所有验证在 Python 层完成，**不依赖 Workbench 或 Arma Reforger 运行时**。`.c` 文件编译验证仅在开发者本地需要时执行（`make validate` 等，未来阶段实现）。

### 4.5 原型已验证（verify/numpy_probe.py，2026-08）

一个独立的可行性证明脚本 `verify/numpy_probe.py`（仅作参考，不改主代码）已运行通过：
float32 模拟器 vs 真实 **numpy 2.4.4** 对拍，**12/12 用例 PASS**（sum/mean/std/dot/matmul/
square/exp/abs，数组尺寸 4/16/100 与 2×3 matmul），容差内一致；并量化了 float32-vs-float64
漂移（2000 元素大数组 mean 漂移 ≈ −0.010、std ≈ +0.006），印证 §4.3 的累积误差结论。
脚本可反复运行：`python verify/numpy_probe.py`。

---


## 5. 集成路径 (Integration Path)

> 本模块是一个独立的设计/规范文档。在后续开发阶段，mapper 作为单独的 Python 模块实现：

```
any2enforce/
├── frontends/
│   ├── numpy_mapper.py          ← 本模块 (future)
│   │   ├── NumpyMapper class
│   │   ├── emit_array_constructor()
│   │   ├── emit_elementwise_op()
│   │   ├── emit_reduction()
│   │   └── ...
│   ├── ... (其他 frontends)
├── docs/
│   └── NUMPY.md                 ← 本文件
└── ...
```

**接口约定**（待定，仅供记录）：

```python
class NumpyMapper:
    def map(self, node: ast.AST) -> str:
        """接收 numpy API 调用的 AST 节点，返回 EnforceScript 代码片段"""
        ...
```

- Mapper 不应假设 transpiler 主循环的细节；只接受 `ast` 节点，返回合法 EnforceScript 字符串。
- 主 transpiler 在遍历 Python AST 时，遇到 `ast.Attribute` 或 `ast.Call` 匹配 numpy 模式时，委派给 `NumpyMapper.map()`。
- 如果无法映射，mapper 抛出 `NumpyMappingError(message)`。

---

## 附录 A：EnforceScript 事实速查

| 项目 | 内容 |
|------|------|
| float 精度 | float32 (IEEE-754 single) |
| Ternary | ❌ 不支持 |
| `Math.Abs` | ❌ 不存在；用 `Math.AbsFloat` / `Math.AbsInt` |
| `Math.Pow` | ✅ |
| `Math.Min`/`Max` | ✅ |
| `Math.Sqrt` | ✅ |
| `Math.Floor`/`Ceil`/`Round` | ✅ |
| `Math.Mod` | ✅ (float mod) |
| `array<T>` | ✅ 读写 `arr[]` / `arr[] =` |
| 运算符重载 | ❌ 不支持 |

---

*文档版本 v1.0 — 2025*