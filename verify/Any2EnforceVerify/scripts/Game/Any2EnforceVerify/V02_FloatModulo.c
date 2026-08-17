// [V02] float 取模：Math.Mod（Math.c 文档确认：Print( Math.Mod(5.0, 2.0) );）
// 注意：float 直接 `%` 的合法性语料无先例，在探测包 P07 单独验证，
//       避免不确定语法拖垮本包整体编译。

class V02_FloatModulo
{
	static void Check()
	{
		float b = Math.Mod(5.5, 2.0);
		PrintFormat("[V02] Math.Mod(5.5, 2.0) => %1   (应为 1.5)", b);
	}
};
