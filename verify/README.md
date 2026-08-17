# 验证包使用说明

两个目录，复制进你的 addon 项目（保持 `scripts/Game/...` 层级）：

```
Any2EnforceVerify/   # 可整体复制：预期全部编译通过 + 可运行自检
Any2EnforceProbes/   # 语法探测：每个文件单独复制、单独编译（预期部分失败）
```

## ⚠️ 常见错误（重要，先看这个）

**不要**把 `.c` 文件的内容粘贴进 `execCode` / 脚本控制台去"运行"。
`execCode` 是表达式执行器，只能执行表达式/语句，**不能声明 `class`**——
你会得到 `error: Broken expression (missing ';'?)`（把 `class X` 当表达式解析了）。

正确流程（两步）：

1. **编译**：把 `.c` 文件放进 addon 的 `scripts/Game/Any2EnforceVerify/` 目录，
   在 Workbench 里 **ValidateScripts** —— 类定义在这里编译；
2. **运行**：编译通过后，才在控制台 / execCode / 任意组件里调用入口：
   ```
   VerifyEntry.Run()
   ```
   （EnforceScript 无命名空间，类名就是 `VerifyEntry`；也可以单独调用
   `V01_IntDivision.Check()` 等任意一个检查。）

## 步骤

1. 把 `Any2EnforceVerify/scripts` 下的 `Game/Any2EnforceVerify/` 复制到你的 addon 的
   `scripts/Game/` 下，在 Workbench 里 **ValidateScripts** —— 预期 0 错误；
2. 编译通过后运行自检：execCode / 游戏控制台 / 任意组件的 `OnPostInit` 中调用
   `VerifyEntry.Run();`，按控制台输出核对下表；
3. 把 `Any2EnforceProbes/scripts` 下的 `Game/Any2EnforceProbes/` **一个文件一个文件**
   复制进 `scripts/Game/`（或把文件逐个丢进现有目录），每次 ValidateScripts，
   按文件头注释取消注释候选语法，记录结果；
4. 把结果回填下表，发给我（或直接更新 `docs/VERIFY.md`），我据此修正
   `backends/enforce.py` 的映射。

## 结果表（对应 docs/VERIFY.md 待确认项）

> 首轮编译发现（已定案）：`1E30`（大写 E、无小数点、无符号）**非法**；
> `1e+30` / `1.0e30` 合法 → 工具的 Python repr 输出（恒小写 e 带符号）安全。

| ID | 验证内容 | 文件 | 预期 | 结果 |
|---|---|---|---|---|
| V01 | int/int → float 除法值 | `Any2EnforceVerify/V01_IntDivision.c` | `7/2`→3.5（float 除法）或 3 | ☐ |
| V02 | Math.Mod float 取模 | `Any2EnforceVerify/V02_FloatModulo.c` | 输出 1.5 | ☐ |
| V03 | 字符串转义 `\t`/`\n`（确定项） | `Any2EnforceVerify/V03_StringEscapes.c` | 合法 | ☐ |
| V04 | 浮点字面量 `1e+30`/`1.0e30`/`0.5` | `Any2EnforceVerify/V04_FloatLiterals.c` | 已定案：合法 | ☐ |
| V05 | 内联数组实参 `{...}` | `Any2EnforceVerify/V05_InlineArrayArg.c` | 编译通过→6（v0.2 放开列表实参） | ☐ |
| V06 | `array.Contains` | `Any2EnforceVerify/V06_Contains.c` | true / false | ☐ |
| C01 | 基类默认构造隐式调用 | `Any2EnforceVerify/C01_BaseCtorImplicit.c` | 编译过→42（隐式调用成立） | ☐ |
| C05 | ScriptInvoker 回调 | `Any2EnforceVerify/C05_ScriptInvoker.c` | 编译过→true | ☐ |
| P01 | 基类必选参数构造 | `Any2EnforceProbes/P01_BaseCtorRequiredArgs.c` | 预期编译失败（需显式调用） | ☐ |
| P02 | 显式 super 构造语法 | `Any2EnforceProbes/P02_SuperCtorSyntax.c` | 候选 A/B/C 哪个能过 | ☐ |
| P03 | 运算符重载 | `Any2EnforceProbes/P03_OpOverload.c` | 预期全部失败（语料 0 命中） | ☐ |
| P04 | char 类型 | `Any2EnforceProbes/P04_CharType.c` | 预期全部失败（无 char） | ☐ |
| P05 | 浮点指数写法 `1e30`/`1.0E30` | `Any2EnforceProbes/P05_FloatLiteralExponent.c` | 按报错行号定位 | ☐ |
| P06 | `int = int / int` 合法性 | `Any2EnforceProbes/P06_IntDivToInt.c` | 编译过→输出 3/4；失败→需 (int) 强转 | ☐ |
| P07 | float 直接 `%` | `Any2EnforceProbes/P07_FloatModulo.c` | 编译过→1.5（工具可简化） | ☐ |
| P08 | 转义 `\u0041`/`\x41`/`\0` | `Any2EnforceProbes/P08_StringEscapes.c` | 按报错行号定位 | ☐ |
| P09 | map.Contains / Get 回退 | `Any2EnforceProbes/P09_MapContains.c` | A 或 B 哪个编译过 | ☐ |

> 判定标准：**编译通过 + 输出符合预期 = 定案**；编译失败的行在文件头注释里已说明含义。
> 任何"预期失败却编译通过"都是重要发现，请务必记录。
