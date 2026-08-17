// ============================================================
// TestMLP.c — 调用 any2enforce 生成的 predict_behavior 的示例入口
//
// 用法：
//   1) 把 mlp_forward.c（工具生成的 MLP 前向）和本文件一起放进
//      addon 的 scripts/ 下（同一次编译即可互相可见），ValidateScripts 应 0 错误；
//   2) 运行（三选一）：
//      a) 游戏内控制台（~）：execCode TestMLP.Run()
//      b) 复用 RunOnGameStart.c：在 override void OnGameStart() 里加一行 TestMLP.Run();
//      c) 直接在 execCode 里试表达式（内联数组实参已验证合法）：
//         predict_behavior({ 1.0, 1.0, 1.0, 1.0 })
//
// 说明：predict_behavior 是全局函数，EnforceScript 无命名空间，任何类都能直接调用；
//       特征向量维度/含义取决于模型（演示版为 4 维）。
// ============================================================
class TestMLP
{
	static void Run()
	{
		// 批量数值对拍：与 Python 参考实现的期望值对比
		//   [ 1, 1, 1, 1]  -> 0     [-1, 1, 0, 0]  -> 1     [ 0, 0,-1, 1] -> 2
		//   [-1,-1,-1,-1]  -> 1     [ 1,-1, 1,-1]  -> 0     [ 0.5,-0.5,0,0]-> 0
		//   [ 0.1,-0.05,0.4,0.2] -> 0     [ 0.9,-0.8,0.7,0.3] -> 0
		CheckVector("T1", { 1.0, 1.0, 1.0, 1.0 }, 0);
		CheckVector("T2", { -1.0, 1.0, 0.0, 0.0 }, 1);
		CheckVector("T3", { 0.0, 0.0, -1.0, 1.0 }, 2);
		CheckVector("T4", { -1.0, -1.0, -1.0, -1.0 }, 1);
		CheckVector("T5", { 1.0, -1.0, 1.0, -1.0 }, 0);
		CheckVector("T6", { 0.5, -0.5, 0.0, 0.0 }, 0);
		CheckVector("T7", { 0.1, -0.05, 0.4, 0.2 }, 0);
		CheckVector("T8", { 0.9, -0.8, 0.7, 0.3 }, 0);
	}

	static void CheckVector(string tag, array<float> feat, int expected)
	{
		int behavior = predict_behavior(feat);
		string verdict = "FAIL";
		if (behavior == expected)
			verdict = "PASS";
		PrintFormat("[MLP] %1 => %2   (期望 %3)  %4", tag, behavior, expected, verdict);
	}
};
