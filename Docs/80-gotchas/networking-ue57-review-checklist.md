---
id: 80-gotchas/networking-ue57-review-checklist
type: topic
status: current
language: zh
owner: ai
anchors:
  - path: Config/DefaultEngine.ini
  - path: Config/DefaultGame.ini
  - path: Source/LyraGame/Inventory/LyraInventoryManagerComponent.cpp
  - path: Source/LyraGame/Equipment/LyraEquipmentManagerComponent.cpp
related: []
sources:
  - "[[_raw/external/NetworkSync/UE 网络通信-收发包详解]]"
  - "[[_raw/external/NetworkSync/UE 网络通信-Iris-总览]]"
  - "[[_raw/external/NetworkSync/UE 网络通信-Iris-NetSerializer]]"
  - "[[_raw/external/NetworkSync/UE 网络通信-Iris-NetToken]]"
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [gotcha, ue57, networking, iris, replication]
---

# UE5.7 网络同步复核清单

> 用于重写旧教程、启用 ReplicationGraph、迁移 Iris 或新增网络同步功能前的风险检查。

## 1. 版本与来源

- [ ] 原文是否基于旧版引擎？若是，不直接引用结论。
- [ ] 是否已用 UE5.7 引擎源码复核关键函数名、CVar、默认值？
- [ ] 是否区分“官方文档描述”“源码实现”“Lyra 当前项目配置”？
- [ ] 是否避免使用“完全替代”“必然”“一定有序”等绝对表述？

## 2. Iris 启用与运行路径

- [ ] `Iris` 插件是否启用？
- [ ] C++ 模块是否调用 `SetupIrisSupport(Target)`？
- [ ] NetDriver 是否实际使用 Iris 路径？
- [ ] `net.Iris.UseIrisReplication` 或等价启动参数是否生效？
- [ ] PIE、Listen Server、Dedicated Server 是否路径一致？
- [ ] 启动日志是否能证明当前运行路径？

Lyra 当前事实：插件和构建支持存在；`DefaultEngine.ini` 有 Iris descriptor/bridge 配置，但当前 `Config/` 中未发现显式 `net.Iris.UseIrisReplication`、Iris NetDriver 或 `NetDriverDefinitions` 配置。UE5.7 源码中该 CVar 默认值为 `0`，所以需要进一步用启动日志确认实际 NetDriver 路径。

## 3. ReplicationGraph

- [ ] 是否确认 `bDisableReplicationGraph` 当前值？
- [ ] 是否确认 `UReplicationDriver::CreateReplicationDriverDelegate` 创建了项目 RepGraph？
- [ ] 启用后是否知道 `AActor::IsNetRelevantFor` 不再是主要扩展点？
- [ ] PlayerState、PlayerController、Pawn、LevelScriptActor 是否有明确路由策略？
- [ ] 是否验证 `Net.RepGraph.PrintGraph` 和 `Lyra.RepGraph.PrintRouting` 输出？

Lyra 当前事实：`DefaultGame.ini` 中 `bDisableReplicationGraph=True`，RepGraph 默认禁用。

## 4. SubObject 复制

- [ ] 动态 UObject 是否有稳定 Outer 和生命周期？
- [ ] 创建后是否调用 `AddReplicatedSubObject`？
- [ ] 移除/销毁前是否调用 `RemoveReplicatedSubObject`？
- [ ] 是否还依赖 `ReplicateSubobjects` 和 `UActorChannel`？
- [ ] Join-in-progress 是否能收到已有 SubObject？
- [ ] SubObject 删除时客户端是否正确清理引用和表现？

Lyra 样例：Inventory 和 Equipment 同时实现 registered list 与传统 `ReplicateSubobjects`。

## 5. FastArray

- [ ] Entry 是否继承 `FFastArraySerializerItem`？
- [ ] Container 是否继承 `FFastArraySerializer`？
- [ ] 是否实现 `NetDeltaSerialize` 并设置 `WithNetDeltaSerializer=true`？
- [ ] 增加/修改元素是否调用 `MarkItemDirty`？
- [ ] 删除/批量变化是否调用 `MarkArrayDirty`？
- [ ] callback 是否只做客户端表现/缓存更新，不做服务端权威逻辑？
- [ ] Iris 下是否验证 equality / dirty 判断行为？

## 6. RPC 与时序

- [ ] 是否依赖 RPC 与属性复制的到达顺序？如果是，需要重构或显式确认。
- [ ] Reliable RPC 是否可能被高频调用导致队列压力？
- [ ] Unreliable RPC 是否只承载可丢弃表现或快照？
- [ ] NetMulticast 是否需要到达所有客户端，还是只需要相关客户端？
- [ ] Client RPC 的 owning connection 是否明确？

Lyra 样例：`FastSharedReplication` 是 unreliable multicast；`ClientConfirmTargetData` 是 reliable Client RPC。

## 7. 条件复制与 Ownership

- [ ] `COND_OwnerOnly`、`COND_SkipOwner`、`COND_SimulatedOnly` 是否有明确测试？
- [ ] AutonomousProxy 与 SimulatedProxy 是否收到不同数据？
- [ ] `bOnlyRelevantToOwner` 与 `bNetUseOwnerRelevancy` 是否符合预期？
- [ ] PlayerState、Pawn、Controller 的 Owner 链是否稳定？

## 8. 自定义序列化

- [ ] `NetSerialize` 是否返回正确成功状态？
- [ ] 是否设置 `WithNetSerializer=true`？
- [ ] Iris 下是否需要加入 `SupportsStructNetSerializerList`？
- [ ] 结构体内部新增字段后是否保持前后兼容？
- [ ] 是否验证丢包、重发、Join-in-progress？

Lyra 样例：`FLyraGameplayAbilityTargetData_SingleTargetHit` 自定义 `NetSerialize` 并在 Iris 配置中显式支持。

## 9. GameplayTag 与 GAS

- [ ] `FastReplication=True` 是否要求所有端 Tag 字典一致？
- [ ] `NumBitsForContainerSize` 与容器规模是否匹配？
- [ ] ASC 复制模式是否符合项目规模：Minimal / Mixed / Full？
- [ ] PredictionKey 生命周期是否正确消费？
- [ ] TargetData 是否有服务端校验与客户端确认？

## 10. 最小测试矩阵

| 场景 | 必测项 |
|---|---|
| 普通属性复制 | 初始同步、变化同步、RepNotify、条件复制 |
| RPC | Server / Client / Multicast、reliable/unreliable、owner 变化 |
| FastArray | add/change/remove、批量变化、Join-in-progress |
| SubObject | 创建、注册、状态同步、移除、销毁、重连 |
| GAS 预测 | 成功、失败、回滚、TargetData 消费、命中确认 |
| RepGraph | 节点路由、空间距离、PlayerState 限频、调试命令 |
| Iris | 传统 API 兼容、自定义 NetSerializer、过滤、优先级、DataStream |

<!-- nav:auto -->

---

**导航**: [[80-gotchas/gas-cue-cleanup-on-asc-destroy|gas-cue-cleanup-on-asc-destroy]] →

<!-- /nav:auto -->
