// [P08] 不确定字符串转义逐个验证（\uXXXX / \xXX / \0）
// 一次编译本文件，按报错行号定位非法转义；注释掉非法行后重试。
// 注意：本文件属于"探测包"，请单独复制编译。

class P08_StringEscapes
{
	static void Check()
	{
		string s1 = "A\u0041B";
		PrintFormat("[P08] \\u0041 => '%1'   (AAB = 合法)", s1);

		string s2 = "A\x41B";
		PrintFormat("[P08] \\x41  => '%1'   (AAB = 合法)", s2);

		string s3 = "a\0b";
		PrintFormat("[P08] \\0 长度 => %1   (2 = 截断 / 3 = 保留)", s3.Length());
	}
};
