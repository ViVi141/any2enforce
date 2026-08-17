// ============================================================
// Any2EnforceVerify — 验证入口
// 把整个 Any2EnforceVerify 文件夹复制到你的 addon 的
// scripts/ 下（保持 Game/Any2EnforceVerify/ 层级），然后：
//   1) 直接编译（ValidateScripts / Workbench）—— 本包预期全过；
//   2) 运行：在脚本调试器 / 游戏控制台 / 任意组件 OnPostInit 中调用
//        Any2EnforceVerify.VerifyEntry.Run();
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
