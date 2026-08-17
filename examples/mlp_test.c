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
//         predict_behavior({ 0.1, -0.05, 0.4, 0.2 })
//
// 说明：predict_behavior 是全局函数，EnforceScript 无命名空间，任何类都能直接调用；
//       特征向量维度/含义取决于模型（演示版为 4 维占位值，换成你的真实特征即可）。
// ============================================================
class TestMLP
{
	static void Run()
	{
		array<float> feat = { 0.1, -0.05, 0.4, 0.2 };
		int behavior = predict_behavior(feat);
		PrintFormat("[MLP] behavior = %1   (类别索引，取决于模型)", behavior);
	}
};
