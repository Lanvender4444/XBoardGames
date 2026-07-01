---
slug: avalon
name: 阿瓦隆
min_players: 5
max_players: 10
start_phase: team_building
factions: [good, evil]
win_conditions:
  # 占位谓词：当前引擎只跟踪阵营存活计数。阿瓦隆真实胜负是"任务成败计数 + 刺杀梅林"，
  # 需要扩展原语 `quest` 跟踪任务结果（Phase 4）。这里先用合法占位以通过编译期校验。
  good: "evil_count == 0"
  evil: "good_count == 0"

roles:
  - name: Merlin            # 梅林：知晓邪恶（除莫德雷德），但若被刺杀则邪恶胜
    faction: good
    count: 1
    abilities:
      - reveal: { attribute: faction, scope: self, phase: setup, visibility: private }
  - name: Percival          # 派西维尔：能看到梅林与莫甘娜（无法区分）
    faction: good
    count: 1
    abilities:
      - reveal: { attribute: role, scope: self, phase: setup, visibility: private }
  - name: LoyalServant      # 亚瑟的忠臣
    faction: good
    count: rest
  - name: Morgana           # 莫甘娜：在派西维尔眼中伪装成梅林
    faction: evil
    count: 1
  - name: Assassin          # 刺客：终局可刺杀梅林
    faction: evil
    count: 1
    abilities:
      - eliminate: { target: single_any, uses: 1, phase: assassinate }
  - name: MinionOfMordred   # 莫德雷德的爪牙
    faction: evil
    count: 1

phases:
  - name: team_building     # 队长提名队员
    actors: all_alive
    actions: [nominate]
    timer: 90
    next: team_vote
  - name: team_vote         # 全体公投是否接受队伍
    actors: all_alive
    actions: [vote]
    on_complete: eliminate_top_voted   # 占位：实际为"组队通过/否决"，Phase 4 用 quest 语义替换
    timer: 60
    next: quest
  - name: quest             # 任务成败投票（仅队员）。需扩展原语 `quest`（Phase 4）
    actors: all_alive
    actions: [vote]
    timer: 60
    next: team_building
    check_win: true
  - name: assassinate       # 终局刺杀（占位）
    actors: all_alive
    actions: []
    next: team_building
---

# 阿瓦隆 Avalon（Phase 4 管线生成验证样本）

> 这是路线图里"**非内置、走规则摄取管线生成**"的验证样本（Start.md §14 Phase 4）。
> 当前文件可被 `schema.parse_rule_md` 解析、被 `compiler.compile_spec` 结构化编译，
> 但**任务成败计数 / 刺杀梅林**的完整胜负需要新增扩展原语 `quest`（§7.3 扩展流程），
> 未在 Phase 1 引擎实现。

## 阵营与特殊角色

| 阵营 | 角色 |
|---|---|
| good（正义） | 梅林 Merlin、派西维尔 Percival、亚瑟忠臣 LoyalServant |
| evil（邪恶） | 莫甘娜 Morgana、刺客 Assassin、莫德雷德爪牙 MinionOfMordred |

信息不对称：邪恶方互认；梅林知晓邪恶（除莫德雷德）；派西维尔能看到梅林与莫甘娜但无法区分。

## 阶段流程

`team_building`（队长提名）→ `team_vote`（组队公投）→ `quest`（任务成败）→ 循环；
五轮任务三胜判正义方领先，邪恶方最后可 `assassinate` 刺杀梅林翻盘。

## 与狼人杀共享同一组原语

`nominate / vote / quest / reveal` —— 与狼人杀的 `eliminate / investigate / protect / vote`
落在同一套"原语 + 阶段状态机"上，正是用来验证引擎通用性的（附录 A）。
