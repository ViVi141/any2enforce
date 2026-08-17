// [V03] 字符串转义（确定项：\t \n，语料先例 "\t" + msg）
// \u0041 / \x41 / \0 等不确定转义移到探测包 P08 单独验证。

class V03_StringEscapes
{
	static void Check()
	{
		string s1 = "tab\there";
		PrintFormat("[V03] \\t => '%1'   (tab空格here = 合法)", s1);

		string s2 = "line1\nline2";
		PrintFormat("[V03] \\n => '%1'", s2);
	}
};
