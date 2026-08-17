// [V04] 浮点字面量：科学计数法
// 对应 VERIFY.md #24（工具当前直接输出 Python repr，如 1e+30）
// 若某一行编译失败：说明该写法非法，工具需改为普通小数形式。

class V04_FloatLiterals
{
	static void Check()
	{
		float f1 = 1e+30;
		PrintFormat("[V04] 1e+30  => %1", f1);

		float f2 = 1.0e30;
		PrintFormat("[V04] 1.0e30 => %1", f2);

		float f3 = 1E30;
		PrintFormat("[V04] 1E30   => %1", f3);

		float f4 = 0.5;
		PrintFormat("[V04] 0.5    => %1", f4);
	}
};
