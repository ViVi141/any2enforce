// [P05] 浮点指数写法逐个验证（V04 首轮编译已发现 1E30 非法）
// 一次编译本文件，按报错行号判断哪个形式非法；注释掉非法行后重试。
// 注意：本文件属于"探测包"，请单独复制编译，勿与 Any2EnforceVerify 混编。

class P05_FloatLiteralExponent
{
	static void Check()
	{
		float a = 1e+30;   // 候选 1：小写 e + 符号（V04 已验证通过）
		PrintFormat("[P05] 1e+30  => %1", a);

		float b = 1.0e30;  // 候选 2：小数点 + 小写 e（V04 已验证通过）
		PrintFormat("[P05] 1.0e30 => %1", b);

		float c = 1e30;    // 候选 3：小写 e 无符号
		PrintFormat("[P05] 1e30   => %1", c);

		float d = 1.0E30;  // 候选 4：小数点 + 大写 E
		PrintFormat("[P05] 1.0E30 => %1", d);
	}
};
