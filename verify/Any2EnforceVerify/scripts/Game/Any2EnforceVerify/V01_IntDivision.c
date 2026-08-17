// [V01] int/int 除法：结果类型与值
// 对应 VERIFY.md #6（工具当前映射：`a // b` -> Math.Floor(a / b)）
// 预期：
//   - "float f = 7 / 2" 输出 3.5  -> EnforceScript 的 / 是 float 除法
//   - "int i = 7 / 2"    能编译且输出 3 或 4 -> int 赋值做了截断/舍入（记录哪个）
//   - 若 "int i = 7 / 2" 编译失败 -> float->int 不允许隐式转换（重要结论）

class V01_IntDivision
{
	static void Check()
	{
		float f = 7 / 2;
		PrintFormat("[V01] float f = 7 / 2     => %1   (3.5 = float 除法)", f);

		// 若这一行编译失败，注释掉并记录：
		int i = 7 / 2;
		PrintFormat("[V01] int i = 7 / 2       => %1   (3 = 截断, 4 = 四舍五入)", i);

		float floored = Math.Floor(7.0 / 2.0);
		PrintFormat("[V01] Math.Floor(7.0/2.0) => %1   (应为 3)", floored);
	}
};
