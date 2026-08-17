// [V01] int/int 除法 → float：能否编译 + 值是多少
// 语料先例：float angleRange = sector/2;  FLICKER_FREQUENCY = 1 / 30;
// 判定：输出 3.5 → `/` 是 float 除法；输出 3 → int 除法后转 float。
// 注意：`int i = 7 / 2;` 是否合法在探测包 P06 单独验证。

class V01_IntDivision
{
	static void Check()
	{
		float f = 7 / 2;
		PrintFormat("[V01] float f = 7 / 2       => %1   (3.5 = float 除法 / 3 = int 除法)", f);

		float floored = Math.Floor(7.0 / 2.0);
		PrintFormat("[V01] Math.Floor(7.0 / 2.0) => %1   (应为 3)", floored);
	}
};
