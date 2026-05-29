---
id: 20-modules/cpp/ULyraReplicationGraph
type: module
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/System/LyraReplicationGraph.h
  - path: Source/LyraGame/System/LyraReplicationGraph.cpp
  - path: Source/LyraGame/System/LyraReplicationGraphSettings.h
  - path: Source/LyraGame/System/LyraReplicationGraphTypes.h
  - path: Config/DefaultGame.ini
related: []
sources:
  - "[[_raw/external/NetworkSync/UE 网络通信-ReplicationGraph]]"
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [replication-graph, networking, relevancy, lyra]
---

# ULyraReplicationGraph

> Lyra 的 ReplicationGraph 实现。当前项目有完整代码和配置，但默认 `bDisableReplicationGraph=True`。

## 职责

`ULyraReplicationGraph` 负责在 Legacy 复制路径下替代普通 `IsNetRelevantFor` 扫描，按节点为连接生成待复制 Actor 列表。

主要能力：

- 注册类到 RepGraph 节点的路由策略。
- 初始化全局节点和连接节点。
- 为 spatial actor 设置 cull distance 和 replication period。
- 为 PlayerState 提供频率限制节点。
- 为 Character 配置 FastShared movement path。
- 提供 RepGraph 调试命令和路由打印。

## 当前启用状态

`Config/DefaultGame.ini`：

```ini
[/Script/LyraGame.LyraReplicationGraphSettings]
bDisableReplicationGraph=True
DefaultReplicationGraphClass=/Script/LyraGame.LyraReplicationGraph
```

结论：代码存在，但默认禁用。启用需要修改设置并通过日志确认 `Lyra::RepGraph::ConditionalCreateReplicationDriver` 创建了 RepGraph。

## 关键节点

| 节点 | 作用 |
|---|---|
| `UReplicationGraphNode_GridSpatialization2D` | 空间网格，处理距离相关 Actor。 |
| `UReplicationGraphNode_ActorList` | 全局 always relevant Actor。 |
| `ULyraReplicationGraphNode_AlwaysRelevant_ForConnection` | 每连接 always relevant Actor。 |
| `ULyraReplicationGraphNode_PlayerStateFrequencyLimiter` | PlayerState rolling subset 限频复制。 |
| `UReplicationGraphNode_TearOff_ForConnection` | TearOff Actor，基类管理。 |

## 路由与类信息

`InitGlobalActorClassSettings` 会：

1. 设置 lazy init，用于尚未加载的复制类。
2. 读取 `ULyraReplicationGraphSettings::ClassSettings`。
3. 遍历所有 replicated native/blueprint class。
4. 通过 `GetClassNodeMapping` 判断路由。
5. 用 `InitClassReplicationInfo` 从 legacy Actor 设置推导 cull distance 和 replication period。
6. 为 `ALyraCharacter` 显式配置 FastShared path。

## Character FastShared Path

`ALyraCharacter` 的 `FSharedRepMovement` 与 RepGraph 结合：

- `CharacterClassRepInfo.FastSharedReplicationFunc` 调用 `ALyraCharacter::UpdateSharedReplication()`。
- `FastSharedReplicationFuncName = "FastSharedReplication"`。
- `FastSharedPathConstants.MaxBitsPerFrame` 由 `Lyra.RepGraph.TargetKBytesSecFastSharedPath` 和 NetServer tick rate 计算。
- `FastSharedPathConstants.DistanceRequirementPct` 由 `Lyra.RepGraph.FastSharedPathCullDistPct` 控制。

## PlayerState 限频

`ULyraReplicationGraphNode_PlayerStateFrequencyLimiter`：

- 跟踪所有 PlayerState。
- 每帧只返回一部分 PlayerState。
- `TargetActorsPerFrame=2`。
- 不抑制 `ForceNetUpdate`。

这能降低大量玩家时所有 PlayerState 对所有连接高频复制的压力。

## 与 Iris 的关系

ReplicationGraph 是 Legacy `ReplicationDriver`。UE5.7 `UNetDriver::SetReplicationDriver` 对 Iris NetDriver 有限制：Iris NetDriver 不能再挂 Legacy `ReplicationDriver`。因此 Lyra RepGraph 与 Iris filter/prioritizer 不是同一 NetDriver 上直接叠加的两层。

## 常见坑

- 忘记 `bDisableReplicationGraph=True`，误以为 Lyra 默认启用了 RepGraph。
- 开启后仍期望 `AActor::IsNetRelevantFor` 是主要扩展点。
- 把 `bAlwaysRelevant` 当作通用解决方案，导致带宽/CPU 回退。
- PlayerState 复制频率问题需要同时看 ASC 需求和 RepGraph 限频策略。
- FastShared path 是移动快照优化，不应用于权威 gameplay 状态。

## 调试命令

- `Net.RepGraph.PrintGraph`
- `Net.RepGraph.PrintAll <Frames> <ConnectionIdx> <Class|Nclass>`
- `Net.RepGraph.PrintAllActorInfo <ActorMatchString>`
- `Lyra.RepGraph.PrintRouting`

## 相关页面

- `[[30-tutorials/network-sync/06-ReplicationGraph与Lyra实践]]`
- `[[10-architecture/subsystems/networking-system]]`

<!-- nav:auto -->

---

**导航**: ← [[20-modules/cpp/ULyraWeaponStateComponent|ULyraWeaponStateComponent]] · [[20-modules/cpp/FLyraGameplayAbilityTargetData_SingleTargetHit|FLyraGameplayAbilityTargetData_SingleTargetHit]] →

<!-- /nav:auto -->
