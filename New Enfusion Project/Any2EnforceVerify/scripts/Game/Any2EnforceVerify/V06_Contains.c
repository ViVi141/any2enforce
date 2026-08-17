// [V06] 成员测试：array.Contains / map.Contains
// 影响：Python `x in lst` 的映射依据（语料 .Contains( 418 文件，多为 array）
// 若 map.Contains 编译失败 -> 字典成员测试需改用 m.Get(k) != null 之类。

class V06_Contains
{
	static void Check()
	{
		array<int> a = { 1, 2, 3 };
		bool b1 = a.Contains(2);
		PrintFormat("[V06] array.Contains(2)  => %1   (true)", b1);
		bool b2 = a.Contains(9);
		PrintFormat("[V06] array.Contains(9)  => %1   (false)", b2);

		map<string, int> m = new map<string, int>();
		m["k"] = 1;
		bool b3 = m.Contains("k");
		PrintFormat("[V06] map.Contains(k)    => %1   (若编译失败 -> map 无 Contains)", b3);
		bool b4 = m.Contains("nope");
		PrintFormat("[V06] map.Contains(nope) => %1   (false)", b4);
	}
};
