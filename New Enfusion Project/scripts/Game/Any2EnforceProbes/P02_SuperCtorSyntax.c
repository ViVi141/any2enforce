// [P02] 显式基类构造语法探测 —— ✅ 已定案：不存在显式语法
// 实测记录：候选 A `super();`、候选 B `super.基类名(5);`、候选 C `基类名(5);`
//           均报 "Overloaded function not compatible"（报错在派生构造签名行）。
// 结论（语料 SCR_TimerEntries.c 佐证）：派生构造声明与基类同名的必选参数，
//       编译器隐式转发；无显式 super 调用。
// 本文件即正确写法：预期编译通过；运行 Check() 应输出 5。

class P02_SuperCtorSyntaxBase
{
	int m_value;

	void P02_SuperCtorSyntaxBase(int value)
	{
		m_value = value;
	}
}

class P02_SuperCtorSyntax : P02_SuperCtorSyntaxBase
{
	void P02_SuperCtorSyntax(int value)
	{
		PrintFormat("[P02] m_value = %1   (5 = 隐式转发定案)", m_value);
	}

	static void Check()
	{
		ref P02_SuperCtorSyntax d = new P02_SuperCtorSyntax(5);
	}
};
