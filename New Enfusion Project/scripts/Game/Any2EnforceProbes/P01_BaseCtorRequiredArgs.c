// [P01] 基类构造带必选参数 —— ✅ 已定案（编译报错 "Overloaded function not
//       compatible" + 语料 SCR_TimerEntries.c 双重证据）
// 结论：EnforceScript 无显式 super 构造调用语法；派生构造按参数名隐式转发
//       给基类构造。基类 P01_BaseCtorRequiredArgsBase(int value) 要求必选
//       参数 value，因此派生构造必须声明 int value。
// 本文件即正确写法：预期编译通过；运行 Check() 应输出 5。

class P01_BaseCtorRequiredArgsBase
{
	int m_value;

	void P01_BaseCtorRequiredArgsBase(int value)
	{
		m_value = value;
	}
}

class P01_BaseCtorRequiredArgs : P01_BaseCtorRequiredArgsBase
{
	void P01_BaseCtorRequiredArgs(int value)
	{
		PrintFormat("[P01] m_value = %1   (5 = 隐式转发定案)", m_value);
	}

	static void Check()
	{
		ref P01_BaseCtorRequiredArgs d = new P01_BaseCtorRequiredArgs(5);
	}
};
