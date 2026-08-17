# 验证包使用说明

两个目录，复制进你的 addon 项目（保持 `scripts/Game/...` 层级）：

```
Any2EnforceVerify/   # 可整体复制：预期全部编译通过 + 可运行自检
Any2EnforceProbes/   # 语法探测：每个文件单独复制、单独编译（预期部分失败）
```

## 步骤

1. 把 `Any2EnforceVerify/scripts` 下的 `Game/Any2EnforceVerify/` 复制到你的 addon 的
   `scripts/Game/` 下，在 Workbench 里 **ValidateScripts** —— 预期 0 错误；
2. 运行自检：在脚本调试器 / 游戏控制台 / 任意组件的 `OnPostInit` 中调用
   `Any2EnforceVerify.VerifyEntry.Run();`，按控制台输出核对下表；
3. 把 `Any2EnforceProbes/scripts` 下的 `Game/Any2EnforceProbes/` **一个文件一个文件**
   复制进 `scripts/Game/`（或把文件逐个丢进现有目录），每次 ValidateScripts，
   按文件头注释取消注释候选语法，记录结果；
4. 把结果回填下表，发给我（或直接更新 `docs/VERIFY.md`），我据此修正
   `backends/enforce.py` 的映射。

## 结果表（对应 docs/VERIFY.md 待确认项）

| ID | 验证内容 | 文件 | 预期 | 结果 |
|---|---|---|---|---|
| V01 | int/int 除法结果类型 | `Any2EnforceVerify/V01_IntDivision.c` | `7/2`→3.5（float 除法）；`int i = 7/2` 编译结果待定 | ☐ |
| V02 | float 直接取模 | `Any2EnforceVerify/V02_FloatModulo.c` | `5.5 % 2.0` 编译通过→1.5（则工具可简化映射） | ☐ |
| V03 | 字符串转义 `\uXXXX`/`\xXX`/`\0` | `Any2EnforceVerify/V03_StringEscapes.c` | `\u0041`→A；`\x41`→A；`\0` 行为待定 | ☐ |
| V04 | 科学计数浮点字面量 | `Any2EnforceVerify/V04_FloatLiterals.c` | `1e+30` 编译通过 | ☐ |
| V05 | 内联数组实参 `{...}` | `Any2EnforceVerify/V05_InlineArrayArg.c` | 编译通过→6（v0.2 放开列表实参） | ☐ |
| V06 | `array/map.Contains` | `Any2EnforceVerify/V06_Contains.c` | array 有；map 待定 | ☐ |
| C01 | 基类默认构造隐式调用 | `Any2EnforceVerify/C01_BaseCtorImplicit.c` | 编译过→42（隐式调用成立） | ☐ |
| C05 | ScriptInvoker 回调 | `Any2EnforceVerify/C05_ScriptInvoker.c` | 编译过→true（回调机制确认） | ☐ |
| P01 | 基类必选参数构造 | `Any2EnforceProbes/P01_BaseCtorRequiredArgs.c` | 预期编译失败（需显式调用） | ☐ |
| P02 | 显式 super 构造语法 | `Any2EnforceProbes/P02_SuperCtorSyntax.c` | 候选 A/B/C 哪个能过 | ☐ |
| P03 | 运算符重载 | `Any2EnforceProbes/P03_OpOverload.c` | 预期全部失败（语料 0 命中） | ☐ |
| P04 | char 类型 | `Any2EnforceProbes/P04_CharType.c` | 预期全部失败（无 char） | ☐ |

> 判定标准：**编译通过 + 输出符合预期 = 定案**；编译失败的行在文件头注释里已说明含义。
> 任何"预期失败却编译通过"都是重要发现，请务必记录。
