# VERIFY.md — EnforceScript 语法实测报告

> 校准语料：`C:\Users\74738\Desktop\_reforger_code_full_v2\scripts`
> （6568 个 `.c` 文件，Arma Reforger 1.x 官方 + 引擎生成脚本）。
> ✅ = 已在真实代码中确认；⚠ = 无直接样本，仍按保守假设实现；
> ❌ = 确认不存在，工具已做降级处理。

## 已确认（✅）— 实现已按此校准

| # | 构造 | 证据（真实代码） | 工具行为 |
|---|---|---|---|
| 1 | 字符串 `+` | `"\t" + msg`；`...ToString() + "s"` | `+` 直出 |
| 2 | 数组下标 `[]` | `s_aAiDebugMsgTypeLabels[m_Type]` | `arr[i]` 直出 |
| 3 | map 下标读写 `[]` | `m_mWeaponTypeHandlingConfig[k] = config;`、`m_mSquadCallsigns[i]` | `m[k]`（读写同一语法） |
| 4 | 数组字面量 | `array<Class> attributes = {};`、`testSuites = {testSuite};`、`array<ref SampleObject> a = {SampleObject(5), ...};` | `array<T> x = { ... };`（仅赋值场景） |
| 5 | map 创建 | `new map<...>()`（254 文件） | `map<K,V> x = new map<K,V>();` + `x[k] = v;` |
| 7 | 取模 | 数值 `%`：`directionAngle % 360`；`Math.Mod(float,float)`（9 文件） | int→`%`；float→`Math.Mod` |
| 8 | 格式化占位符 | `string.Format("%1_###_%2", ...)`、`PrintFormat("Run: %1", ...)` | `%1..%9` |
| 9 | 字符串化 | `.ToString()`（588 文件）、`static string.ToString(void var)` | `str(x)`→`x.ToString()` / `string.ToString(x)` |
| 10 | Math 函数 | `Math.c` 权威签名：`Floor/Ceil/Pow/Mod/Min/Max/MinInt/MaxInt/AbsFloat/AbsInt/Clamp/Round/Sqrt` | `Math.Floor(a/b)`、`Math.Pow`、`Math.MinInt/MaxInt`、`Math.AbsInt/AbsFloat` |
| 11 | 参数默认值 | `void Print(string msg, LogLevel level = LogLevel.NORMAL)`；`ToFloat(default: 0.0, offset: 3)` 命名参数 | 默认值直出；命名参数 v0.1 不支持 |
| 12 | 构造函数 | `void SCR_AIDebugMessage(string message, EAIDebugMsgType type = EAIDebugMsgType.NONE, ...)` | `void ClassName(params)` |
| 13 | super 方法调用 | `super.Begin(...)`、`super.OnUpdate(...)`（1357 文件） | `super.M(...)` 直出 |
| 17 | foreach | `foreach (Class attr : attributes)`、`foreach (ref SCR_AIGroupVehicle vehicle : ...)` | `foreach (T x : arr)`；类元素自动加 `ref` |
| 18 | auto | `auto points = new array<vector>();` | 无注解局部变量 → `auto` |
| 20 | Print | `proto void Print(void var, LogLevel level = LogLevel.NORMAL)` | `Print(x)` 任意类型 |
| 20b | PrintFormat | `proto void PrintFormat(string fmt, void param1..param9 = NULL, LogLevel level = ...)`（201 文件） | `print(a,b)` → `PrintFormat("%1 %2", a, b)` |
| 22 | 可见性 | `protected int m_x;`（2430 文件） | 显式 `protected`（可配置） |
| 23 | 字段默认值 | 引擎大量裸声明未初始化字段 | 类型默认值（0/""/null） |
| 25 | 静态成员 | `static string Format(...)`、`static const ref array<string> s_aAiDebugMsgTypeLabels = {...};` | `static` 直出 |
| 26 | 字段访问 | 引擎用裸 `m_x`（`this.m_x` 仅 87 文件） | **裸 `m_x`（`m_` 前缀消歧，无需 `this.`）** |
| 27 | 类类型 `ref` | `ref SCR_TimerEntryBase`、`array<ref SampleObject>` | ClassType 渲染为 `ref Foo` |
| 28 | enum | `enum EAIDebugMsgType { NONE = 0, ... };` + `EAIDebugMsgType.NONE` | 枚举直出 |
| 29 | switch/case | `switch (m_LogLevel) { case LogLevel.SPAM: ...; break; }` | v0.1 不支持 Python→switch（Python 无原生） |
| 30 | 计数 for | `for (int i = 0; i < n; i++)`（396 文件） | `range()` 展开成同形 |
| 31 | C 风格强转 | `(int)h << 24`、`(float)milliseconds / 1000` | `int(x)`→`(int)(x)` |

## 确认不存在（❌）— 工具已降级

| 构造 | 证据 | 降级行为 |
|---|---|---|
| 三元运算符 `c ? a : b` | 全语料 `?` 仅出现在注释/属性字符串中 | `x = a if c else b` → `T x = b; if (c) { x = a; }`；`return` 场景 → if/else return |
| 裸全局 `format(...)` | 只有 `string.Format` 静态方法（2 个自定义 Format 无关） | f-string / `%` 格式化 → `string.Format(...)` |
| `Math.Abs` | Math.c 中只有 `AbsFloat`/`AbsInt` | `abs(x)` 按类型分派 `Math.AbsInt/AbsFloat` |
| `PrintError`/`PrintWarning` 全局 | 0 文件（仅有自定义方法） | 不映射 |
| 数组 `new array<T> { ... }` | 0 文件；惯用 `array<T> x = { ... };` | 改用 `{}` 初始化式 |

## 待确认（⚠）— 保守假设 + Workbench 校验项

| # | 构造 | 假设 |
|---|---|---|
| 6 | int/int 除法结果类型 | `Math.Floor(a / b)`；EnforceScript `/` 疑似返回 float |
| 13b | 显式基类构造调用 | `super(` 0 命中 → 假定基类默认构造隐式调用；`super().__init__(...)` 暂报错 |
| 14 | 属性惯用法 | 引擎无 property，用 `GetX/SetX`；`@property` v0.1 报错待 v0.2 生成 getter/setter |
| 15 | 运算符重载 | 未发现样本，不支持 |
| 16 | 回调/函数指针 | 未发现样本；后续调查 `ScriptInvoker`/`ScriptCaller` |
| 21 | 字符串转义 `\uXXXX`/`\xXX` | 语料极少（1/6 文件），转义规则按 C 系处理 |
| 24 | 浮点科学计数字面量 `1e+30` | 未见样本，`repr()` 直出 |

## 语料事实速查（其他发现）

- 命名惯例：实例字段 `m_`，静态字段 `s_`，方法 PascalCase；静态常量 `static const`。
- 命名参数语法：`method(paramName: value)`（如 `ToFloat(default: 17.6, offset: 3)`、`PrintFormat(..., level: LogLevel.DEBUG)`）。
- `string` API：`Length/Contains/StartsWith/EndsWith/Substring/IndexOf/Trim/Split/Join/ToInt/ToFloat/ToLower/ToUpper/Get(i)`。
- 集合：`.Count()`（array/map/set）、`.Insert()`、`.Remove()`、`.Find()`；map 另支持 `[]` 读写与 `.Set/.Get`。
- `NULL` 只见于引擎 proto 签名默认值；业务代码一律小写 `null`。
- 模块级可执行代码不存在 —— Reforger 全靠类/组件/实体驱动（印证 v0.1"只输出函数与类"的取舍）。

## 自动化校验（规划）

`tests/verify_workbench.py`：把"待确认"项生成最小 `.c` → 部署 addon → `ValidateScripts`，
把编译结果回填本表，接入 CI。当前无 Workbench 环境时，以本语料报告为准。

## 手工验证包（立即可用）

`verify/` 目录已备好两个复制即用的包：

- `verify/Any2EnforceVerify/` —— 预期全部编译通过，`VerifyEntry.Run()` 打印运行时自检
  （int 除法、float 取模、字符串转义、浮点字面量、内联数组实参、Contains、基类隐式构造、
  ScriptInvoker 回调）；
- `verify/Any2EnforceProbes/` —— 逐个编译的语法探测（参数化基类构造、super 构造语法、
  运算符重载、char 类型），预期部分失败，失败本身就是结论。

使用与结果回填见 [`verify/README.md`](../verify/README.md)。
