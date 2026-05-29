# Phase 4：Run 状态管理（RunManager）— 学习导读

## 本阶段目标

实现 RunManager：记录局内状态（当前层数、拥有的 Relic、HP 保留、货币），支持局的开始、结束（胜利/失败）和数据重置。

## 推荐阅读清单

1. [`01-UGameInstance详解.md`](../../Docs/30-tutorials/ue-framework/10-engine-layer/01-UGameInstance详解.md)
   — **RunManager 挂载点**。GameInstance 跨关卡持久存在，是在关卡切换后还需要保留 Run 状态的天然容器。重点阅读：`GameInstanceSubsystem` 的创建方式（用 `UGameInstanceSubsystem` 实现 RunManager，比直接加在 GameInstance 上更干净）。

2. [`00-UWorld详解.md`](../../Docs/30-tutorials/ue-framework/20-world-layer/00-UWorld详解.md)
   — 理解 World 和 GameInstance 的关系；关卡切换时 World 被销毁但 GameInstance 保留，这是 RunManager 选择挂在 GameInstance 上的原因。

3. [`01-ULevel与LevelStreaming详解.md`](../../Docs/30-tutorials/ue-framework/20-world-layer/01-ULevel与LevelStreaming详解.md)
   — 当房间之间使用 Level Streaming 切换时，理解哪些 Actor 会随 Level 销毁、哪些应该在 GameInstance 层保留。

4. [`00-AGameModeBase详解.md`](../../Docs/30-tutorials/ue-framework/30-gamemode-layer/00-AGameModeBase详解.md)
   — RunManager 需要与 GameMode 协作（局结束时调用 GameMode 切换状态或重启关卡），理解 GameMode 的 `RestartGame` / `EndGame` 接口。

## Lyra 单机差异提示

| 文档 | 可跳过的章节 |
|------|------------|
| `UGameInstance详解` | Seamless Travel、多人会话（Session）管理章节 |
| `UWorld详解` | 服务器/客户端 World 分离的章节 |
| `AGameModeBase详解` | `Login` / `Logout` / `GetNetMode` 相关的多人章节 |

## 项目映射说明

**RunManager 推荐实现方式：**

```cpp
// 挂在 GameInstance 上，跨关卡持久
UCLASS()
class URunManagerSubsystem : public UGameInstanceSubsystem
{
    UPROPERTY() int32 CurrentFloor;
    UPROPERTY() TArray<TSoftObjectPtr<URelicData>> AcquiredRelics;
    UPROPERTY() float PersistentHP;  // 若设计为 HP 保留局内

    void StartNewRun();
    void EndRun(bool bVictory);
    void AdvanceFloor();
};
```

- `StartNewRun()` → 重置所有局内状态，撤销所有 Relic 授予，回到起始房间。
- `EndRun(bVictory)` → 调用 GameMode 切换到结算界面，将结果写入 Meta 进度（Phase 6）。
- `AdvanceFloor()` → 递增层数，触发程序化关卡生成（Phase 5）。

Lyra 没有"run 状态"这个概念，但其 `ULyraExperienceManagerComponent` 管理 Experience 的加载/卸载状态机是一个可以学习的状态管理模式。

## 扩展阅读

- [`01-AGameStateBase详解.md`](../../Docs/30-tutorials/ue-framework/30-gamemode-layer/01-AGameStateBase详解.md) — 若需要在关卡内广播 Run 状态变更（如多个 Widget 监听"层数更新"事件），可考虑在 GameState 上挂委托。
