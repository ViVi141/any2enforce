// [P03] 运算符重载探测
// 对应 VERIFY.md #15。语料中 opAdd/opEquals 等 0 命中 -> 预期不支持。
// 逐个取消注释一个"候选"，单独编译一次，记录哪个能通过。
// 注意：本文件属于"探测包"，预期失败，请单独复制。

class P03_Vec
{
	int m_x;

	// 候选 A：opAdd 风格（类似 C#/SQF 命名惯例）
	//P03_Vec opAdd(P03_Vec other) { return other; }

	// 候选 B：operator 关键字 + 运算符名
	//P03_Vec operator+(P03_Vec other) { return other; }

	// 候选 C：opEquals（等值比较重载）
	//bool opEquals(P03_Vec other) { return true; }
};
