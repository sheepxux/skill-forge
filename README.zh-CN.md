<p align="center">
  <img src="assets/skill-forge-logo.png" alt="Skill Forge logo" width="360">
</p>

# Skill Forge 技能锻造器

[![Release Checks](https://github.com/sheepxux/skill-forge/actions/workflows/release-checks.yml/badge.svg)](https://github.com/sheepxux/skill-forge/actions/workflows/release-checks.yml)
[![ClawHub package](https://img.shields.io/badge/ClawHub-skills--forge-2ea44f)](https://clawhub.ai/sheepxux/skills-forge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[English](README.md) ｜ 简体中文**

**Skill Forge（技能锻造器）是面向自我演化型 LLM Agent 的签名审批 skill 流水线。** 从日志里检测能力缺口、按 profile 生成脚手架、跑验证器评分，再用 HMAC 绑定的审批令牌守住每一次 install 与 update 的状态变更。

当前版本：**`v1.4.0 "Evolve First"`**。

---

## 为什么需要 Skill Forge

绝大多数"自我改进型 Agent"工具的默认设计是：Agent 失败 → Agent 自己写一个新 skill → Agent 自己装上去。这套流程在 demo 里看起来惊艳，到生产环境就会出事——一个有问题的 skill 静默覆盖一个能用的 skill，没有审计、没法回滚、也没法判断"新装的这个到底比之前那个好还是更差"。

Skill Forge 把生命周期拆成 **detect → generate → validate → evaluate → install → evolve** 六段，每一步都是可签名、可校验、可回滚的：

- **自动检测**：从 `.learnings`、错误日志、需求记录里检测重复出现的能力缺口，让问题在变成"长期失败"之前浮出来。
- **按 profile 生成**：`academic` / `product` / `integration` / `script` / `workflow` 五种 profile，配套的 references 和 quality gates 都是该 profile 真实需要的。
- **量化打分验证器**：检查 frontmatter、章节、触发词、references、profile 专属行为。`milestone` 等级要求真结构，不是凭感觉。
- **签名审批门**：每一次 install 或 replace 都需要一个 HMAC-SHA256 签名 token，绑定 skill 名、目标路径、安装方式、源目录路径、源目录内容的 SHA-256 哈希。审批后篡改候选目录 → 立刻失效。`--apply` 直接调用永远 blocked。
- **Replay 非回归门**：当目标位置已经装着同名 skill，候选会和已安装基线跑同一批脱敏的 replay cases，候选回归 → install 被拦下。
- **Evolve-first 路由**（`--prefer-evolve` opt-in）：在 forge 新 skill 之前，先判断是否应该让某个已装 skill 进化——同 profile、足够的触发词 / 主题 / 名字重叠就路由到 evolve。防止 skill 集合膨胀（"装了 12 个相似的 citation skill"），同时签名门 + 回归门仍然守住实际的状态变更。
- **审计追踪**：`flock` 保护、原子写入的 manifest，含完整版本历史与回滚能力。
- **隐私优先的反馈**：写盘前自动脱敏邮箱、JWT、PEM 私钥、Telegram bot token、常见云/Git/Slack token 前缀、IPv4/v6、带分隔符的电话号。
- **确定性发布基准**：每个 profile 都有固定的基准用例 + 验证、隐藏 eval、行数、运行时长四组预算，质量门不会在版本之间漂移。

---

## 30 秒上手

[安装](#安装)之后跑这条安全的 plan-only smoke test：

```bash
python3 skill-forge/scripts/skill_forge.py demo --json
```

期望行为：

- 检测到内置的 `citation-helper` 示例
- 分类为 `academic` profile
- 在 `./generated-forge-demo/citation-helper` 生成候选 skill
- 验证为 `grade=milestone`
- 打印 install plan 后以 `install_status=planned` 退出
- **不会变更**任何已安装的 skill

走 Telegram 真实审批安装：

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

python3 skill-forge/scripts/skill_forge.py forge \
  --source skill-forge/examples/sample-feature-requests.md \
  --source skill-forge/examples/sample-errors.md \
  --output ./generated \
  --install telegram \
  --agent-name StudyAgent \
  --json
```

流水线会发一条与候选目录内容哈希绑定的 Telegram 审批消息，等你回复 `yes` / `同意安装`，再校验签名 token 才动文件。

---

## 安装

从 [ClawHub](https://clawhub.ai/sheepxux/skills-forge) 安装：

```bash
clawhub install skills-forge
clawhub install somnia            # 可选：夜审 companion
```

ClawHub 上的包名是 `skills-forge`（`skill-forge` 这个 slug 已经被另一个发布者占用），但 skill 元数据名仍是 `skill-forge`。ClawHub 可能会显示安全警告，因为本 skill 含 Telegram 审批和本地 install/rollback 脚本——先看源码再装。

本地开发，把仓库 symlink 到 OpenClaw workspace：

```bash
mkdir -p ~/.openclaw/workspace/skills
ln -sfn "$PWD/skill-forge" ~/.openclaw/workspace/skills/skill-forge
ln -sfn "$PWD/../somnia"   ~/.openclaw/workspace/skills/somnia      # 如果同级 clone 了 somnia
```

配置 Telegram 审批：

```bash
cp .env.example ~/.openclaw/skill-forge.env
# 编辑 ~/.openclaw/skill-forge.env，填入 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID
```

确认环境就绪：

```bash
python3 skill-forge/scripts/skill_forge.py doctor \
  --env-file ~/.openclaw/skill-forge.env --json
```

> **关于 `doctor` 这个名字**：这是命令行工具圈的通用约定（`brew doctor`、`flutter doctor`、`npm doctor`、`gem doctor` 都是这个名字），含义统一为"诊断本地环境是否就绪"。沿用约定让用过其他工具的开发者零学习成本上手。

---

## 签名安装门是怎么工作的

```
┌─────────────────────┐
│   候选 skill 目录    │  ─┐
└─────────────────────┘   │   sha256(目录内容) ─┐
                          │                     │
            ┌─────────────▼──────────────┐      │
            │ telegram_approval.py       │      │
            │  - 发送 Telegram 消息       │      │
            │  - 等待回复                │      │
            │  - HMAC 签名 token，包含：   │ ────┤
            │      skill, target,        │      │
            │      method, source_dir,   │      │
            │      source_hash, mode,    │      │
            │      issued_at, expires_at │      │
            └─────────────┬──────────────┘      │
                          │ approval_token      │
            ┌─────────────▼──────────────┐      │
            │ propose_skill_install.py   │      │
            │   --apply --approval-token │      │
            │  - 校验 HMAC               │      │
            │  - 校验过期时间             │      │
            │  - 重算 source_hash        │ ◄────┘
            │     校验每一项 claim       │
            └─────────────┬──────────────┘
                          │ 全部通过
                          ▼
                   原子 + flock 写入
                       manifest
```

没有 `--approved-by-telegram` 这种声明性 boolean。**Token 本身就是门**。HMAC 密钥优先用 `SKILL_FORGE_APPROVAL_SECRET` env，否则从 bot token 确定性派生（确保所有能访问 bot 的环境都能验证它发出的 token）。

`mode=dry-run` 的 token（`--telegram-dry-run approve` 触发）默认会被 `--apply` 拒绝，除非显式传 `--allow-dry-run-install`；那种情况下 audit 字段写 `approved_by=dry-run` 而不是 `telegram`。流水线对外报 `install_status=dry-run-blocked`。

## Evolve-first 路由怎么工作（v1.4.0+，opt-in）

```
                  ┌────────────────────────────┐
detect  ──→  ──→  │ decide_skill_action.py     │
opportunity       │  对每个已装 skill：         │
                  │   - profile 是否相同（硬门）│
                  │   - trigger 重叠度          │
                  │   - 主题词重叠度            │
                  │   - 名字重叠度              │
                  │   - 名字完全相同 → fitness │
                  │     直接 1.0               │
                  └─────────────┬──────────────┘
                                │
            ┌───────────────────┼────────────────────┐
            ▼                   ▼                    ▼
    fitness ≥ 阈值       0.4–阈值              fitness < 阈值
    且明显领先          或 top-2 在               或没有候选
            │           ambiguous_margin 内              │
            ▼                   ▼                       ▼
    路由到 evolve       ambiguous（v1.4 暂时        forge 新 skill
    + 写入 source=     回退到 forge 并在 payload    （默认 scaffold 流程）
    forge-routing       里曝光供人工 review）
    的合成 feedback
```

在 `forge` 上加 `--prefer-evolve` 启用（或单独调 `decide` 子命令）。v1.x 默认 off 保持向后兼容。

设计目的：当用户的请求其实只是"已装 skill 的一组新触发词"时，路由器会防止 skill 集合膨胀。即便路由错了，**replay 非回归门会在下游兜住**——候选用同一批基线 cases 评分，回归就拦下，manifest 永远见不到坏的 install。

## Replay 非回归门是怎么工作的

`evolve` 跑在已经装好的 skill 上时，候选**和**已安装基线会用同一批脱敏 replay cases 评分。下面这个条件成立就拦下 install：

```
candidate_score - baseline_score < --min-replay-improvement   # 默认 0
```

Replay 评分是离线的关键词/覆盖度检查——毫秒级、确定性、不需要 API key。它能可靠抓住最常见的回归形态："有人删掉了原本回应用户投诉的那段说明"。如果你想关掉硬阻断只保留覆盖度评分，传 `--min-replay-improvement -100`。

---

## 和其他工具相比

| 能力 | Skill Forge | LangChain Hub | AutoGen skills | OpenAI Apps SDK | 手工 prompt |
| --- | :---: | :---: | :---: | :---: | :---: |
| 从 Agent 日志自动检测能力缺口 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 量化质量验证器（评分 + 等级）| ✅ | ❌ | ❌ | 平台审核 | ❌ |
| profile 专属脚手架（5 种 profile）| ✅ | ❌ | ❌ | ❌ | ❌ |
| 安装需要签名审批 token | ✅ HMAC + source-hash | ❌ | ❌ | 平台审核 | ❌ |
| 候选被改动 → 审批失效 | ✅ | ❌ | ❌ | n/a | ❌ |
| 升级时回归对比已安装基线 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 审计追踪 + 回滚 | ✅ 原子 + `flock` | ❌ | ❌ | 平台侧 | ❌ |
| 反馈写盘前脱敏 | ✅ | ❌ | ❌ | 平台侧 | ❌ |
| 确定性发布基准 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 运行时 / 托管要求 | 无，本地 Python 3.9+ | hub 拉取 | 本地 Python | OpenAI 托管 | 无 |
| License | MIT | MIT | MIT | 闭源 | n/a |

Skill Forge 是 LangChain Hub / AutoGen / 你自己的内部 registry 的**互补品**。它们解决"分享 prompt 和模块"，Skill Forge 解决"在装进 agent runtime 之前要不要审、能不能回滚、是不是真的更好"。把 Skill Forge 放在任何一个 registry **之前**就行。

---

## Forge Console 命令参考

`scripts/skill_forge.py` 是统一的产品入口。所有子命令都接受 `--json`。

| 命令 | 用途 | 是否变更状态 |
| --- | --- | --- |
| `doctor` | 检查本地就绪：包、Python 版本、OpenClaw 路径、Telegram 配置、审批密钥、ClawHub、CI、git 状态 | 无 |
| `demo` | 跑内置 `citation-helper` 示例的 plan-only 演示 | 无 |
| `forge` | 检测、生成、验证、评估，并可选申请 install 审批。加 `--prefer-evolve` 先走 `decide` 路由 | 仅在签名审批后 install |
| `decide` | 给定 opportunity，判断该 evolve 已装 skill 还是 forge 新的。返回 `evolve` / `forge` / `ambiguous` 加每个候选的 fitness | 无 |
| `evolve` | 基于反馈和 replay 回归门提交 reviewed update 候选 | 仅在签名审批后 install |
| `install` | 打印或应用某个候选 skill 的 install plan | apply 需要签名审批 |
| `uninstall` | 打印或应用 uninstall / 回滚 | apply 需要签名审批 |
| `feedback` | 记录脱敏反馈给后续 evolve 用 | 写 feedback JSONL |
| `replay` | 用 replay cases 给一个 skill 目录打分 | 无 |
| `release-check` | 跑发布门 + secret scan | 无 |
| `version` | 打印产品版本 | 无 |

源码仓库环境下，最常用的几条门也封装成了 `make`：

```bash
make doctor          # 就绪检查
make demo            # plan-only smoke test
make benchmark       # 各 profile 的确定性基准
make package-check   # 完整 release-checks + secret scan
```

需要直接调底层脚本（`detect`、`generate_skill_scaffold`、`validate`、`propose_skill_install`、`telegram_approval`、`propose_skill_update`、`record_skill_feedback`、`evolve_skill_pipeline`、`replay/*`、夜审、调度）的话，参见 [`docs/manual-workflow.md`](docs/manual-workflow.md)。

---

## 运行模式

**Install modes**（`forge` / `evolve` 的 `--install`）：

| 模式 | 行为 |
| --- | --- |
| `plan` *(默认)* | 仅打印 install plan。不变更状态。 |
| `telegram` | 发送 Telegram 审批请求，校验签名 token 后才动文件。 |
| `ask` / `auto` | 已被禁用的兼容别名。本地审批不能 mutate skill。 |

**Evaluation modes**（`--eval`）：

| 模式 | 行为 |
| --- | --- |
| `hidden` *(默认)* | 跑 smoke check；对外隐藏内部用例。 |
| `details` | 开发者模式；暴露内部 check 细节。 |
| `off` | 跳过评估。 |

**Replay modes**（`--replay`）：

| 模式 | 行为 |
| --- | --- |
| `hidden` *(evolve 和夜审的默认)* | 跑 replay 检查；隐藏 case 细节。 |
| `off` | 跳过 replay。 |

`--min-replay-improvement <N>` 控制回归门（默认 `0`，即不允许回归）。传 `-100` 关闭。

---

## 配置

Telegram 审批读取这些 env（含 OpenClaw 别名）：

| 用途 | 默认 env | 别名 |
| --- | --- | --- |
| Bot token | `TELEGRAM_BOT_TOKEN` | `OPENCLAW_TELEGRAM_BOT_TOKEN` |
| Chat ID | `TELEGRAM_CHAT_ID` | `OPENCLAW_TELEGRAM_CHAT_ID` |
| HMAC 密钥 | `SKILL_FORGE_APPROVAL_SECRET` *(可选；默认从 bot token 派生)* | — |

发现顺序——首个存在的值生效：

1. 显式 `--env-file <path>`
2. `~/.openclaw/telegram.env`
3. `~/.openclaw/skill-forge.env`
4. `~/.openclaw/.env`
5. `~/.openclaw/workspace/telegram.env`
6. `~/.openclaw/workspace/.env`
7. 进程环境变量

审批回复词（大小写不敏感、单词整匹配；reply 优先于子串匹配）：

| 决策 | 接受的词 |
| --- | --- |
| 同意 | `y`, `yes`, `approve`, `approved`, `同意`, `同意安装`, `安装`, `确认` |
| 拒绝 | `n`, `no`, `reject`, `rejected`, `拒绝`, `拒绝安装`, `取消`, `不同意` |

非 reply 的消息体里必须出现审批消息打印的 Request ID 才被认作匹配同一次请求。

完整的夜审 / env-file / 回滚细节见 [`docs/manual-workflow.md`](docs/manual-workflow.md)。

---

## 仓库结构

```text
skill-forge/
├── README.md / README.zh-CN.md
├── SECURITY.md
├── RELEASE.md
├── CONTRIBUTING.md
├── SUPPORT.md
├── LICENSE
├── Makefile
├── .env.example
├── assets/
│   └── skill-forge-logo.png
├── docs/
│   ├── manual-workflow.md
│   └── launch/                    # 推广 / launch 资产
├── tests/
│   └── run_release_checks.py
└── skill-forge/                   # 实际发布的 skill 包
    ├── VERSION
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── examples/
    ├── references/
    └── scripts/
        ├── skill_forge.py         # Forge Console
        ├── forge_pipeline.py
        ├── detect_skill_opportunities.py
        ├── generate_skill_scaffold.py
        ├── validate_skill_candidate.py
        ├── evaluate_skill_candidate.py
        ├── lib/                   # approval, install_flow, runtime, telegram_config, policy
        ├── install/               # propose_skill_install + telegram_approval
        ├── evolve/                # propose_skill_update, record_skill_feedback, evolve_skill_pipeline
        ├── replay/                # collect / run / compare / redact / report
        ├── security/scan_secrets.py
        ├── somnia/                # 夜审运行时
        └── templates/profile_packs.py

../somnia/                          # 可选 companion，独立目录/仓库
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/                        # 委托到 skill-forge/.../somnia 的薄 shim
```

每个 `install/`、`evolve/`、`replay/`、`somnia/` 下的脚本在 `skill-forge/scripts/*.py` 都有向后兼容包装。

---

## 发布与贡献

发布前在本地跑完整 release suite：

```bash
make package-check
# 或：
python3 tests/run_release_checks.py
python3 skill-forge/scripts/security/scan_secrets.py --json
```

两条 GitHub Actions workflow 守 `main` 与 PR：

- **Release Checks** —— 跑全部 26+ 条断言（compile、secret scan、validation、forge plan、console doctor/demo、install gate、签名 token 正向路径、篡改拒绝、dry-run 拦截、缺源拒绝、uninstall token gate、replay、somnia review）。
- **Benchmarks** —— 各 profile 的确定性基准，含评分 / 行数 / 运行时长预算；上传 JSON artifact。

签名门协议、dry-run 拒绝语义、redactor 覆盖范围、锁机制保证见 [`SECURITY.md`](SECURITY.md)。发布 checklist 见 [`RELEASE.md`](RELEASE.md)。贡献流程与代码规范见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。需要支持或反馈见 [`SUPPORT.md`](SUPPORT.md)。

欢迎通过 Issues 和 Discussions 贡献（`💡 Skill Showcase` 分类专门用来分享你 forge 出来的 skill）。提 PR 前请先跑 `make package-check`。

---

## 配套 skill：Somnia

`somnia` 是一个薄包装，通过 `runpy.run_path` 委托到 Skill Forge 的夜审运行时。当你希望 agent 把维护工作路由到一个独立入口时用它（定时健康报告、replay 回归检查、睡眠时段升级提案）。Somnia 自己永远不会装/替换 skill——所有 mutation 仍走 Skill Forge 的签名门。

Somnia 当前版本：`v0.6.0 "Quality Aligned"`。

---

## 最近版本

- `v1.4.0 "Evolve First"` —— 新增 `decide` 子命令和 `forge --prefer-evolve` 路由，让 opportunity 在新 forge 之前先看能否进化已装 skill。同 profile 是硬门，名字完全相同短路到 fitness 1.0。合成 feedback 标记 `source=forge-routing` 保持审计时间轴可追溯。
- `v1.3.0 "Benchmark Pipeline"` —— 5 种 profile 的确定性基准用例；validation/eval/runtime 预算；`make benchmark`；专门的 GitHub Actions workflow 上传 JSON artifact。
- `v1.2.0 "Quality Refinement"` —— 脚手架 description 锚定用户提供的 trigger；workflow 章节升级为 milestone-grade 必需；编号步骤奖励只统计 workflow 节段；冗余文档检测大小写不敏感；`version` / `license` / `author` 进入 frontmatter 白名单。
- `v1.1.0 "Skill Quality Engine"` —— 精简的 SKILL.md 主体、progressive resource loading、execution mode 标注、富 trigger 的 frontmatter，以及拒绝 README/CHANGELOG 类文档污染 agent 上下文的验证规则。
- `v1.0.x "Forge Console"` —— 统一的产品 CLI 覆盖 doctor / demo / forge / evolve / install / uninstall / feedback / replay / release-check / version。
- `v0.5.0 "Signed Gate"` —— HMAC 签名审批 token + 源内容哈希绑定；replay 非回归门；原子 + `flock` 锁的 manifest 写入；扩展的 redactor。

完整历史（v0.1.0 → 当前）见 [`RELEASE.md`](RELEASE.md) 和 [GitHub Releases 页面](https://github.com/sheepxux/skill-forge/releases)。

---

## License

MIT。见 [`LICENSE`](LICENSE)。
