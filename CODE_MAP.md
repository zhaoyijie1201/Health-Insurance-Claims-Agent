# 代码地图

按 A2 starter scaffold 的模块结构组织：九个平铺的 `.py` 文件在仓库根目录，没有包、没有第三方依赖。scaffold 原件、Class 4 notebook 和我们的第一版实现都在课程文件夹的 `reference/` 下，不在仓库里。

| 文件 | 行数约 | 内容 |
|---|---|---|
| `config.py` | 110 | **唯一改配置的地方**。BACKEND / MODEL / BASE_URL、护栏上限、autonomy、价格、数据路径。环境变量 `A2_BACKEND`、`A2_MODEL`、`A2_PRICE_TIER`、`A2_DATA`、`OPENROUTER_API_KEY` 可覆盖 |
| `tools.py` | 380 | **工具层**。v2 六个工具、v1 七个工具各自的 REGISTRY 和六字段 DESCRIPTORS；narrative 扫描、四项重复匹配；`issue_decision_letter` 是唯一的写操作 |
| `prompt.py` | 120 | **模型看到的文本**。路由规则 + 描述符 + 依赖规则 + JSON 应答格式。`python run_eval.py --prompt` 打印全文和 token 数 |
| `backends.py` | 300 | **模型接口**。`decide()` 是 scripted 策略（careful / sequential / repeats / credulous），只读 transcript 里已有的 observation；`_live_call()` 是全仓库唯一知道厂商存在的函数 |
| `agent.py` | 190 | **主循环** `run_case()`。每次模型调用：ASK → METER → 预算检查 → 结论或执行多个工具调用 → 追加观察。所有仪表在这里记录 |
| `guardrails.py` | 90 | **护栏层** `Guardrails`。step cap、budget ceiling、去重、autonomy 门；每次触发都记入 `fired` |
| `harness.py` | 230 | **评估框架**。`code_check()` 对答案键做代码检查；`run_set()` 按负例三次 trial 跑集合，写 `results/eval_<label>.{json,md}`，失败运行的 transcript 存到 `results/transcripts/` |
| `run_eval.py` | 100 | 命令行入口。**评分者跑的就是它** |
| `run_guardrails.py` | 200 | D3(b) 护栏清单 11 条 + 1 条对照，写 `results/guardrails.md` |
| `demo_loop_failure.py` | 110 | D7 失败 1：循环失败，四项报告 + 前后表，写 `results/d7_loop_failure.md` |
| `demo_tool_failure.py` | 90 | D7 失败 2：工具接口失败（narrative 注入），写 `results/d7_tool_failure.md` |

## 读代码的建议顺序

1. `tools.py`：agent 能做什么。先看 v2 六个函数，再看底部 DESCRIPTORS 的 v2 和 v1 对照。
2. `prompt.py`：模型被告知什么。`--prompt` 打印出来读一遍。
3. `agent.py`：怎么循环。一个 while 循环，读完就读完了整个 agent。
4. `backends.py` 的 `decide()`：scripted 后端每一轮怎么决策。
5. `harness.py` 的 `code_check()`：怎么评分。

## 一次运行的形状

```
turn 1   get_claim(claim_id)                                     单独先跑
turn 2   lookup_policy ‖ lookup_hospital ‖ check_coverage × N     互相独立，一轮发完
turn 3   get_preauthorisation(...)                               只对 requires_preauth 的 line
last     issue_decision_letter(...)  仅 approve，过门，返回 recorded 后运行结束
   或    final {decision: escalate | request_document}            不发信，不过门
```

turns 只数调工具的轮；结尾的 `final` 计入 `model_calls` 和 token，不计入 turns。这和 Appendix A 一致：CLM-8842 是 4 turns 8 次调用，CLM-8925 是 2 turns。

## 模块的职责边界

- **门在写操作前面，不在 agent 前面。** `agent.py` 在调用 `issue_decision_letter` 之前先做 `tools.validate_decision()`（无效记录不会拿去问人），再过 `guards.gate()`，通过后工具追加一条记录到 `results/decisions.jsonl`。
- **escalate 和 request_document 通过 `final` 结束**，不调写工具。`validate_final()` 拒绝没有 trigger 的 escalate 和没有 missing 的 request；`final` 里写 approve_in_principle 会被拒绝（G11）。
- **停止一定是大声的。** 被护栏停下的运行 `decision` 是 None，`stopped_by` 写明是哪个护栏。它不会伪装成 escalate。
- **v1 和 v2 的区别只在工具层。** prompt 里的路由规则、循环、护栏三者完全相同，`--tools v1` 切换。v1 多一个 `check_duplicate_claim` 工具，`get_claim` 不做扫描，写操作没有 narrative 拦截。
- **SCRIPTS 机制保留。** `run_case(script=[...])` 逐条回放显式的 move 列表，护栏清单和 D7 用它构造特定的坏行为；日常评估由 `decide()` 策略驱动，不需要为每条案例手写脚本。

## 常用命令

| 目的 | 命令 |
|---|---|
| scripted 完整评估（D5a） | `python run_eval.py` |
| 单条 trace | `python run_eval.py CLM-8842` |
| 演示时由人在门口确认 | `python run_eval.py CLM-8842 --ask` |
| 看 prompt 和它的 token 数 | `python run_eval.py --prompt` / `--prompt --tools v1` |
| D2(c) 改前：每轮一个动作 | `python run_eval.py --policy sequential` |
| D2(b) v1 工具层 | `python run_eval.py --tools v1` |
| D3(b) 护栏清单 | `python run_guardrails.py` |
| D7 失败 1 / 失败 2 | `python demo_loop_failure.py` / `python demo_tool_failure.py` |
| 一个 live 电池（D5b） | `python run_eval.py --backend live --model openai/gpt-4o-mini` |
| v1 对照（D2b，同一模型） | `python run_eval.py --backend live --model openai/gpt-4o-mini --tools v1` |

## 目前 scripted 后端的结果（2026-09-05，40 条案例，21 条负例，82 trials）

| 运行 | 通过 | turn 中位/最大 | 输入 token | 说明 |
|---|---|---|---|---|
| careful v2（并行） | 82/82 | 2 / 4 | 618,594 | CLM-8842 正好 4 turn，CLM-8925 正好 2 turn |
| sequential v2 | 82/82 | 2 / 10 | 891,205 | 并行比串行少 31% 输入 token；最长合法运行 CLM-9007 十轮 |
| careful v1 工具 | 70/82 | 3 / 4 | 451,493 | 四条敌意文本案例全挂；prompt 更短但不安全 |
| repeats，去重开 | 21/82 | 3 / 3 | 511,430 | 61 次在第 3 轮被 duplicate_action 拦下 |
| repeats，去重关 | 21/82 | 12 / 12 | 2,350,340 | 61 次跑到 step cap；预算上限没触发 |
| credulous v1 / v2 | 70/82 / 82/82 | | | v2 写操作 BLOCKED 后转 escalate |

token 数是 scripted 的 chars/4 估算，结构和 live 账单一样（前缀每轮重发）；live 路径改用 API 返回的 usage。
案例集的构成见 `docs/EVALUATION_SET.md`。
