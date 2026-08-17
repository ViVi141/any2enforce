// ============================================================
// Any2EnforceVerify — 验证入口
// 把整个 Any2EnforceVerify 文件夹复制到你的 addon 的
// scripts/ 下（保持 Game/Any2EnforceVerify/ 层级），然后：
//   1) 直接编译（ValidateScripts / Workbench）—— 本包预期全过；
//   2) 编译通过后运行（execCode / 游戏控制台 / 任意组件 OnPostInit）：
//        VerifyEntry.Run();
//      （EnforceScript 无命名空间，类名就是 VerifyEntry；
//        注意：execCode 不能声明 class，类必须先进 scripts/ 编译）
//   3) 按输出逐项核对 docs/VERIFY.md 的待确认清单。
// ============================================================

class VerifyEntry
{
	static void Run()
	{
		Print("==== Any2EnforceVerify ====");
		V01_IntDivision.Check();
		V02_FloatModulo.Check();
		V03_StringEscapes.Check();
		V04_FloatLiterals.Check();
		V05_InlineArrayArg.Check();
		V06_Contains.Check();
		C01_BaseCtorImplicit.Check();
		C05_ScriptInvoker.Check();
		Print("==== Any2EnforceVerify done ====");
	}
};
