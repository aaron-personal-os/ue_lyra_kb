# 学习路线总览

> 本文档帮助用户选择合适的学习路线，系统性地学习 UE 技术知识。

## 学习路线图

### 路线 A：UE 框架基础（推荐首先学习）
- **目标**：理解 UE 游戏框架的整体架构
- **难度**：入门 → 中级
- **预计时间**：20 小时
- **系列入口**：[[30-tutorials/ue-framework/00-UE框架概述]]
- **前置知识**：C++ 基础、了解游戏引擎基本概念

### 路线 B：GAS 能力系统
- **目标**：掌握 GAS 的完整使用和内部原理
- **难度**：中级 → 高级
- **预计时间**：40 小时
- **系列入口**：[[30-tutorials/gas/00-GAS系统总览]]
- **前置知识**：路线 A（至少读完 Actor 和 Component 部分）

### 路线 C：网络同步与复制
- **目标**：理解 UE 的网络架构和 Lyra 的网络实现
- **难度**：中级 → 高级
- **预计时间**：30 小时
- **系列入口**：[[30-tutorials/network-sync/00-UE网络通信总览]]
- **前置知识**：路线 A

### 路线 D：动画系统
- **目标**：理解动画蓝图、状态机、IK 和 Lyra 动画实现
- **难度**：中级 → 高级
- **预计时间**：15 小时
- **系列入口**：[[30-tutorials/animation/01-Lyra动画系统框架深度分析-概览]]
- **前置知识**：路线 A（Actor/Component 部分）

### 路线 E：Niagara 粒子系统
- **目标**：理解 Niagara 框架设计和 Lyra 中的应用
- **难度**：中级 → 高级
- **预计时间**：15 小时
- **系列入口**：[[30-tutorials/niagara/01-Niagara系统框架深度分析-概览]]
- **前置知识**：路线 A

### 路线 F：GameFeature 系统
- **目标**：掌握 UE5 GameFeature 架构，从概念到 Lyra 实战
- **难度**：入门 → 高级
- **预计时间**：4 小时
- **系列入口**：[[30-tutorials/game-feature/00-GameFeature系统从入门到实战]]
- **前置知识**：路线 A（至少读完 GameMode 和 Component 部分）

### 路线 G：Modular Gameplay 系统
- **目标**：掌握 UE5 Modular Gameplay 架构，理解组件化游戏设计
- **难度**：入门 → 高级
- **预计时间**：3.5 小时
- **系列入口**：[[30-tutorials/modular-gameplay/00-ModularGameplay系统教程系列]]
- **前置知识**：路线 A（至少读完 Actor 和 Component 部分）

### 路线 H：摄像机系统
- **目标**：掌握 UE5 摄像机系统核心概念、引擎层实现与 Lyra 实战
- **难度**：入门 → 高级
- **预计时间**：10 小时
- **系列入口**：[[30-tutorials/camera-system/00-UE摄像机-Camera系统从入门到实战]]
- **前置知识**：路线 A（Actor/Pawn/Controller 部分）

### 路线 I：性能优化
- **目标**：掌握 UE5 性能分析与优化技术，打造流畅游戏体验
- **难度**：中级 → 高级
- **预计时间**：5 小时
- **系列入口**：[[30-tutorials/performance-optimization/00-性能优化系列概览]]
- **前置知识**：路线 A（至少读完 Tick 系统和渲染管线部分）

### 路线 I：GC（垃圾回收）
- **目标**：掌握 UE5 垃圾回收机制，优化内存管理
- **难度**：入门 → 高级
- **预计时间**：10 小时
- **系列入口**：[[30-tutorials/garbage-collection/00-GC垃圾回收系列概览]]
- **前置知识**：路线 A（至少读完 Actor 和 UObject 部分）

### 路线 J：资源管理
- **目标**：掌握 UE5 资源管理体系，从资产分类、异步加载到 Cook/Pak 打包
- **难度**：入门 → 高级
- **预计时间**：10 小时
- **系列入口**：[[30-tutorials/resource-management/00-UE5资源管理系列概览]]
- **前置知识**：路线 A（至少读完 UObject 和 Asset 部分）、路线 I（GC 基础，推荐）

### 路线 K：输入系统
- **目标**：掌握 UE5 Enhanced Input 系统，从输入动作配置到 Lyra 输入架构
- **难度**：入门 → 高级
- **预计时间**：8 小时
- **系列入口**：[[30-tutorials/input-system/00-UE5输入系统系列概览]]
- **前置知识**：路线 A（至少读完 Actor、Pawn、Controller 部分）

### 路线 L：UE 反射系统
- **目标**：掌握 UE 反射系统的核心概念、宏机制、反射 API 及在 Lyra 中的实际应用
- **难度**：入门 → 高级
- **预计时间**：6 小时
- **系列入口**：[[30-tutorials/ue-reflection/00-UE反射系统从入门到实战]]
- **前置知识**：路线 A（UE 框架基础，至少读完 Actor 和 UObject 部分）

### 路线 M：UE 编辑器扩展
- **目标**：掌握 UE 编辑器扩展机制，包括菜单、工具栏、属性面板、蓝图节点 Pin 的自定义
- **难度**：中级 → 高级
- **预计时间**：8 小时
- **系列入口**：[[30-tutorials/editor-extension/00-UE编辑器扩展系列概览]]
- **前置知识**：路线 A（UE 框架基础）、C++ 基础、蓝图基础

### 路线 N：UE 移动系统
- **目标**：掌握 UCharacterMovementComponent 架构、移动模式、物理计算、网络同步与 Lyra 实战
- **难度**：入门 → 高级
- **预计时间**：10 小时
- **系列入口**：[[30-tutorials/movement-system/00-UE移动系统深度解析系列概览]]
- **前置知识**：路线 A（UE 框架基础，至少读完 Actor、Pawn、Character 部分）

## 推荐学习顺序

A（UE 框架基础） → N（移动系统）→ B（GAS）或 C（网络）→ D / E（按兴趣）

## 每个系列与 Lyra 项目的关联

| 系列 | Lyra 中的对应实现 | 关键模块文档 |
|------|-----------------|-------------|
| UE 框架 | GameMode/GameState/Character | [[20-modules/cpp/ALyraGameMode]] 等 |
| 移动系统 | LyraCharacterMovementComponent | （待创建模块文档） |
| GAS | AbilitySystem/Abilities | [[20-modules/cpp/ULyraAbilitySystemComponent]] 等 |
| 网络同步 | ReplicationGraph/武器同步 | [[20-modules/cpp/ULyraReplicationGraph]] 等 |
| 动画 | 角色动画系统 | [[10-architecture/overview]] |
| Niagara | 特效系统 | [[10-architecture/overview]] |
| UE 反射 | Experience/AbilitySet/Inventory/Equipment | [[30-tutorials/ue-reflection/00-UE反射系统从入门到实战]] 等 |

## 相关页面

- [[index]] - 知识库目录
- [[overview]] - 项目概览

---
> 最后更新：2026-05-17

### 路线 O：Config/INI 系统
- **目标**：掌握 UE Config/INI 配置系统的完整机制，从文件结构、层级合并、INI 操作符到 UObject 集成、Lyra 实战与高级主题
- **难度**：入门 → 高级
- **预计时间**：6 小时
- **系列入口**：[[30-tutorials/config-ini/00-UEConfigINI系统深度解析]]
- **前置知识**：路线 A（至少读完 UE 框架系列的 Actor 和 UObject 部分）

### 路线 P：Mutable 可定制角色系统
- **目标**：掌握 Mutable 插件，实现角色创建器、换装系统、武器自定义等可定制角色功能
- **难度**：入门 → 高级
- **预计时间**：8 小时
- **系列入口**：[[30-tutorials/mutable/00-Mutable可定制角色系统系列概览]]
- **前置知识**：路线 A（至少读完 Actor、Component、SkeletalMesh 部分）

