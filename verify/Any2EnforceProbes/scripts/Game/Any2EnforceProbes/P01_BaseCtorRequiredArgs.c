// [P01] 基类构造带必选参数：派生类是否必须显式调用？
// 对应 VERIFY.md #13b 的边界情况。逐个文件复制到 addon 编译：
//   - 本文件若编译失败 -> 参数化基类构造必须显式调用（需 P02 找语法）
//   - 本文件若编译通过 -> 参数化基类构造可被忽略（记录输出值）
// 注意：本文件属于"探测包"，预期可能失败，请单独复制，勿与
// Any2EnforceVerify 包混在一起编译。

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
	void P01_BaseCtorRequiredArgs()
	{
		PrintFormat("[P01] m_value = %1", m_value);
	}
};
