// ============================================================
// TrainingLabGlue.c — 把训练实验室接到真实实体上（v2：真实实体模式版）
//
// 依赖：training_lab.c（any2enforce 生成）的全局函数：
//   lab_init / lab_forward / lab_train_step / lab_teacher
//
// 实体模式学自 ANNA（车辆驱动）与 Realistic-Stamina-System（组件惯例），
// 详见 examples/entity_patterns.md。两个变体：
//   TrainingLabComponent         — 简单/脚本实体：SetOrigin 平移
//   TrainingLabVehicleComponent  — 车辆实体：注入转向/油门（ANNA 模式）
//
// 用法（WorldEditor）：
//   1) 场景放两个实体：学员实体（挂上面任一组件）+ 目标实体；
//   2) 组件属性 m_Target 选目标（或命名目标实体为 "LabTarget" 自动查找）；
//   3) 运行任务 → 学员实体被"正在学习"的模型驱动去追目标，
//      控制台每 10 个 tick 打印 loss / 准确率 / 追击误差。
// ============================================================

class TrainingLabBase : ScriptComponent
{
	[Attribute("", UIWidgets.Object)]
	protected IEntity m_Target;

	protected IEntity m_Entity;
	protected float m_fTick;

	// 训练缓冲（布局与 training_lab.py 一致：每样本 4 特征 + 4 维 one-hot + 类别）
	// array/map/set 字段必须 ref（编译错误实证；ANNA: protected static ref array<float>）
	protected ref array<float> m_aBufX = {};
	protected ref array<float> m_aBufY = {};
	protected ref array<int> m_aLabels = {};

	protected ref array<float> m_W1 = new array<float>();
	protected ref array<float> m_B1 = new array<float>();
	protected ref array<float> m_W2 = new array<float>();
	protected ref array<float> m_B2 = new array<float>();

	//------------------------------------------------------------------------------------------------
	override void OnPostInit(IEntity owner)
	{
		super.OnPostInit(owner);
		m_Entity = owner;
		if (!m_Target)
			m_Target = GetGame().FindEntity("LabTarget");

		lab_init(m_W1, m_B1, m_W2, m_B2);
		GetGame().GetCallqueue().CallLater(Tick, 100, true);
	}

	//------------------------------------------------------------------------------------------------
	void Tick()
	{
		if (!m_Entity || !m_Target)
			return;

		vector targetPos = m_Target.GetOrigin();
		vector ownPos = m_Entity.GetOrigin();
		// Reforger 是 Y-up：地面追击在 XZ 平面（[0] 与 [2]）
		float dx = targetPos[0] - ownPos[0];
		float dy = targetPos[2] - ownPos[2];

		// 1) 特征（与 lab 相同：dx/100, dy/100, 1, 0；真实世界尺度大时改除数为场景尺度）
		array<float> feat = { dx / 100.0, dy / 100.0, 1.0, 0.0 };

		// 2) 前 50 个 tick 由 teacher 开车收集干净数据，之后换模型决策
		int action;
		if (m_fTick < 50)
			action = lab_teacher(dx, dy);
		else
			action = ArgMax(lab_forward(feat, m_W1, m_B1, m_W2, m_B2));

		// 3) 驱动实体（子类覆写 ApplyAction：简单实体平移 / 车辆注入输入）
		ApplyAction(action);

		// 4) 采样入缓冲（teacher 标签基于当前相对位置）
		AppendSample(feat, lab_teacher(dx, dy));

		// 5) 每 10 个 tick 训一轮 + 遥测
		m_fTick = m_fTick + 1;
		if (((int)m_fTick) % 10 == 0)
		{
			TrainBurst();
			PrintTelemetry(dx, dy);
		}
	}

	//------------------------------------------------------------------------------------------------
	void ApplyAction(int action)
	{
		// 由子类覆写：动作 0=-X, 1=+X, 2=-Z, 3=+Z
	}

	//------------------------------------------------------------------------------------------------
	void AppendSample(array<float> feat, int label)
	{
		m_aBufX.Insert(feat[0]);
		m_aBufX.Insert(feat[1]);
		m_aBufX.Insert(feat[2]);
		m_aBufX.Insert(feat[3]);
		m_aBufY.Insert(0.0);
		m_aBufY.Insert(0.0);
		m_aBufY.Insert(0.0);
		m_aBufY.Insert(0.0);
		m_aBufY[m_aBufY.Count() - 4 + label] = 1.0;
		m_aLabels.Insert(label);

		if (m_aLabels.Count() > 200)
		{
			m_aBufX.Clear();
			m_aBufY.Clear();
			m_aLabels.Clear();
		}
	}

	//------------------------------------------------------------------------------------------------
	void TrainBurst()
	{
		int n = m_aLabels.Count();
		if (n < 1)
			return;

		for (int s = 0; s < n; s++)
		{
			array<float> x = { m_aBufX[s * 4 + 0], m_aBufX[s * 4 + 1],
				m_aBufX[s * 4 + 2], m_aBufX[s * 4 + 3] };
			array<float> y = { m_aBufY[s * 4 + 0], m_aBufY[s * 4 + 1],
				m_aBufY[s * 4 + 2], m_aBufY[s * 4 + 3] };
			for (int e = 0; e < 8; e++)
				lab_train_step(x, y, m_W1, m_B1, m_W2, m_B2, 0.1);
		}
	}

	//------------------------------------------------------------------------------------------------
	void PrintTelemetry(float dx, float dy)
	{
		int n = m_aLabels.Count();
		if (n < 1)
			return;

		int acc = 0;
		for (int s = 0; s < n; s++)
		{
			array<float> x = { m_aBufX[s * 4 + 0], m_aBufX[s * 4 + 1],
				m_aBufX[s * 4 + 2], m_aBufX[s * 4 + 3] };
			if (ArgMax(lab_forward(x, m_W1, m_B1, m_W2, m_B2)) == m_aLabels[s])
				acc = acc + 1;
		}

		float err = dx;
		if (err < 0.0)
			err = -dx;
		float ey = dy;
		if (ey < 0.0)
			ey = -dy;

		PrintFormat("[Lab] tick=%1  acc=%2%%  err=%3", (int)m_fTick,
			acc * 100 / n, err + ey);
	}

	//------------------------------------------------------------------------------------------------
	int ArgMax(array<float> probs)
	{
		int best = 0;
		float bestP = probs[0];
		for (int ci = 1; ci < probs.Count(); ci++)
		{
			if (probs[ci] > bestP)
			{
				bestP = probs[ci];
				best = ci;
			}
		}
		return best;
	}
};

// ============================================================
// 变体 1：简单/脚本实体 —— SetOrigin 平移（43 文件惯例）
// ============================================================
class TrainingLabComponent : TrainingLabBase
{
	override void ApplyAction(int action)
	{
		vector ownPos = m_Entity.GetOrigin();
		float nx = ownPos[0];
		float nz = ownPos[2];
		if (action == 0)
			nx = nx - 2.0;
		else if (action == 1)
			nx = nx + 2.0;
		else if (action == 2)
			nz = nz - 2.0;
		else
			nz = nz + 2.0;
		m_Entity.SetOrigin(Vector(nx, ownPos[1], nz));
	}
};

// ============================================================
// 变体 2：车辆实体 —— 注入驾驶输入（ANNA ApplyManeuverInputs 模式）
// 注意：车辆是物理仿真，不能 SetOrigin；通过转向/油门输入驱动。
//       动作映射为：0/1 大幅转向，2 直行加速，3 倒车。
// ============================================================
class TrainingLabVehicleComponent : TrainingLabBase
{
	protected CarControllerComponent m_Controller;  // 组件字段不需要 ref（RSS 实证）

	override void OnPostInit(IEntity owner)
	{
		super.OnPostInit(owner);
		m_Controller = CarControllerComponent.Cast(
			m_Entity.FindComponent(CarControllerComponent));
	}

	override void ApplyAction(int action)
	{
		if (!m_Controller)
			return;

		VehicleWheeledSimulation sim = m_Controller.GetSimulation();
		if (!sim.EngineIsOn())
			sim.EngineStart();

		float steer = 0;
		float throttle = 0.6;
		if (action == 0)
			steer = -1.0;
		else if (action == 1)
			steer = 1.0;
		else if (action == 3)
			throttle = -0.4;

		sim.SetSteering(steer);   // 引擎 API：SetSteering（不是 SetSteer）
		sim.SetThrottle(throttle);
	}
};
