# Bitter Lesson 审计综合 + U4 执行决策 — 2026-07-06

**输入**（均为 Codex GPT-5.5 pro/xhigh 独立上下文产出，Fable 已抽查核验）：
- `reviews/2026-07-06-codex-sharpen-v3-plan.md` — U4–U9 定稿 + U4 可执行 packet
- `reviews/2026-07-06-codex-bitter-lesson-audit.md` — 18 项违例审计 + 升级计划 + 对账

## 1. 两份报告的核心结论

### Task A（计划定稿）
- U4 READY-WITH-EDITS：给出了逐文件精确编辑（`<20%`→`<30%` 只需改 WADH 一处 3035 行；Gotchas 已是 `<30%`）、完整 TDD 测试脚本、Darwin guard 降级命令包（冻结决策重打分，因 R4-T4 无活体 runner）、分支/PR 清单。
- 5 个计划-现状矛盾被抓出，最重要的两个：U7 计划引用的 `test_state_schema_legacy_read.sh` 不存在；Darwin guard 按计划原文无法执行（只能 rescoring 降级）。
- U5 NOT-READY（owner-gated），U8/U9 READY。

### Task B（Bitter Lesson 审计）
- **3 个 scaling-blocker**：BL-01 Decision Contract 的 11 族枚举 JSON 表（把判断力变成标签复读）；BL-02 Darwin guard 把措辞冻结在 Sonnet 快照上（最好的 eval 资产 + 最坏的耦合）；BL-13 全部校准只对 Claude Sonnet 一个通道。
- **结构性违例模式**（每个都有 file:line 证据，已抽查确认）：grep 散文 tripwire 测试（21/40 个测试）、state.json 水合字段长文清单（21 个字段名硬编码在 SKILL.md）、手调常数（<30%、0.05、95/95、max_edits=3、exactly-3-lanes、30-40 fixtures、4-source/12-pattern/8-lead caps）、exactly-one-of-5 模式分类器。
- **保留清单**（模型无关的不变量，别动）：workspace 隔离、holdout 神圣性、stable input identity、confound fixture replay、human gates、domain oracle 边界。
- **升级计划 9 步**：契约分类（invariant/default_policy/rationale/deprecated）→ Darwin 转行为级 eval → schema 抽取 → grep 测试替换 → 路由瘦身 → 搜索可扩展化 → 阈值校准化 → 跨模型回放 → 退役 campaign/meta-steering。

## 2. 冲突点（需要 owner 决策）

**冲突 1：U4 怎么执行。** Task A 的 packet 会把 `<30%`、`threshold + noise_floor`、`margin < 0.05` 作为散文常数写死，并加一个新的 grep 契约测试——恰是 Task B 判定的 MAJOR 违例模式（BL-07/BL-08）。
- 选项 a（按 A 原样执行）：最快落地，忠于 v3 计划；代价是给未来升级再加一层要拆的措辞冻结。
- 选项 b（**推荐**，A 执行 + B 微修正）：同样的编辑，但措辞把常数标注为「默认策略，可按不确定性/样本量覆盖」（例：`margin < 0.05（默认 borderline 阈值，可校准）`）；新测试保留但定位为 docs-lint 而非行为证明。改动量 ≈ 零，方向兼容升级计划。
- 选项 c（PARK U4，直接启动升级计划）：最纯粹；代价是 U6 依赖 U4 的 threshold wire-in，v3 链条断裂，且 U4 修的是「不诚实信号」（stale 阈值矛盾、无噪声门的 keep 规则）——这本身是 invariant 级修复，不该等大重构。

**推荐 b 的理由**：U4 的常数全部生活在 advisory 层（headroom_advisory 明文「never an automated abort」）而非硬门——这已经是 Bitter-Lesson-friendly 的设计；把它们标成可覆盖默认值后，与升级计划第 7 步（阈值校准化）完全同向。

**冲突 2：U9（meta-learnings seed）。** Task A 判 READY，Task B 判 PARK（「把人类过去的发现变成未来模型的转向法则」= BL-17）。
- 可调和：按 U9 执行但**全部条目标 candidate、零 active、零 actionable_entry_ids**（= B 要的「optional evidence corpus」）。或者干脆 PARK 到升级计划第 9 步一起处理。推荐后者——U9 无依赖方，不挡任何路。

## 3. 推荐执行序列

1. **U4（选项 b）** — Codex 5.5 xhigh 执行，TDD（新契约测试先 RED）+ Darwin rescoring guard + 独立 code review → PR。
2. **U7 → U8** — 按 A 的 sharpening notes（U7 去掉不存在的文件引用；U8 原样）。均 PROCEED（B 认定强对齐）。
3. **U6** — U4 合并后执行，作为升级计划的「第一次瘦身」（B 的建议）。
4. **U5** — 维持 owner-gated，不动。
5. **U9** — PARK，并入升级计划第 9 步。
6. **升级计划立项** — 以 B 报告第 4 节为底稿另立 v4 计划文档（建议名：`docs/plans/2026-07-XX-bitter-lesson-dehardening-v4-plan.md`），关键首步：Darwin guard 从「措辞冻结」转为「行为 oracle」（R4 fixtures 保留，pass 条件从 exact-match JSON 改为 invariant 保持：安全边界/holdout 保护/证据要求不破）。这一步做完，后续所有 prose 简化才解锁。

## 4. 风险与诚实披露

- Darwin guard 降级：rescoring 无法捕捉「只在活体决策生成时出现的漂移」（A 的 Open Risk #1）。缓解：U4 PR body 明写此限制；升级计划的行为级 eval 才是真解。
- Task B 建议的「行为级 Darwin eval」在换措辞后需要真实模型跑决策生成——那是付费 run，按 CLAUDE.md paid-run pre-flight 走（dry-run + 成本预估 + owner go）。
- 本文档与两份 reviews/ 报告未提交 git（untracked），与既有 dirty state 一致，不影响 U4 的干净分支。
