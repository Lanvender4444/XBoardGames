# 05 · CLI 自动对局 与 测试

---

# 一、`app/cli/autoplay.py` 🟢 — 命令行自动对局（Phase 1 里程碑工具）

**目的**：用"随机合法行动"策略驱动全 AI 的一整局，逐回合打印事件，直到分出胜负。这是验证引擎抽象是否
成立的关键：CLI、未来的人类 WebSocket、AI LangGraph 都走同一条 `apply` 路径。

### `run_game(slug, players, seed=0, max_rounds=50, on_event=None) -> GameState`
跑通一整局并返回终局状态：
1. `load_builtin(slug)` 编译内置 Rule.md；构造 `GameEngine`。
2. 建 `players` 个全 AI `Seat`，`init_session(seed=...)`。
3. 用 `RandomPolicy(seed)` 作为所有席位的决策器。
4. 主循环：当未结束且 round≤max_rounds——
   - 对 `actors_to_act` 中每个席位，`policy.decide` 取行动（None 则回退 `PASS`），`engine.apply`。
   - `engine.advance_phase` 结算并转移。
   - `_flush` 把新增事件交给 `on_event`。
5. `safety` 计数器防御死循环（超过 `max_rounds*20` 抛 `RuntimeError`，提示规则/引擎疑似死循环）。

### `_flush(state, since, on_event)`
把 `log[since:]` 的每条新事件交给回调（`on_event` 为 None 时什么都不做）。增量派发，避免重复打印。

### `_seat_label(state, seat_id) -> str`
把席位 id 渲染成 `#i(Role)`；id 为 None（系统事件）渲染为 `—`。

### `_print_event(state, ev)`
逐条打印事件：`[r{round}/{phase}] {actor} {action} {payload}` + 非 public 时附 `[visibility]`。
用 `ev.round`（事件发生时的回合）而非当前回合，保证日志回合标注准确。

### `main(argv=None) -> int`
argparse 入口：参数 `--game`（默认 werewolf）、`--players`（默认 8）、`--seed`（默认 0）、`--quiet`（只打印结果）。
跑完后打印每个席位的角色公开与胜者阵营。也是 `pyproject` 中 `autoplay` 脚本入口。

### `app/cli/__init__.py`
包说明（引擎验证工具）。

**用法**：`uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42`

---

# 二、`tests/` 🟢 — 34 用例，全部通过

> 用 `uv run pytest` 运行。`pyproject` 配置 `pythonpath=["."]`，故测试直接导入本地 `app` 包。

## `tests/test_predicates.py`（谓词安全求值，6 用例）
- `test_basic_comparisons`：`==`、`>=` 基本比较。
- `test_werewolf_win_condition`：`werewolf_count >= good_count` 为真。
- `test_boolean_and_arithmetic`：`and`、`not`、`+` 组合。
- `test_unknown_variable_raises`：引用未知变量抛错。
- `test_validate_rejects_unknown_names`：`validate` 拒绝允许集外变量。
- `test_no_arbitrary_code_execution`：`__import__('os')` 被拒绝——证明非 eval、无代码执行风险。

## `tests/test_compiler.py`（规则编译，8 用例）
用一个内联 `MINIMAL` Rule.md 文本作样本。
- `test_compile_minimal`：最小规则编译，校验 slug/角色集/actor_roles/start_phase。
- `test_builtin_werewolf_compiles`：内置狼人杀编译，校验人数边界、阵营、Villager=rest、女巫两能力。
- `test_builtin_avalon_compiles`：阿瓦隆样本结构上能解析+编译，阶段引用正确。
- `test_unknown_primitive_rejected`：把 eliminate 改成不存在的 `teleport` → `CompileError`。
- `test_dangling_phase_reference_rejected`：`next` 指向不存在阶段 → `CompileError`。
- `test_unknown_actor_role_rejected`：actors 引用不存在角色 → `CompileError`。
- `test_bad_win_predicate_rejected`：谓词引用未知变量 → `CompileError`。
- `test_all_primitives_registered`：九个原语都在注册表。

## `tests/test_engine.py`（引擎契约，10 用例）
fixture `werewolf_def` 加载内置定义；`make_state` 建 n 人局。
- `test_init_assigns_all_roles`：8 人局角色配额 = 2 狼/1 预言家/1 女巫/4 平民，起始阶段 night。
- `test_player_count_bounds`：3 人（低于 min 6）抛 `ValueError`。
- `test_actors_to_act_in_night`：夜晚行动者只来自 狼/预言家/女巫，平民不在内。
- `test_seer_investigate_is_private`：预言家查验产出 `PRIVATE` 事件且 audience 是本人。
- `test_illegal_action_rejected`：平民夜晚提交查验 → `IllegalActionError`。
- `test_full_night_then_vote_progresses`：所有夜晚行动者行动后 advance，进入 day_discussion，存活数不增。
- `test_check_win_good_when_no_wolves`：手动杀光狼 → 好人胜。
- `test_check_win_werewolf_parity`：杀到狼≥好人 → 狼胜。
- `test_engine_does_not_import_network_or_llm`：读引擎源码，断言不含 `import fastapi/redis/langgraph/websockets`——
  守护"引擎纯逻辑"这一架构约束（§11）。

## `tests/test_autoplay.py`（端到端自动对局，参数化多用例）
- `test_werewolf_game_converges`（seed 0/1/7/42/123）：整局必收敛，winner 非空且属于两阵营之一。
- `test_winner_consistent_with_alive_counts`：胜者与存活计数自洽（好人胜→无狼；狼胜→狼≥好人）。
- `test_various_player_counts`（6/8/10/12 人）：各人数均跑通且席位数正确。
- `test_event_log_is_ordered`：事件 `seq` 升序且连续无洞（0..n-1）。

## `tests/__init__.py`
空文件，使 `tests` 成为包。
