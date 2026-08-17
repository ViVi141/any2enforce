// [C05] 回调机制：ScriptInvoker（Insert 注册 + Invoke 触发）
// 对应 VERIFY.md #16。语料 457 文件使用 ScriptInvoker；ScriptCaller 不存在。
// 判定：编译通过 + 输出 true = 回调机制确认（后续 lambda/回调映射用它）。

class C05_ScriptInvoker
{
	protected ref ScriptInvoker m_Event = new ScriptInvoker();
	protected bool m_bFired;

	void C05_ScriptInvoker()
	{
		m_Event.Insert(EventHandler);
	}

	void EventHandler()
	{
		m_bFired = true;
	}

	static void Check()
	{
		ref C05_ScriptInvoker inst = new C05_ScriptInvoker();
		inst.m_Event.Invoke();
		PrintFormat("[C05] ScriptInvoker 回调触发 => %1   (true = 正常)", inst.m_bFired);
	}
};
