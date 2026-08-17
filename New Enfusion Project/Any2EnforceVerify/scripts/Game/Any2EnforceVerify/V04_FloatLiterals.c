// [V04] 浮点字面量（首轮编译已定案）
// 已确认：1e+30（小写 e + 符号）与 1.0e30 合法；
// 已确认非法：1E30（大写 E、无小数点、无符号）→ 已移除。
// 工具输出用 Python repr（恒为小写 e 且带符号，如 1e+30）→ 安全。
// 其余指数写法（1e30 / 1.0E30）在探测包 P05 验证。

class V04_FloatLiterals
{
	static void Check()
	{
		float f1 = 1e+30;
		PrintFormat("[V04] 1e+30  => %1", f1);

		float f2 = 1.0e30;
		PrintFormat("[V04] 1.0e30 => %1", f2);

		float f3 = 0.5;
		PrintFormat("[V04] 0.5    => %1", f3);
	}
};
