// [P07] float 直接取模 %（语料无先例；Math.Mod 已确认存在）
// 判定：编译通过 + 输出 1.5 → float 可直接用 %，工具映射可从
//       Math.Mod 简化为 %；编译失败 → 维持 Math.Mod 现状。
// 注意：本文件属于"探测包"，请单独复制编译。

class P07_FloatModulo
{
	static void Check()
	{
		float a = 5.5 % 2.0;
		PrintFormat("[P07] 5.5 mod 2.0 => %1   (1.5 = 直接取模合法)", a);
	}
};
