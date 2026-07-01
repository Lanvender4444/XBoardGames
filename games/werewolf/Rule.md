---
slug: werewolf
name: 狼人杀
min_players: 6
max_players: 12
start_phase: night
factions: [good, werewolf]
win_conditions:
  good:     "werewolf_count == 0"          # 票出所有狼
  werewolf: "werewolf_count >= good_count"  # 狼数 >= 好人数（屠边）

# ── 机器可读定义（编译器消费）。下方正文为人类可读镜像，供审校（§7.1 第③步）。──
roles:
  - name: Seer
    faction: good
    count: 1
    abilities:
      - investigate: { target: single_other, reveals: faction, phase: night, visibility: private }

  - name: Witch
    faction: good
    count: 1
    abilities:
      - protect:   { target: single_any, uses: 1, phase: night }     # 解药
      - eliminate: { target: single_other, uses: 1, phase: night }   # 毒药

  - name: Werewolf
    faction: werewolf
    count: 2
    channels: [werewolf_chat]
    abilities:
      - eliminate: { target: single_other, phase: night, group_decision: true }

  - name: Villager
    faction: good
    count: rest

phases:
  - name: night
    actors: "Werewolf Seer Witch"
    resolution_order: [investigate, protect, eliminate]
    timer: 60
    next: day_discussion

  - name: day_discussion
    actors: all_alive
    actions: [speak]
    timer: 180
    next: day_vote

  - name: day_vote
    actors: all_alive
    actions: [vote]
    on_complete: eliminate_top_voted
    next: night
    check_win: true
---

# 狼人杀 Werewolf

社交推理游戏：好人阵营靠白天投票找出狼人，狼人阵营靠夜晚击杀缩小好人数量。

## 阵营（Factions）

- **good（好人）**：预言家、女巫、平民。胜利条件 `werewolf_count == 0`。
- **werewolf（狼人）**：胜利条件 `werewolf_count >= good_count`（屠边）。

## 角色（Roles）

### 预言家 Seer
- faction: good，count: 1
- 能力：`investigate`（夜晚查验一名其他玩家的**阵营**，结果只对自己可见）

### 女巫 Witch
- faction: good，count: 1
- 能力：`protect`（解药，1 次，可救任意目标）、`eliminate`（毒药，1 次，毒杀一名其他玩家）

### 狼人 Werewolf
- faction: werewolf，count: 2
- 能力：`eliminate`（夜晚群体决策击杀一名其他玩家）
- 私有频道：`werewolf_chat`

### 平民 Villager
- faction: good，count: rest（占满剩余席位）

## 阶段（Phases）

### night
- 行动者：狼人、预言家、女巫
- 结算优先级：`investigate → protect → eliminate`
- 计时：60s；下一阶段：`day_discussion`

### day_discussion
- 行动者：所有存活者；动作：`speak`
- 计时：180s；下一阶段：`day_vote`

### day_vote
- 行动者：所有存活者；动作：`vote`
- 结算：`eliminate_top_voted`（票数最高者出局，平票无人出局）
- 下一阶段：`night`；每轮投票后 `check_win`
