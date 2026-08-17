// [P03] 运算符重载探测 —— ✅ 已定案：不支持
// 实测记录：候选 B `operator+` 报 `Expected '(', not a '+'`（非法）；
//           候选 A `opAdd` / 候选 C `opEquals` 能编译，但仅作为普通方法名
//           （引擎是否接线到运算符无证据，全语料 0 用法）→ 按不支持处理。
// 若想彻底确认 opAdd 不接线运算符：取消注释"候选 D"再编译，
//   报错 = 确认不重载；通过 = 意外发现，务必记录。

class P03_OpOverload
{
	int m_x;

	// 候选 A：opAdd 风格（仅普通方法，可编译）
	//P03_OpOverload opAdd(P03_OpOverload other) { return other; }

	// 候选 B：operator 关键字 + 运算符名 —— ❌ 已确认非法
	//P03_OpOverload operator+(P03_OpOverload other) { return other; }

	// 候选 C：opEquals（仅普通方法，可编译）
	//bool opEquals(P03_OpOverload other) { return true; }

	// 候选 D：两个对象直接相加（若 opAdd 是运算符重载则编译通过）
	//static void Check()
	//{
	//	ref P03_OpOverload a = new P03_OpOverload();
	//	ref P03_OpOverload b = new P03_OpOverload();
	//	ref P03_OpOverload c = a + b;
	//}
};
