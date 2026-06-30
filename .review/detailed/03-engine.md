# 03 · 游戏引擎 `app/engine`（§11）

引擎是**纯逻辑、可单测、不依赖网络与 LLM**。它不区分行动来源：人类（WebSocket）与 AI（LangGraph）
的行动都变成 `Action` 喂给 `apply`——这就是"人机混局跑同一套引擎"的实现基础。

---

## `app/engine/types.py` 🟢 — 数据类型与已编译定义

### `class Visibility(str, Enum)`
事件可见性：`PUBLIC`（所有人）/ `PRIVATE`（仅行动者本人，如查验结果）/ `FACTION`（同阵营，如狼队私聊）。

### 已编译定义（frozen dataclass，`compiler` 的产物，引擎只认它们）
- **`AbilityDef`**：一个绑定到原语的能力。`primitive`、`params`（剩余参数）、`phase`（可用阶段）、
  `uses`（次数上限，None=不限）、`visibility`。
- **`RoleDef`**：`name / faction / count`（int 或 `"rest"`）/ `abilities` / `channels`（私有频道）。
- **`PhaseDef`**：`name`、`actors`（原始串）、`actor_roles`（解析后的角色名元组）、`actions`（允许原语）、
  `resolution_order`（结算优先级）、`timer`、`next`、`on_complete`、`check_win`。
- **`GameDefinition`**：整局定义。含 `slug/name/min_max_players/factions/win_conditions/roles/phases/start_phase`；
  方法 `phase(name)`、`role(name)` 按名查找（找不到抛 `KeyError`）。

### 运行时类型
- **`Seat`**（可变）：`seat_id / actor_type(human|ai) / role / faction / alive / name`。
- **`Action`**：一次行动意图。`seat / type`（原语名或 `"pass"`）/ `targets`（元组）/ `channel` / `extra`。
- **`Event`**：一条 session_event。`seq / phase / round / actor / action / payload / visibility / audience`
  （audience 是 private/faction 时的可见席位集合）。
- **`WinResult`**（frozen）：`faction`（胜方）+ `reason`（命中的谓词）。
- **`GameState`**（可变，引擎工作内存）：
  - 字段：`definition / seats / phase / round / seq / finished / winner`
  - `ability_uses: {(seat_id, primitive) -> 剩余次数}`
  - `acted: set[int]`（本阶段已行动席位）
  - `pending: {原语 -> [Action]}`（本阶段累积、待结算的行动）
  - `log: list[Event]`（事件流）
  - 便捷查询：`seat(id)`、`alive_seats()`、`faction_count(faction, alive_only=True)`。

---

## `app/engine/predicates.py` 🟢 — 胜负谓词安全求值（§7.2）

**为什么不用 `eval`**：win_conditions 是字符串谓词（如 `"werewolf_count >= good_count"`）。直接 `eval`
有任意代码执行风险。这里用 `ast` 解析并**只放行**比较、布尔、算术、变量、数字字面量，其它语法一律抛
`ValueError`，编译期即可发现写错的谓词。test_predicates 专门验证 `__import__('os')` 被拒绝。

### `_eval(node, ctx) -> Any`
递归求值 AST 节点。支持：`Expression`、`BoolOp`(and/or)、`UnaryOp`(not/负号)、
`BinOp`(+,-,*,//,%)、`Compare`(==,!=,<,<=,>,>=，支持链式)、`Name`（从 ctx 取值，未知名抛错）、
`Constant`（int/float/bool）。遇到任何不允许的节点抛 `ValueError`。

### `evaluate(predicate, ctx) -> bool`
`ast.parse(mode="eval")` → `_eval` → 转 bool。运行时用它判断某阵营是否达成胜利。

### `validate(predicate, allowed_names) -> None`
编译期静态校验：解析后遍历所有 `Name` 节点，若引用了 `allowed_names` 之外的变量则抛 `ValueError`。
编译器用它确保谓词只引用 `{faction}_count`/`alive_count`。

---

## `app/engine/engine.py` 🟢 — `GameEngine`（逐方法详解）

模块常量 `PASS = "pass"`（跳过可选行动的伪行动类型）。
`class IllegalActionError(ValueError)`：提交了不在 `legal_actions` 中的行动时抛出——既防人类作弊，也防
AI 幻觉出非法操作（§9.1/§10 的"合法性双保险"）。

### 初始化

**`init_session(definition, players, seed=None) -> GameState`**
1. 校验人数在 `[min_players, max_players]`。
2. `_expand_roles` 展开角色清单，用 `random.Random(seed)` 洗牌（seed 固定→可复盘，§5 seed）。
3. 为每个传入 `Seat` 赋 role/faction/name，重建 `seats`。
4. 构造 `GameState`，phase=起始阶段，round=1。
5. 初始化 `ability_uses`：对每个有限次能力登记剩余次数。
6. emit `game_start` 与首个 `phase_enter` 事件。返回初始状态。

**`_expand_roles(definition, n) -> list[str]`**
按各 `RoleDef.count` 展开角色名列表；`count="rest"` 的角色占满剩余席位（最多一个 rest）。
最终长度必须等于 n，否则抛 `ValueError`（提示检查 Rule.md 的 count）。

### 调度（谁该行动）

**`actors_to_act(state) -> list[Seat]`**
返回当前阶段**仍需行动且尚未提交**的席位：游戏结束返回空；否则取该阶段的候选席位，过滤掉已在
`acted` 中的，并且只保留那些 `legal_actions` 非空的（没有合法行动的就不必等它）。

**`_phase_seats(state, phase) -> list[Seat]`**
解析阶段行动者：`actors` 为 `all_alive`/`all` 时返回所有存活席位；否则返回角色在 `actor_roles` 中的存活席位。

### 合法行动集

**`legal_actions(state, seat) -> list[Action]`**
某席位当前能做的全部合法行动。游戏结束或席位已死返回空。否则：
1. **阶段级通用行动**（不绑角色）：若阶段 actions 含 `vote`→生成投票项；含 `speak`→生成公共发言；含 `nominate`→提名项。
2. **角色能力行动**：遍历该角色的能力，跳过阶段不匹配或次数耗尽的，调用 `_ability_options` 生成选项；
   有限次能力会把本回合标记为"可选"。
3. **可选/无事可做**：若存在可选能力，或该席位属于本阶段行动者但暂无具体行动，则追加一个 `PASS` 行动，
   让流程能推进（避免卡死）。

**`_targets_other_alive(state, seat) -> list[int]`**：除自己外的存活席位 id 列表（多数目标型能力用）。

**`_vote_options(state, seat) -> list[Action]`**：对每个其他存活席位生成一个 `vote` 行动，外加一个弃票
（`extra={"abstain": True}`，无目标）。

**`_nominate_options(...)`** 🟡：阿瓦隆队长组队占位，当前返回空（Phase 4 接入）。

**`_ability_options(state, seat, ab) -> list[Action]`**
按原语生成具体选项：
- `eliminate/protect/investigate`：依 `params.target` 决定目标域——`single_other`（除己外存活）或
  `single_any`（任意存活，如女巫救人可救己）。每个目标一个行动。
- `speak`：进入该能力指定频道的发言。
- 其它原语当前返回空（待扩展）。

### 应用行动（核心）

**`apply(state, action) -> (state, new_events)`**
服务器权威的唯一改状态入口：
1. 游戏已结束→抛 `IllegalActionError`。
2. `_is_legal` 校验：行动必须精确匹配某个 `legal_actions`（type+targets），否则抛 `IllegalActionError`。
3. 记 `start=len(log)`，把席位加入 `acted`。
4. 按类型处理：
   - **`PASS`**：emit 私有 `pass` 事件（仅本人可见）。
   - **`speak`**：emit `speak`；非 public 频道→`FACTION` 可见，否则 `PUBLIC`。
   - **`investigate`**：**即时私有结算**——查目标的 faction 或 role（按 `reveals`），消耗一次使用，
     emit `investigate_result`（`PRIVATE`，audience=本人）。这是查验结果只对预言家可见的实现。
   - **其余（eliminate/protect/vote/nominate）**：放入 `pending` **累积**，待阶段结算；eliminate/protect 立即
     消耗次数；emit `<type>_submitted` 事件——投票公开可见，夜晚私有行动仅本人可见。
5. 返回本次新增事件切片 `log[start:]`。

**`_is_legal(state, action) -> bool`**：在该席位的 `legal_actions` 中查找 type 与 targets 完全一致的项。

**`_ability(state, seat, primitive) -> AbilityDef|None`**：在席位角色的能力里找指定原语（取第一个匹配）。

**`_consume_use(state, seat, primitive)`**：把 `ability_uses[(seat,primitive)]` 减一（不低于 0）。

### 阶段推进与结算

**`advance_phase(state) -> (state, new_events)`**
结算本阶段累积行动并转移：
1. **结算**：阶段有 `resolution_order`→`_resolve_night`；`on_complete == "eliminate_top_voted"`→`_resolve_vote`。
2. **胜负检查**：若阶段 `check_win` 或刚发生过夜晚结算→`check_win`；命中则置 `finished/winner`，emit `game_over` 并提前返回。
3. **转移**：清空 `acted` 与 `pending`；`next` 为 None 则停留；若 `next == start_phase` 则 `round += 1`（回到夜晚=新一轮）；
   切换 phase 并 emit `phase_enter`。

**`_resolve_night(state, phase)`**
按 `resolution_order` 依次处理：`protect`→把目标加入 `protected` 集合；`eliminate`→调用 `_eliminate_victims`
得到出局集合，未被保护且仍存活者标记死亡并 emit `death`。`investigate` 不在此处（已在 apply 即时结算）。

**`_eliminate_victims(state) -> set[int]`**
区分两类击杀：
- **群体决策**（狼队，能力带 `group_decision`）：所有狼的指向计票，取得票最高（平票取最小 seat_id 保证确定性）作为单一受害者。
- **个体击杀**（如女巫毒药，无 group_decision）：每个各自生效，全部计入受害者集合。
两类合并返回。**这修正了"狼刀和女巫毒会被错误合并计票"的语义问题。**

**`_resolve_vote(state, phase)`**
白天投票结算：累计非弃票的票数，emit `vote_result`（含计票）；无有效票则返回；取最高票，平票（多于一人并列）
则 emit `vote_tie` 且无人出局（占位规则 tie_rule=no_elim，可由 Rule.md 配置覆盖）；否则该席位出局并 emit `death`。

### 胜负

**`check_win(state) -> WinResult|None`**
构造上下文后，按 `win_conditions` 逐阵营用 `predicates.evaluate` 求值，首个为真的阵营即胜者（返回 `WinResult`）。

**`_win_context(state) -> dict[str,int]`**
构造谓词上下文：`alive_count` + 每个阵营的存活计数 `<faction>_count`（如 good_count、werewolf_count）。

### 事件

**`_emit(state, actor, action, payload, visibility=PUBLIC, audience=()) -> Event`**
统一造事件：用当前 `seq` 与 `round/phase` 构造 `Event`，`seq += 1`，追加到 `log` 并返回。
所有状态变更都经它落账——保证事件流连续有序（test_autoplay 验证 seq 连续无洞）、可复盘、可派生记忆。

## `app/engine/__init__.py`
重导出 `GameEngine` 与全部类型，方便 `from app.engine import GameEngine, Seat, Action`。
