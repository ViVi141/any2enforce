// [P04] char / 字符类型探测 —— ✅ 已定案：EnforceScript 无 char 类型
// 实测记录：候选 A `char m_c;` 与候选 B `void SetChar(char c)` 均报
//           `Unknown type 'char'`（声明与参数都不行）；
//           候选 C `s[0]` 字符串下标可编译（返回 string，不是 char）。
// 若想确认字符串下标返回类型，取消注释"候选 C"运行 Check()。

class P04_CharType
{
	// 候选 A：char 类型声明 —— ❌ 已确认不存在
	//char m_c;

	// 候选 B：char 参数 —— ❌ 已确认不存在
	//void SetChar(char c) { }

	// 候选 C：字符串下标取字符（string.Get(i) 存在，[] 是否可用？）
	//static void Check()
	//{
	//	string s = "abc";
	//	PrintFormat("[P04] s[0] => '%1'", s[0]);
	//}
};
