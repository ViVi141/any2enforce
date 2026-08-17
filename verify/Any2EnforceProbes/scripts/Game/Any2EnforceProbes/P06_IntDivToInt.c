// [P06] int = int / int（V01 已确认 float f = 7 / 2 可编译，但赋给 int 待验证）
// 判定：编译通过 → int 直接收 int/int（输出 3 或 4）；
//       编译失败 → float→int 需显式强转 (int)，工具需在 `a // b` 处加 (int)。
// 注意：本文件属于"探测包"，请单独复制编译。

class P06_IntDivToInt
{
	static void Check()
	{
		int i = 7 / 2;
		PrintFormat("[P06] int i = 7 / 2 => %1   (3 = 截断 / 4 = 四舍五入)", i);
	}
};
