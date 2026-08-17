// [V05] 内联数组实参 { ... }（语料已见 GetCaseParentSuites({...})，此处运行时确认）
// 影响：若合法，v0.2 可支持把 Python 列表字面量直接作为实参，
//      而不仅限于赋值场景（当前 v0.1 限制）。

class V05_InlineArrayArg
{
	static int Sum(array<int> xs)
	{
		int total = 0;
		foreach (int x : xs)
		{
			total += x;
		}
		return total;
	}

	static void Check()
	{
		int s = Sum({ 1, 2, 3 });
		PrintFormat("[V05] Sum({1,2,3}) => %1   (6 = 内联实参合法)", s);
	}
};
