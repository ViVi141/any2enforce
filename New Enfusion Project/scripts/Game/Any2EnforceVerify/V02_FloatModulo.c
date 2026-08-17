// [V02] float 取模：% 直接用于 float
// 对应 VERIFY.md #7（工具当前映射：int 用 %，float 用 Math.Mod）
// 预期：
//   - 若 "5.5 % 2.0" 编译通过且输出 1.5 -> float 可直接用 %，工具映射可简化
//   - 若编译失败 -> float 必须 Math.Mod，维持现状

class V02_FloatModulo
{
	static void Check()
	{
		float a = 5.5 % 2.0;
		PrintFormat("[V02] 5.5 mod 2.0       => %1   (1.5 = 直接取模合法)", a);

		float b = Math.Mod(5.5, 2.0);
		PrintFormat("[V02] Math.Mod(5.5,2.0) => %1   (对照)", b);
	}
};
