# 02 · 规则摄取管线 `app/rules`（§7）

管线四步：①文书提取 → ②LLM 结构化为 Rule.md → ③人工审校 → ④受控编译为 GameDefinition。
本目录实现了③后的 schema 解析与④编译（可运行），①②为 Phase 4 占位。

---

## `app/rules/primitives.py` 🟢 — 能力原语库（§7.3）

**核心思想**：编译器只认有限的一组可组合原语；Rule.md 里每个能力必须映射到其一。这样"生成任意游戏"
被约束在安全、可测的范围内——这是**可控性与表达力的刻意权衡**。新机制要走"扩展原语"评审（写新
primitive + 测试），而不是在 Rule.md 里塞任意逻辑。

### `class Primitive`（`@dataclass(frozen=True)`）
描述一个原语：`name`（标识）、`semantics`（语义说明）、`params`（允许的参数名元组，供编译期校验）。

### `REGISTRY: dict[str, Primitive]`
九个原语的注册表（§7.3 表格逐一对应）：
`eliminate`（移除玩家）、`protect`（抵消一次 eliminate）、`investigate`（向行动者揭示目标信息）、
`vote`（群体计票）、`nominate`（提名/组队）、`reveal`（向范围公开信息）、`swap`（交换属性）、
`assign`（分配角色/标记）、`speak`（发言进频道）。每个都登记了允许的参数键。

### `is_known(name) -> bool`
原语名是否在注册表中。编译器与阶段校验用它快速判断。

### `get(name) -> Primitive`
取原语；不存在时抛 `KeyError`，错误信息会列出已知原语并提示"新机制需扩展原语库，不要在 Rule.md 塞逻辑"。

### `all_names() -> set[str]`
返回全部原语名集合。供编译器做参数/谓词允许集校验与测试断言（test_compiler 断言九原语齐全）。

---

## `app/rules/schema.py` 🟢 — Rule.md 规范与解析（§7.2）

**格式约定**：`Rule.md` = YAML frontmatter（元信息 + 机器可读的 roles/phases）+ 结构化正文（人类可读文档）。
**设计取舍**：§7.2 在正文里用 markdown 描述角色/阶段便于人读，但供编译器消费的**权威定义放在
frontmatter**，正文是其人类可读镜像。这样解析稳健、可单测，同时保留"frontmatter + 正文"的形态。

### `class RuleParseError(ValueError)`
解析阶段错误（缺字段、frontmatter 不闭合、ability 写法非法等）。

### 中间表示 dataclass
- `AbilitySpec`：`primitive` + `params`（解析后的能力）。
- `RoleSpec`：`name / faction / count / abilities / channels`。
- `PhaseSpec`：`name / actors / actions / resolution_order / timer / next / on_complete / check_win`。
- `RuleSpec`：整份规则的解析结果（含 `start_phase` 与原始 `body` 正文）。

### `_parse_ability(raw) -> AbilitySpec`
兼容两种能力写法：
1. 显式 `{primitive: investigate, target: single_other, ...}` → 取 `primitive` 键，其余为 params。
2. 单键映射（§7.2 风格）`{investigate: {target: single_other, reveals: faction}}` → 键为原语名，值为 params。
非映射或多键无法识别时抛 `RuleParseError`。

### `_parse_role(raw) / _parse_phase(raw)`
把 frontmatter 里的角色/阶段字典转成 `RoleSpec`/`PhaseSpec`；阶段各字段带合理默认（actors 默认 all_alive，check_win 默认 False）。

### `_split_frontmatter(text) -> (dict, str)`
切分 frontmatter 与正文：要求文本以 `---` 开头，用 `text.split("---", 2)` 取出中间 YAML 与之后正文；
`yaml.safe_load` 解析；缺失或未闭合、非映射均抛 `RuleParseError`。

### `parse_rule_md(text) -> RuleSpec`
顶层入口：切分 frontmatter → 读取 slug/name/min_max_players/factions/win_conditions/roles/phases →
`start_phase` 缺省取第一个阶段名。缺必填字段抛 `RuleParseError`（带字段名）。
**注意**：这里只做语法/结构解析，**不做原语映射与引用闭合校验**——那是编译器的职责（关注点分离）。

---

## `app/rules/compiler.py` 🟢 — 受控编译 Rule.md → GameDefinition（§7.1 第④步）

**职责**：把 `RuleSpec` 编译成引擎可执行的 `GameDefinition`，并在编译期做全部受控校验。任一不满足即抛
`CompileError`，把错误挡在运行之前（§7.1/§15 风险缓解）。

### `class CompileError(ValueError)`
编译期校验失败（未知原语、未知参数、悬空阶段、未知角色、非法谓词等）。

### `_ability_def(spec) -> AbilityDef`
把 `AbilitySpec` 编译成引擎用的 `AbilityDef`：
1. 校验 `primitive` 在原语库（否则 `CompileError`）。
2. 校验 params 的键都在该原语声明的允许集合内（多余键报错）。
3. 解析 `visibility`（非法值报错）。
4. 把 `phase / uses / visibility` 抽到 `AbilityDef` 的专门字段，其余留在 `params`。

### `compile_rule_md(text) -> GameDefinition`
便捷入口：`parse_rule_md` → `compile_spec`。

### `compile_spec(spec) -> GameDefinition`
核心编译，按顺序做四组校验与构造：
1. **角色 + 能力**：禁止重名；角色阵营必须属于 `factions`；最多一个 `count="rest"`；每个能力经 `_ability_def`。
2. **阶段**：`start_phase` 必须存在；每个阶段的 `next` 必须指向已存在阶段（**引用闭合**）；`actors` 若为角色列表
   则解析成 `actor_roles` 并校验角色存在；阶段引用的 `actions`/`resolution_order` 原语必须已知。
3. **胜负谓词静态校验**：允许变量集 = `{alive_count} ∪ {<faction>_count}`；阵营必须已知；
   调用 `predicates.validate` 确认谓词只引用允许变量且语法合法。
4. 组装并返回不可变的 `GameDefinition`。

### `load_builtin(slug) -> GameDefinition`
读取并编译内置 `games/<slug>/Rule.md`（经 `builtin_rule_path`）；文件不存在抛 `FileNotFoundError`。

### `builtin_rule_path(slug) -> Path`
`resource_dir() / "games" / slug / "Rule.md"`——开发态指向仓库 `games/`，打包态指向 `_MEIPASS`。

---

## `app/rules/parser.py` 🟡 — 文书结构化（§7.1 ①②，Phase 4 占位）

### `class ExtractResult`（dataclass）
②的产物载体：`text`（提取出的原始文本）、`rule_md_draft`（Rule.md 草稿，待人工审校）、`warnings`。

### `extract_text(document_path) -> str` 🟡
①提取：从 PDF/docx/txt/图片抽文本（OCR 兜底）。当前 `NotImplementedError`。

### `structure_to_rule_md(raw_text) -> ExtractResult` 🟡
②结构化：用 LLM 从原始文本抽取角色/阶段/动作/胜负条件，产出 Rule.md 草稿。当前 `NotImplementedError`。
注释强调：抽取有歧义遗漏，草稿必须经第③步人工审校才允许编译。

## `app/rules/__init__.py`
重导出 `primitives`、`RuleSpec`、`parse_rule_md`、`compile_rule_md`、`load_builtin`、`CompileError`。
