---
id: 30-tutorials/pcg/05-常用PCG节点详解
title: 常用PCG节点详解
description: "PCG内置50+节点详解，涵盖采样、变换、过滤、生成等常用节点的使用方法和组合技巧"
type: tutorial
status: current
language: zh
owner: ai
series: pcg
lesson_index: 5
difficulty: intermediate
prerequisites: [30-tutorials/pcg/04-pcg-graph-basics]
tags: [pcg, nodes, surface-sampler, static-mesh-spawner]
last_synced: 2026-05-17
---

# 常用PCG节点详解

> **前置知识**：[04-PCG 图表基础](./04-PCG图表基础.md)
> **预计阅读时间**：35 分钟

## 概念直觉

### PCG 节点 = 数据处理单元

PCG 内置了 **50+ 个节点**，覆盖常见需求：

```
[输入] → [采样] → [变换] → [过滤] → [生成] → [输出]
         ↑           ↑           ↑           ↑
    Surface     Transform    Filter    Mesh Spawner
    Sampler     Points       Points
```

**核心节点分类**：
1. **输入类**：Surface Sampler、Create Points
2. **变换类**：Transform Points、Modify Points
3. **过滤类**：Filter Points、Density Filter
4. **生成类**：Static Mesh Spawner、Actor Spawner
5. **调试类**：Debug Draw、Print Points

---

## 技术机制

### 1. Surface Sampler — 表面采样器

**源码位置**：`Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGSurfaceSampler.h`

#### 功能

在 **表面**（地形、静态网格）上采样点。

#### 参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `Density` | `float` | 点密度（每立方米点数） |
| `Bounds Modifier` | `TSoftObjectPtr<AActor>` | 采样范围（通常是 PCG Volume） |
| `Loose Bounds` | `FVector` | 松散边界（扩大采样范围） |
| `bUseLandscape` | `bool` | 是否使用地形 |
| `bUseStaticMesh` | `bool` | 是否使用静态网格 |

#### 执行逻辑（简化版）

```cpp
// PCGSurfaceSampler.cpp
TArray<FPCGTaggedData> UPCGSurfaceSamplerSettings::Execute(
    const TArray<FPCGTaggedData>& InputData,
    const FPCGExecutionContext& Context) const
{
    TArray<FPCGTaggedData> OutputData;

    // 1. 获取采样范围
    FBox Bounds = GetBounds(Context.Component);

    // 2. 计算点数
    int32 NumPoints = Density * Bounds.GetVolume();

    // 3. 采样表面
    TArray<FPCGPoint> Points;
    for (int32 i = 0; i < NumPoints; ++i)
    {
        // 3.1 随机位置
        FVector Location = FMath::RandPointInBox(Bounds);

        // 3.2 投影到表面
        FVector ProjectedLocation = ProjectToSurface(Location);

        // 3.3 创建点
        FPCGPoint Point;
        Point.Transform.SetLocation(ProjectedLocation);
        Point.Density = 1.0f;

        Points.Add(Point);
    }

    // 4. 创建点数据
    UPCGPointData* PointData = NewObject<UPCGPointData>();
    PointData->SetPoints(Points);

    // 5. 返回
    FPCGTaggedData TaggedData;
    TaggedData.Data = PointData;
    OutputData.Add(TaggedData);

    return OutputData;
}
```

**关键发现**：
- `Density` 是 **密度**，不是 **数量**
- `ProjectToSurface()` 是关键（将随机点投影到表面）
- 输出包含 `Point` + `Surface`（传递给下游）

---

### 2. Transform Points — 变换点

**源码位置**：`Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGTransformPoints.h`

#### 功能

批量修改点的 **位置、旋转、缩放**。

#### 参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `Location Min/Max` | `FVector` | 位置偏移范围 |
| `Rotation Min/Max` | `FRotator` | 旋转范围 |
| `Scale Min/Max` | `FVector` | 缩放范围 |
| `bUniformScale` | `bool` | 是否均匀缩放 |

#### 执行逻辑（简化版）

```cpp
// PCGTransformPoints.cpp
TArray<FPCGTaggedData> UPCGTransformPointsSettings::Execute(
    const TArray<FPCGTaggedData>& InputData,
    const FPCGExecutionContext& Context) const
{
    TArray<FPCGTaggedData> OutputData;

    for (const FPCGTaggedData& TaggedData : InputData)
    {
        const UPCGPointData* PointData = Cast<UPCGPointData>(TaggedData.Data);
        if (!PointData) continue;

        // 创建新的点数据
        UPCGPointData* NewPointData = NewObject<UPCGPointData>();

        // 遍历所有点
        for (const FPCGPoint& Point : PointData->GetPoints())
        {
            FPCGPoint NewPoint = Point;

            // 随机位置偏移
            FVector LocationOffset = FMath::RandPointInBox(FBox(LocationMin, LocationMax));
            NewPoint.Transform.AddToTranslation(LocationOffset);

            // 随机旋转
            FRotator RandomRotation = FRotator(
                FMath::RandRange(RotationMin.Pitch, RotationMax.Pitch),
                FMath::RandRange(RotationMin.Yaw, RotationMax.Yaw),
                FMath::RandRange(RotationMin.Roll, RotationMax.Roll)
            );
            NewPoint.Transform.SetRotation(RandomRotation.Quaternion());

            // 随机缩放
            float RandomScale = FMath::RandRange(ScaleMin.X, ScaleMax.X);
            NewPoint.Transform.SetScale3D(FVector(RandomScale));

            NewPointData->AddPoint(NewPoint);
        }

        // 添加到输出
        FPCGTaggedData NewTaggedData = TaggedData;
        NewTaggedData.Data = NewPointData;
        OutputData.Add(NewTaggedData);
    }

    return OutputData;
}
```

**关键发现**：
- `TransformPoints` 是 **非破坏性** 的（创建新数据，不修改原数据）
- 支持 **随机范围**（Min/Max）
- 支持 **均匀缩放**（`bUniformScale`）

---

### 3. Static Mesh Spawner — 静态网格生成器

**源码位置**：`Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGStaticMeshSpawner.h`

#### 功能

根据点数据 **生成静态网格实例**（Hierarchical Instanced Static Mesh）。

#### 参数

| 参数 | 类型 | 说明 |
|-----|------|------|
| `Static Mesh` | `TSoftObjectPtr<UStaticMesh>` | 要生成的网格 |
| `Material Override` | `TSoftObjectPtr<UMaterialInterface>` | 材质覆盖 |
| `Cull Distance` | `float` | 剔除距离 |
| `bUseHISM` | `bool` | 是否使用 HISM（默认 true） |

#### 执行逻辑（简化版）

```cpp
// PCGStaticMeshSpawner.cpp
TArray<FPCGTaggedData> UPCGStaticMeshSpawnerSettings::Execute(
    const TArray<FPCGTaggedData>& InputData,
    const FPCGExecutionContext& Context) const
{
    // 1. 获取 PCG Component
    UPCGComponent* Component = Context.Component.Get();
    if (!Component) return {};

    // 2. 创建 HISM Component（如果不存在）
    UHierarchicalInstancedStaticMeshComponent* HISM = Component->GetOrCreateHISM();
    HISM->SetStaticMesh(StaticMesh.LoadSynchronous());

    // 3. 添加实例
    for (const FPCGTaggedData& TaggedData : InputData)
    {
        const UPCGPointData* PointData = Cast<UPCGPointData>(TaggedData.Data);
        if (!PointData) continue;

        for (const FPCGPoint& Point : PointData->GetPoints())
        {
            // 添加实例
            HISM->AddInstance(Point.Transform);
        }
    }

    // 4. 返回空（不输出数据）
    return {};
}
```

**关键发现**：
- `Static Mesh Spawner` 通常作为 **终端节点**（不输出数据）
- 使用 `HISM`（Hierarchical Instanced Static Mesh）提高性能
- 一个 `HISM` 只能渲染 **一种网格**（要多种网格需要多个 Node）

---

## 实践案例

### 案例 1：创建一片随机树林

**目标**：在地面上生成 1000 棵随机的树。

#### 步骤 1：准备资产

1. 导入树模型（`Tree_01.FBX`）
2. 创建材质（`M_Tree`）

#### 步骤 2：创建 PCG 图表

```
[Surface Sampler] → [Transform Points] → [Static Mesh Spawner]
```

#### 步骤 3：配置参数

**Surface Sampler**：
- `Density`：0.5（每 2 立方米 1 棵树）
- `Bounds Modifier`：`PCG Volume`

**Transform Points**：
- `Rotation Min`：(0, 0, 0)
- `Rotation Max`：(0, 360, 0)（随机 Yaw）
- `Scale Min`：(0.8, 0.8, 0.8)
- `Scale Max`：(1.2, 1.2, 1.2)

**Static Mesh Spawner**：
- `Static Mesh`：`Tree_01`
- `Cull Distance`：5000（5 米外开始剔除）

#### 步骤 4：测试

1. 放置 `PCG Volume`（覆盖森林区域）
2. 赋值 PCG 图表
3. 点击 `Generate`

**预期结果**：Volume 范围内生成 1000 棵随机的树。

---

### 案例 2：创建多种树木的混合森林

**目标**：随机生成 3 种树木，比例分别为 50%、30%、20%。

#### 步骤 1：创建 3 个 Surface Sampler

```
[Surface Sampler 1] (Density=0.25) → [Static Mesh Spawner 1] (Tree_01)
[Surface Sampler 2] (Density=0.15) → [Static Mesh Spawner 2] (Tree_02)
[Surface Sampler 3] (Density=0.10) → [Static Mesh Spawner 3] (Tree_03)
```

#### 步骤 2：配置参数

**Surface Sampler 1**：
- `Density`：0.25
- `Seed`：123（保证可复现）

**Surface Sampler 2**：
- `Density`：0.15
- `Seed`：456（不同 Seed → 不同位置）

**Surface Sampler 3**：
- `Density`：0.10
- `Seed`：789

#### 步骤 3：测试

**预期结果**：3 种树木混合生成，比例约为 50:30:20。

---

## 常见错误

### Error 1：Static Mesh Spawner 没有生成任何东西

**症状**：Generate 后，场景中没有树。

**原因**：
1. `Static Mesh` 未赋值
2. `Surface Sampler` 没有输出点
3. `HISM` 被意外删除

**解决**：
1. 检查 `Static Mesh` 是否赋值
2. 在 `Static Mesh Spawner` 前添加 `Debug Draw`，确认有点数据
3. 检查 `HISM` Component 是否存在（Outliner 中搜索）

### Error 2：性能爆炸（FPS 暴跌）

**症状**：Generate 后，FPS 从 60 降到 10。

**原因**：
1. 点数量过多（>10000）
2. 没有使用 `HISM`（每个树都是独立 Actor）
3. `Cull Distance` 设置过大

**解决**：
1. 降低 `Density`
2. 确保 `bUseHISM = true`
3. 设置合理的 `Cull Distance`（如 5000）

### Error 3：树木"漂浮"在空中

**症状**：生成的树不在地面上，而是漂浮在空中。

**原因**：`Surface Sampler` 的 `Project to Surface` 失败。

**解决**：
1. 检查地面是否有 **碰撞**（PCG 需要碰撞才能投影）
2. 确保地面是 `Landscape` 或 `Static Mesh`（有碰撞）
3. 手动调整 `Transform Points` 的 `Location Offset`（Z 轴）

---

## 延伸阅读

### 官方文档
- [PCG 节点官方文档](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/pcg-nodes-in-unreal-engine)
- [PCG Surface Sampler 官方文档](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/pcg-surface-sampler-in-unreal-engine)
- [PCG Static Mesh Spawner 官方文档](https://dev.epicgames.com/documentation/zh-cn/unreal-engine/pcg-static-mesh-spawner-in-unreal-engine)

### 源码深入
- `Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGSurfaceSampler.h`
- `Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGTransformPoints.h`
- `Engine/Plugins/PCG/Source/PCG/Public/Elements/PCGStaticMeshSpawner.h`

### 社区教程
- [Reids Channel - PCG 节点详解](https://www.youtube.com/watch?v=PL_9jbU_gxY)
- [PrismaticaDev - PCG 高级节点技巧](https://www.youtube.com/watch?v=bkMJOvem3FI)

---

## 总结

通过本篇你学到了：

1. **Surface Sampler** — 在表面上生成点，支持密度贴图（Density Map）控制分布
2. **Transform Points** — 对点进行位移、旋转、缩放，支持 Min/Max 范围
3. **Static Mesh Spawner** — 用 Static Mesh 替换点，生成可渲染的网格实例
4. **点过滤与调试** — 使用 Debug Draw 可视化点，使用过滤器筛选点

---

## 下一步

→ **下一课**：[06-表面采样实战](./06-表面采样实战.md) — 深入学习 Surface Sampler 的高级用法（密度贴图、图层权重、法线过滤等）。

<!-- nav:auto -->

---

**导航**: ← [[30-tutorials/pcg/04-PCG图表基础|04-PCG图表基础]] · [[30-tutorials/pcg/06-表面采样实战|06-表面采样实战]] →

<!-- /nav:auto -->
