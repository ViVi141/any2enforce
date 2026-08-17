# 实体处理模式（从 ANNA + Realistic-Stamina-System 学到）

> 证据来源：`ANNA`（自动驾驶，车辆驱动）、`Realistic-Stamina-System`（角色状态，modded
> 组件）、Reforger 官方脚本语料。这些是"如何覆盖/操作真实实体"的实测惯例，
> `training_lab_glue.c` 按此重写。

## 1. 组件挂到实体上

```c
class MyComponent : ScriptComponent          // 通用组件基类（GameLib/generated）
{
	override void OnPostInit(IEntity owner)  // 206+ 文件的标准钩子
	{
		super.OnPostInit(owner);
		m_Entity = owner;
		// 定时逻辑：CallLater(方法, 毫秒, repeat) —— 组件没有每帧虚函数，定时器是惯例
		GetGame().GetCallqueue().CallLater(Tick, 100, true);
	}
	void Tick() { }
}
```
- 编辑器里把组件加到实体上即可；也可用 `modded class` 给某类实体全局附加行为。

## 2. 实体位置与移动

```c
vector pos = entity.GetOrigin();      // 世界坐标（382 文件）
float x = pos[0]; float z = pos[2];   // Reforger 是 Y-up：地面平面 = XZ（[0] 与 [2]）

// 简单/脚本实体：直接平移
entity.SetOrigin(Vector(nx, ny, nz)); // 43 文件；对物理实体无效
```

## 3. 驱动车辆（ANNA 模式 —— 不要 SetOrigin）

```c
CarControllerComponent ctrl = CarControllerComponent.Cast(
	vehicle.FindComponent(CarControllerComponent));   // ANNA 标准取法
VehicleWheeledSimulation sim = ctrl.GetSimulation();
if (!sim.EngineIsOn())
	sim.EngineStart();
sim.SetSteering(steer);      // -1..1（注意：是 SetSteering，不是 SetSteer）
sim.SetThrottle(throttle);   // -1..1
sim.SetBreak(brake, handbrakeBool);   // 注意：引擎拼写是 SetBreak（不是 SetBrake）
```
- 真实车辆通过"注入驾驶输入"驱动，物理由引擎仿真；`VehicleWheeledSimulation` 还有
  `GetGear/SetGear/GetClutch/GetBrake` 等（`_reforger_code_full_v2/scripts/Game/generated/
  Vehicle/VehicleWheeledSimulation_SA_B.c`）。

## 4. 影响角色（RSS 模式）

```c
modded class SCR_CharacterControllerComponent { ... }      // 扩展角色的控制器
modded class SCR_CharacterStaminaComponent : CharacterStaminaComponent { ... }  // 状态组件

// 影响移动速度：只写 SetSpeedLimit(source, 绝对值)，不要单独 OverrideMaxSpeed
character.SetSpeedLimit(staminaSource, limit);   // SCR_ChimeraCharacter 方法
```
- RSS 的 `SCR_RSS_SpeedBridge.c` 注释明确："必须只写入独立 source 参与 min 合并；
  禁止再单独 OverrideMaxSpeed" —— 插件式 API 的正确用法。
- 组件字段类型（如 `SCR_CharacterStaminaComponent`）**不需要 ref**（RSS 16 处实证）。

## 5. 字段 ref 规则（本工具已按此实现）

| 字段类型 | ref 要求 | 证据 |
|---|---|---|
| `array/map/set` | **必须 `ref`** | 编译错误 `Variable 'm_aBufX' is not strong ref`；ANNA `protected static ref array<float> s_Means;` |
| 用户类 | `ref`（`ref Foo m_x;`） | ANNA `ref SCR_TimerEntryBase` |
| 组件类 | **不需要** `ref` | RSS `protected SCR_CharacterStaminaComponent m_pStaminaComponent;` ×16 |

## 6. 其他

- 实体查找：`GetGame().FindEntity("Name")`（按名字）；属性注入：`[Attribute("", UIWidgets.Object)]`。
- 全局函数名全项目唯一（无命名空间）；训练用全局 `lab_*` 需 `--prefix` 或手动加前缀。
