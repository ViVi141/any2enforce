// [P09] map 成员测试写法验证 —— ✅ 已定案：map.Contains 存在
// 实测记录：候选 A `m.Contains("k")` 编译通过（与 array.Contains 同款 API）。
// 结论：Python `x in dict` 直接映射 `m.Contains(x)`（工具已实现）。

class P09_MapContains
{
	static void Check()
	{
		map<string, int> m = new map<string, int>();
		m["k"] = 1;

		bool b1 = m.Contains("k");
		PrintFormat("[P09] map.Contains(k)    => %1   (1 = 存在)", b1);
		bool b2 = m.Contains("nope");
		PrintFormat("[P09] map.Contains(nope) => %1   (0 = 不存在)", b2);
	}
};
