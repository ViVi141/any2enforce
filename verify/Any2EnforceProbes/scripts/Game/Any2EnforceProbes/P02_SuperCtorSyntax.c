// [P02] 显式基类构造语法探测（配合 P01：若 P01 编译失败才需要本文件）
// 逐个取消注释一个"候选"，单独编译一次，记录哪个能通过。
// 注意：本文件属于"探测包"，每次只测一个候选。

class P02_Base
{
	int m_value;

	void P02_Base(int value)
	{
		m_value = value;
	}
}

class P02_Derived : P02_Base
{
	void P02_Derived()
	{
		// 候选 A：super() 空调用
		//super();

		// 候选 B：super.基类名(参数)
		//super.P02_Base(5);

		// 候选 C：直接用基类名调用
		//P02_Base(5);

		PrintFormat("[P02] m_value = %1", m_value);
	}
};
