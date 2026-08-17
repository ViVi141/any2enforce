// [P09] map 成员测试写法验证（map.Contains 语料无先例）
// 逐个取消注释候选，单独编译：
//   候选 A：m.Contains(key)     —— 若编译过：Python `x in dict` 直接映射
//   候选 B：m.Get(key) != null  —— 回退方案（m.Get 有 505 文件先例）
// 注意：本文件属于"探测包"，请单独复制编译。

class P09_MapContains
{
	static void Check()
	{
		map<string, int> m = new map<string, int>();
		m["k"] = 1;

		// 候选 A：map.Contains
		//bool b1 = m.Contains("k");
		//PrintFormat("[P09] map.Contains(k) => %1   (true = 有 Contains)", b1);

		// 候选 B：Get 回退
		int v = m.Get("k");
		PrintFormat("[P09] m.Get(k) => %1   (1 = Get 可用)", v);
	}
};
