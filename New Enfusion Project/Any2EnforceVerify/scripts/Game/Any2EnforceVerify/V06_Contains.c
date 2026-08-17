// [V06] 成员测试：array.Contains（语料先例 418 文件）
// map 上的 Contains 无先例，移到探测包 P09 验证。

class V06_Contains
{
	static void Check()
	{
		array<int> a = { 1, 2, 3 };
		bool b1 = a.Contains(2);
		PrintFormat("[V06] array.Contains(2) => %1   (true)", b1);
		bool b2 = a.Contains(9);
		PrintFormat("[V06] array.Contains(9) => %1   (false)", b2);
	}
};
