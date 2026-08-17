// [P04] char / 字符类型探测
// 语料中 char 仅出现在注释里（FilePath.c 的文档）-> 预期 EnforceScript 无 char。
// 逐个取消注释一个"候选"，单独编译一次，记录哪个能通过。
// 注意：本文件属于"探测包"，预期失败，请单独复制。

class P04_CharType
{
	// 候选 A：char 类型声明
	//char m_c;

	// 候选 B：char 参数
	//void SetChar(char c) { }

	// 候选 C：字符串下标取字符（string.Get(i) 存在，[] 是否可用？）
	//string GetChar(string s) { return s[0]; }
};
