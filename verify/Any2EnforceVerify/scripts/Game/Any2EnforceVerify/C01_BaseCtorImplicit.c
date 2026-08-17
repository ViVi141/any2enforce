// [C01] 基类默认构造是否隐式调用
// 对应 VERIFY.md #13b。语料中 super 显式构造调用 0 命中 -> 强假设：隐式调用。
// 判定：编译通过 + 输出 42 = 隐式调用成立（基类构造先于派生构造执行）。
// 注意：类名与文件名保持一致（C01_BaseCtorImplicit），VerifyEntry 调用
//       C01_BaseCtorImplicit.Check()。

class C01_BaseCtorImplicitBase
{
	int m_value;

	void C01_BaseCtorImplicitBase()
	{
		m_value = 42;
	}
}

class C01_BaseCtorImplicit : C01_BaseCtorImplicitBase
{
	void C01_BaseCtorImplicit()
	{
		PrintFormat("[C01] 派生构造内基类字段 m_value = %1   (42 = 隐式调用)", m_value);
	}

	static void Check()
	{
		ref C01_BaseCtorImplicit d = new C01_BaseCtorImplicit();
	}
};
