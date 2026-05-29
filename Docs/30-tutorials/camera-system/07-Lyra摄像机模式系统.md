---
id: 30-tutorials/camera-system/07-Lyra摄像机模式系统
title: Lyra摄像机模式系统
description: Lyra 的核心架构创新：用 CameraMode + Stack 替代引擎的 CameraModifier，实现灵活的多模式混合。
type: tutorial
status: current
language: zh
owner: ai
series: camera-system
lesson_index: 7
difficulty: advanced
prerequisites: ["[[30-tutorials/camera-system/06-LyraCameraComponent深度解析]]"]
tags: [lyra, camera-mode, camera-mode-stack, tutorial]
last_synced: 2026-05-19
engine_sources:
  - path: Engine/Source/Runtime/Engine/Classes/Camera/CameraTypes.h
    context: FMinimalViewInfo 定义
lyra_sources:
  - path: Source/LyraGame/Camera/LyraCameraMode.h
    context: ULyraCameraMode / ULyraCameraModeStack 完整定义
  - path: Source/LyraGame/Camera/LyraCameraMode.cpp
    context: ULyraCameraMode::UpdateCameraMode / GetPivotLocation 实现
  - path: Source/LyraGame/Camera/LyraCameraMode_ThirdPerson.h
    context: ULyraCameraMode_ThirdPerson 定义（穿透避免）
---

# Lyra摄像机模式系统

> Lyra 的核心架构创新：用 CameraMode + Stack 替代引擎的 CameraModifier，实现灵活的多模式混合。

## 概述

本课深入 Lyra 的摄像机模式（CameraMode）系统。学完本课你将理解：
- `ULyraCameraMode` 的生命周期（OnActivation / UpdateCameraMode / OnDeactivation）
- `ULyraCameraModeStack` 的混合算法（按权重 Blend）
- `FLyraCameraModeView::Blend()` 的具体插值方式
- `ULyraCameraMode_ThirdPerson` 的穿透避免算法
- 为什么这是比 `CameraModifier` 更灵活的架构

---

## 核心概念

### `ULyraCameraMode` —— 摄像机行为的「模式」

每个 CameraMode 定义了**一套完整的摄像机行为**：位置、旋转、FOV，以及这套行为的更新逻辑。

```
ULyraCameraMode（抽象基类）
  ├── ULyraCameraMode_ThirdPerson  （第三人称：有穿透避免）
  ├── ULyraCameraMode_FirstPerson  （第一人称：Attach 到头部 Socket）
  └── ULyraCameraMode_Vehicle       （载具模式：固定在载具上的 Camera）
```

**直觉理解**：CameraMode 就像「**镜头语言**」——每个 Mode 定义一种拍摄方式，Stack 负责把多种拍摄方式混合在一起。

### `ULyraCameraModeStack` —— 模式混合栈

```
Stack（数组，栈顶 = 最后一个元素）：
  [0] Mode_A（权重 0.6）← 主要模式
  [1] Mode_B（权重 0.4）← 叠加模式（如：受伤眩晕）
  [2] Mode_C（权重 0.0）← 非激活，不参与混合
```

每帧 `EvaluateStack()` 遍历 Stack，把所有 `BlendWeight > 0` 的 Mode 的 View 按权重混合。

---

## 源码深度分析

### `ULyraCameraMode::UpdateCameraMode()` —— 每帧更新

文件：`Source/LyraGame/Camera/LyraCameraMode.cpp`

```cpp
// [1] UpdateCameraMode 是每帧调用的核心函数
//     它先更新 BlendWeight（混合权重），再调用虚函数 UpdateView()
void ULyraCameraMode::UpdateCameraMode(float DeltaTime)
{
    // [1-1] 更新 BlendWeight（由 BlendAlpha 和 BlendFunction 计算）
    UpdateBlending(DeltaTime);

    // [1-2] 如果权重为 0，跳过视图更新（优化）
    if (BlendWeight <= 0.0f) return;

    // [1-3] ★ 调用虚函数 UpdateView()
    //     子类（如 ThirdPerson）在这里实现自己的摄像机逻辑
    UpdateView(DeltaTime);
}
```

**`UpdateView()` 的职责**（子类重写）：

```cpp
// [2] ULyraCameraMode_ThirdPerson::UpdateView()
//     计算「理想摄像机位置」，处理穿透避免
void ULyraCameraMode_ThirdPerson::UpdateView(float DeltaTime)
{
    // [2-1] 获取 Pivot（旋转中心 = 角色头部位置）
    FVector PivotLoc = GetPivotLocation();
    FRotator PivotRot = GetPivotRotation();

    // [2-2] ★ 根据 View Pitch 从曲线取 TargetOffset
    //     （ pitch 越大 → 摄像机越往后上方偏移，露出的角色身体越多）
    FVector TargetOffset = CalculateTargetOffsetFromCurve(PivotRot);

    // [2-3] 计算理想位置 = Pivot + Offset
    FVector DesiredLoc = PivotLoc + PivotRot.RotateVector(TargetOffset);

    // [2-4] ★ 穿透避免（核心特性）
    UpdatePreventPenetration(DeltaTime, DesiredLoc);

    // [2-5] 写入 this->View（最终产出）
    View.Location = DesiredLoc;
    View.Rotation = PivotRot;
    View.FieldOfView = FieldOfView;
}
```

### `FLyraCameraModeView::Blend()` —— 混合算法

文件：`Source/LyraGame/Camera/LyraCameraMode.cpp` [25-46]

```cpp
// [3] 两个 View 的混合（被 EvaluateStack() 调用）
void FLyraCameraModeView::Blend(const FLyraCameraModeView& Other, float OtherWeight)
{
    if (OtherWeight <= 0.0f) return;
    if (OtherWeight >= 1.0f)
    {
        *this = Other;  // 完全覆盖
        return;
    }

    // [3-1] Location：线性插值
    Location = FMath::Lerp(Location, Other.Location, OtherWeight);

    // [3-2] ★ Rotation：用 GetNormalized() 处理 360° 环绕
    //     例如：从 359° 到 1°，应该走 2° 而不是 358°
    FRotator DeltaRot = (Other.Rotation - Rotation).GetNormalized();
    Rotation = Rotation + (OtherWeight * DeltaRot);

    // [3-3] ControlRotation：同理处理环绕
    FRotator DeltaControlRot = (Other.ControlRotation - ControlRotation).GetNormalized();
    ControlRotation = ControlRotation + (OtherWeight * DeltaControlRot);

    // [3-4] FOV：线性插值
    FieldOfView = FMath::Lerp(FieldOfView, Other.FieldOfView, OtherWeight);
}
```

**设计决策分析**：为什么 Rotation 不用 `FMath::Lerp()` 而是手动处理 `GetNormalized()`？
> 因为 `FRotator` 的 `Yaw` 取值范围是 `[-180, 180]` 或 `[0, 360]`，直接 Lerp 会出现「长路径」问题（如：从 359° 到 1°，Lerp 会走 358° 而不是最短的 2°）。`GetNormalized()` 把差值规范化到 `[-180, 180]`，保证走最短路径。

### `ULyraCameraModeStack::EvaluateStack()` —— 栈评估

```cpp
// [4] 遍历 Stack，按权重混合所有激活的 Mode
bool ULyraCameraModeStack::EvaluateStack(float DeltaTime, FLyraCameraModeView& OutView)
{
    // [4-1] 先让所有 Mode 更新自己的 View
    for (ULyraCameraMode* Mode : CameraModeStack)
    {
        Mode->UpdateCameraMode(DeltaTime);
    }

    // [4-2] 从栈底开始混合（栈底 = 最旧/最主的模式）
    FLyraCameraModeView CombinedView = ZeroInitialized;
    for (int32 i = 0; i < CameraModeStack.Num(); i++)
    {
        ULyraCameraMode* Mode = CameraModeStack[i];
        if (Mode->GetBlendWeight() <= 0.0f) continue;

        if (i == 0)
        {
            CombinedView = Mode->GetCameraModeView();  // 第一个：直接取
        }
        else
        {
            CombinedView.Blend(Mode->GetCameraModeView(), Mode->GetBlendWeight());
        }
    }

    OutView = CombinedView;
    return true;
}
```

---

## Lyra 实践

### `ULyraCameraMode_ThirdPerson` 的穿透避免

这是 Lyra Camera 系统最复杂的部分。核心思路：**多条射线检测障碍物，平滑推开 Camera**。

```
穿透避免流程：
  1. 计算理想位置（无碰撞时）
  2. 从理想位置向角色发射「主射线」
     - 如果命中 → Camera 拉近
  3. 从角色向多个方向发射「预测射线」
     - 如果命中 → 提前把 Camera 推开（防止突然穿墙）
  4. 用指数衰减平滑过渡（避免抖动）
```

**`FLyraPenetrationAvoidanceFeeler` 结构体**：

```cpp
// 文件：Source/LyraGame/Camera/LyraPenetrationAvoidanceFeeler.h
struct FLyraPenetrationAvoidanceFeeler
{
    float TraceRadius;       // 射线半径（球形 Trace）
    float TraceLength;        // 射线长度
    float PenetrationBlendIn;  // 拉入时的混合时间
    float PenetrationBlendOut; // 推出时的混合时间
    FVector Direction;        // 射线方向（局部坐标，相对于 Camera 朝向）
};
```

**为什么用多条射线而不是 `USpringArmComponent` 的单球 Trace？**

| 方案 | 优点 | 缺点 |
|------|------|------|
| `USpringArmComponent`（单球 Trace） | 简单，性能好 | 穿墙时 Camera 直接缩到角色体内，视觉差 |
| Lyra（多条射线） | 可以「横向推开」Camera，保持可见性；预测射线防止突然穿墙 | 实现复杂，性能略差 |

### `bDoPredictiveAvoidance` 的作用

当 `bDoPredictiveAvoidance = true` 时，除了主射线（Index 0），还会发射多条**预测射线**（Index 1+）。

**直觉理解**：就像开车时不仅看正前方，还看「如果我现在转向，会不会撞墙」——预测射线提前把 Camera 推开，避免突然穿墙的「抖动感」。

---

## 常见问题与陷阱

### 1. CameraMode 切换时没有平滑过渡？

**原因**：`ULyraCameraMode::BlendTime` 为 0（默认 0.5f，但可能被覆盖为 0）。

**解决**：在 CameraMode 的 Blueprint 子类中，设置 `BlendTime = 0.2f`（200ms 过渡）。

### 2. 穿透避免导致 Camera 抖动？

**原因**：射线检测频率太高（每帧），当障碍物边缘不规则时会出现抖动。

**解决**：
```cpp
// 在 ULyraCameraMode_ThirdPerson 的子类中：
PenetrationBlendInTime = 0.1f;   // 拉入时慢一点
PenetrationBlendOutTime = 0.15f;  // 推出时更慢（更平滑）
```

### 3. 多个 CameraMode 同时激活时，旋转混合出现「万向锁」？

**原因**：`FRotator` 的 `GetNormalized()` 在 Pitch 接近 ±90° 时会出现万向锁。

**解决**：在 `UpdateView()` 中使用 `FQuat` 做旋转插值，而不是 `FRotator`。Lyra 的默认实现已经处理了这个问题（用 `GetNormalized()`）。

---

## 总结与要点

| # | 要点 | 说明 |
|---|------|------|
| 1 | `ULyraCameraMode` 是摄像机行为的抽象 | 每个 Mode 定义一套完整的位置/旋转/FOV 计算逻辑 |
| 2 | `ULyraCameraModeStack` 管理多模式混合 | 按权重线性混合 Location/Rotation/FOV |
| 3 | `FLyraCameraModeView::Blend()` 处理旋转环绕 | 用 `GetNormalized()` 避免 360° 长路径问题 |
| 4 | `ULyraCameraMode_ThirdPerson` 用多条射线避免穿透 | 比 `USpringArmComponent` 更稳定，支持预测避免 |
| 5 | Lyra 的架构比 `CameraModifier` 更灵活 | 每个 Mode 可以完全替换摄像机行为，而不是「后处理叠加」 |

---

## 相关页面

- [[30-tutorials/camera-system/06-LyraCameraComponent深度解析]] ← 上一课：LyraCameraComponent 深度解析
- [[30-tutorials/camera-system/08-Lyra摄像机与ExperiencePawnData集成]] → 下一课：Lyra 摄像机与 Experience/PawnData 集成

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/camera-system/06-LyraCameraComponent深度解析|06-LyraCameraComponent深度解析]] · [[30-tutorials/camera-system/08-Lyra摄像机与ExperiencePawnData集成|08-Lyra摄像机与ExperiencePawnData集成]] →

<!-- /nav:auto -->
