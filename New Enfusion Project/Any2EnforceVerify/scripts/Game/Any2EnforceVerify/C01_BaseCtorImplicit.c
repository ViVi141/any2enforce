// [C01] 基类默认构造是否隐式调用
// 对应 VERIFY.md #13b。语料中 super 显式构造调用 0 命中 -> 强假设：隐式调用。
// 判定：编译通过 + 输出 42 = 隐式调用成立（基类构造先于派生构造执行）。

class C01_Base
{
	int m_value;

	void C01_Base()
	{
		m_value = 42;
	}
}

class C01_Derived : C01_Base
{
	void C01_Derived()
	{
		PrintFormat("[C01] 派生构造内基类字段 m_value = %1   (42 = 隐式调用)", m_value);
	}

	static void Check()
	{
		ref C01_Derived d = new C01_Derived();
	}
};
