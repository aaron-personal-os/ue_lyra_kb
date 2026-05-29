---
id: 10-architecture/data-flow/network-replication-flow
type: topic
status: current
language: zh
owner: ai
anchors:
  - path: Source/LyraGame/Character/LyraCharacter.cpp
  - path: Source/LyraGame/Inventory/LyraInventoryManagerComponent.cpp
  - path: Source/LyraGame/Equipment/LyraEquipmentManagerComponent.cpp
  - path: Source/LyraGame/Weapons/LyraGameplayAbility_RangedWeapon.cpp
  - path: Source/LyraGame/Weapons/LyraWeaponStateComponent.cpp
related: []
sources:
  - "[[_raw/external/NetworkSync/UE 网络通信-属性复制&RPC流程]]"
  - "[[_raw/external/NetworkSync/UE 网络通信-属性复制&RPC详解]]"
last_synced: 2026-05-16
last_verified: 2026-05-16
tags: [networking, data-flow, replication, fast-array, gas]
---

# 网络复制数据流

> 本页用 Lyra 项目源码中的典型场景描述网络同步链路。

## 1. 普通属性复制：Character 加速度

```mermaid
sequenceDiagram
    participant S as Server ALyraCharacter
    participant D as NetDriver/Replication
    participant C as Client SimulatedProxy
    S->>S: PreReplication()
    S->>S: 压缩 CurrentAcceleration 到 FLyraReplicatedAcceleration
    S->>D: DOREPLIFETIME_CONDITION(ReplicatedAcceleration, COND_SimulatedOnly)
    D->>C: 复制属性变化
    C->>C: OnRep_ReplicatedAcceleration()
    C->>C: 解压为 FVector 并写入 LyraMovementComponent
```

要点：

- 服务端不复制完整浮点加速度，而是复制 3 个量化字段。
- `COND_SimulatedOnly` 避免把该数据发给 AutonomousProxy。
- 客户端 RepNotify 是“解压 + 写入本地移动组件”，不是 gameplay 权威逻辑。

## 2. FastShared movement：跳过默认属性复制时的快路径

```mermaid
sequenceDiagram
    participant S as Server Character
    participant M as Multicast RPC
    participant C as SimulatedProxy
    S->>S: UpdateSharedReplication()
    S->>S: FSharedRepMovement::FillForCharacter()
    S->>S: 与 LastSharedReplication 比较
    alt 数据变化
        S->>M: FastSharedReplication(SharedMovement)
        M->>C: unreliable multicast
        C->>C: 更新时间戳/MovementMode/RepMovement/Crouch
        C->>C: OnRep_ReplicatedMovement()
    else 数据未变化
        S->>S: 跳过发送
    end
```

要点：

- 这是 Lyra 针对移动同步的带宽优化路径。
- RPC 是 unreliable，不能承载必须到达的 gameplay 状态。
- `FSharedRepMovement` 开启 `WithNetSerializer` 与 `WithNetSharedSerialization`。

## 3. FastArray：Inventory 条目同步

```mermaid
sequenceDiagram
    participant S as Server InventoryComponent
    participant L as FLyraInventoryList
    participant N as FastArray Delta
    participant C as Client InventoryComponent
    S->>L: AddEntry(ItemDef, StackCount)
    L->>L: Entries.AddDefaulted_GetRef()
    L->>L: NewObject<ULyraInventoryItemInstance>()
    L->>L: MarkItemDirty(NewEntry)
    L->>N: NetDeltaSerialize()
    N->>C: 仅发送新增/变化/删除元素
    C->>L: PostReplicatedAdd/Change/PreReplicatedRemove
    L->>C: BroadcastChangeMessage()
```

要点：

- `FFastArraySerializer` 解决“数组整体复制太重”的问题。
- Entry 中的 `LastObservedCount` 标记为 `NotReplicated`，只作为客户端本地差量计算辅助。
- 物品实例是 UObject SubObject，需要另行复制，FastArray Entry 的指针本身不足以传输对象状态。

## 4. SubObject 生命周期

```mermaid
flowchart TD
    A[服务器创建 Item/Equipment Instance] --> B[写入 FastArray Entry]
    B --> C{使用 Registered SubObject List?}
    C -->|是| D[AddReplicatedSubObject]
    C -->|否/兼容 Legacy| E[ReplicateSubobjects + Channel->ReplicateSubobject]
    D --> F[客户端收到对象引用和对象状态]
    E --> F
    F --> G[FastArray callback 驱动本地表现]
    H[服务器移除实例] --> I[RemoveReplicatedSubObject]
    I --> J[MarkArrayDirty]
```

要点：

- FastArray 负责“列表结构和条目变化”。
- SubObject 复制负责“条目指向的 UObject 实例状态”。
- Lyra 同时写了 `ReplicateSubobjects` 和 `AddReplicatedSubObject`，便于兼容 Legacy 与 registered list。

## 5. GAS 武器 TargetData 预测

```mermaid
sequenceDiagram
    participant C as Local Client
    participant ASC as AbilitySystemComponent
    participant S as Server
    participant W as WeaponStateComponent
    C->>C: PerformLocalTargeting()
    C->>ASC: FScopedPredictionWindow
    C->>ASC: 构建 TargetData + UniqueId
    C->>W: AddUnconfirmedServerSideHitMarkers
    C->>ASC: OnTargetDataReadyCallback
    ASC->>S: CallServerSetReplicatedTargetData
    S->>S: 校验 TargetData / CommitAbility
    S->>W: ClientConfirmTargetData(UniqueId, bSuccess, HitReplaces)
    W->>C: Client RPC 确认命中标记
    C->>ASC: ConsumeClientReplicatedTargetData
```

要点：

- 本地先做命中检测是为了手感和预测。
- 服务器仍是权威：最终是否 Commit、是否确认命中由服务器决定。
- `FLyraGameplayAbilityTargetData_SingleTargetHit::NetSerialize` 追加 `CartridgeID`，并在 Iris 配置中列入 `SupportsStructNetSerializerList`。

## 6. GameplayTag 快速复制

```mermaid
flowchart LR
    A[GameplayTag 配置] --> B[FastReplication=True]
    B --> C[Tag 使用网络索引而非完整字符串]
    C --> D[ASC/StatTags/GameplayCue 等同步更省带宽]
```

Lyra 在 `DefaultGameplayTags.ini` 中设置：

- `FastReplication=True`
- `NumBitsForContainerSize=6`
- `NetIndexFirstBitSegment=16`

这会影响 GAS Tag、StatTags、GameplayCue 等多处网络数据的编码成本。

## 7. RepGraph 复制候选生成

```mermaid
flowchart TD
    A[NetDriver tick] --> B{ReplicationGraph 启用?}
    B -->|否| C[Legacy IsNetRelevantFor / Priority]
    B -->|是| D[LyraReplicationGraph 节点]
    D --> E[GridSpatialization2D]
    D --> F[AlwaysRelevantNode]
    D --> G[AlwaysRelevant_ForConnection]
    D --> H[PlayerStateFrequencyLimiter]
    E --> I[为连接生成 Actor 列表]
    F --> I
    G --> I
    H --> I
    I --> J[Replication Driver 复制 Actor]
```

要点：

- RepGraph 优化的是“为每个连接找哪些 Actor 需要考虑复制”。
- Lyra 默认禁用，因此这张图是可选优化路径。
- 一旦启用，`AActor::IsNetRelevantFor` 不再是主要的相关性扩展点。

## 验证建议

每条链路都应至少验证：

- Listen Server 与 Dedicated Server。
- Join-in-progress。
- 丢包与延迟。
- Owner / SimulatedProxy 差异。
- 对象销毁与重生。
- 重复添加/删除 FastArray 元素。
