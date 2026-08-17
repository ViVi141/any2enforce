// [V03] 字符串转义：\uXXXX / \xXX / \0 / \t
// 对应 VERIFY.md #21
// 若某一行编译失败：逐行注释定位不支持哪种转义，并把结论记入 VERIFY.md。

class V03_StringEscapes
{
	static void Check()
	{
		string s1 = "A\u0041B";
		PrintFormat("[V03] \\u0041 => '%1'   (AAB = 合法)", s1);

		string s2 = "A\x41B";
		PrintFormat("[V03] \\x41  => '%1'   (AAB = 合法)", s2);

		string s3 = "a\0b";
		PrintFormat("[V03] \\0 长度 => %1   (2 = 截断, 3 = 保留)", s3.Length());

		string s4 = "tab\there";
		PrintFormat("[V03] \\t  => '%1'   (tab空格here = 合法)", s4);
	}
};
