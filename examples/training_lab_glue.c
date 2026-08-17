// ============================================================
// TrainingLabGlue.c — 把训练实验室接到真实实体上
//
// 依赖：training_lab.c（any2enforce 生成）的全局函数：
//   lab_init / lab_forward / lab_train_step / lab_teacher
//
// 用法（WorldEditor）：
//   1) 场景放两个实体：学员实体（挂本组件）+ 目标实体；
//   2) 组件属性 m_Target 选目标实体（或把目标实体命名为 "LabTarget"，
//      在 OnPostInit 里按名字自动查找）；
//   3) 运行任务 → 学员实体会被"正在学习"的模型驱动去追目标，
//      控制台每 10 个 tick 打印 loss / 准确率 / 追击误差。
//
// 设计：这是"接真实世界"的最小壳 —— 特征/标签/训练/决策全部复用已转好的
// lab_* 函数，本文件只做三件事：取实体位置、喂数据、驱动实体。
// 替换目标/载具时，只改 Tick() 里取位置和移动实体的两处。
// ============================================================
class TrainingLabComponent : ScriptComponent
{
	[Attribute("", UIWidgets.Object)]
	protected IEntity m_Target;

	protected IEntity m_Entity;
	protected float m_fTick;

	// 训练缓冲（布局与 training_lab.py 一致：每样本 4 特征 + 4 维 one-hot + 类别）
	// 注意：array/map/set 字段必须 ref（EnforceScript 强引用要求）
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

		// 3) 驱动实体：教学壳直接 SetOrigin 平移（换车辆/角色请用其移动 API）
		//    动作：0=-X, 1=+X, 2=-Z, 3=+Z
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
