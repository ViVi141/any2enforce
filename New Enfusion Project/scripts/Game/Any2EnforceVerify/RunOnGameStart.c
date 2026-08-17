// RunOnGameStart.c — 免控制台自触发入口（方案 A）
// 游戏模式启动时自动执行 VerifyEntry.Run()，结果打印到游戏控制台日志。
// 用法：和 VerifyEntry.c 一起放在 scripts/Game/Any2EnforceVerify/ 下，编译后
//       直接进游戏（Play / 运行任务）即可，无需 execCode。
// 前提：任务里有 GameMode（标准 Conflict/CombatOps 任务都有）。
// 备选：若你的 addon 已有组件，也可以在任意组件的 OnPostInit 里加一行
//       VerifyEntry.Run(); 然后删掉本文件。

modded class SCR_BaseGameMode
{
	override void OnGameStart()
	{
		super.OnGameStart();
		VerifyEntry.Run();
	}
};
