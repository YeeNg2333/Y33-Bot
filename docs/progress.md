# 开发进度（progress）

本文件是 Y33-Bot 的**开发进度台账**，2026-10-28 从 `AGENTS.md` 迁出。

迁出原因：`AGENTS.md` 是**受保护的智能体指令文件**，写入需要人工交互批准；而进度每批都变，
无人值守的看板卡写不进去（上一轮 `BUGS.md` 与 `docs/acceptance.md` 里都留下了「进度未写入」的登记）。
进度、时间线、数字这类高频变动的内容放这里，看板卡与 worker **直接追加，不必再申请人批准**。

- **写进度只动本文件。** `AGENTS.md` 只在「仓库结构 / 工作规则 / 常用命令」这三类内容变化时才改。
- 缺陷记 `BUGS.md`，验收证据记 `docs/acceptance.md`，自测手册记 `docs/smoke.md`；
  本文件只做**时间线索引**，引用它们，不重复粘贴证据。

## 记录规则

1. **最新在前**。每条含三部分：日期（YYYY-MM-DD）、已完成、进行中、已知阻塞/待办。
2. 数字必须是**本机实跑**结果（pytest 例数 / 覆盖率 / ruff 文件数），不写「大概」「可能」。
3. 未执行的场景（如真机 S5 8 步）照实写「未执行 + 原因」，不许写成通过。
4. 卡号 / PR 号只写工具返回过的真实 id，别凭记忆写。

## 当前基线（最近一次实跑）

| 项 | 值 | 出处 |
|---|---|---|
| 用例 | **453 passed**，`tests/` 无 skip/xfail | `docs/acceptance.md` §10.4/§11.1/§12.1 |
| 覆盖率 | **99.33%**（门槛 70%） | 同上 |
| lint | `ruff check .` 全过；`ruff format --check .` **46 文件**合规 | 同上 |
| 日志模板真行 | **361/361 命中**（MISS 0；改前同一批行 101/361）；≤1.21.1 旧形态 **3/3** | `docs/acceptance.md` §10.1–§10.2 |
| 真机回归 | **四族 1.21.11 全通过**（原版 / Fabric / Forge 61.2.0 / NeoForge 21.11.48）：真事件行 8/8、14/14、14/14、14/14 命中；同一批真行换旧模板四族全 `FAIL`；三类出站 404（预期）；看门狗单段 1 次 / Fabric 两段 2 次 | `docs/acceptance.md` §13–§17 |
| 真机回归是否动了用例数/覆盖率 | **没有**：本批只改 `docs/`、`BUGS.md`、`test-notes/`，`src/` 与 `tests/` 零改动；2026-10-29 21:0x 在本机重跑 `pytest -q --cov=y33bot --cov-fail-under=70` → **453 passed in 50.04s**、`Total coverage: 99.33%`；`ruff check .` / `ruff format --check .` → `All checks passed!` / **46 files already formatted**（与上表逐项相同） | 本表 + `docs/acceptance.md` §17 |
| 发布 | `v0.1.0` annotated tag（指向 `f0ddd4e`）；v0.2 功能已合入 main | 下表 2026-10-13 条目 |
| 产品代码 | 2026-10-18 矩阵批**零改动**；2026-10-29 模板批同样**零改动**；2026-10-29 BUG-004 批改动 3 个 `src/` 文件（`mclog/patterns.py`、`mclog/watcher.py`、`service.py`）；2026-10-29 BUG-005 批改动 `qq/gateway.py`（超时文案可读化 + 去 `start()` 双前缀）、`qq/probe.py`（直连 opener）、`service.py`（`run` 启动前一次性探活，不重试） | `BUGS.md`「测试矩阵与证据来源」、`docs/acceptance.md` §10.5/§11/§12、`PLAN.md` §7.3/§7.4 |

> 数字变了要同步三处：`README.md` §14、`docs/smoke.md` §7（粘贴块里的例数行 + 下方「覆盖度」行两处）、
> `docs/acceptance.md` 的**最新一节**（当前是 §17），再回本表更新。
> 注意 `docs/acceptance.md` §1 总表与 §3 逐文件表是**变更前记录**（只加标注、不改写），不要再去改它们的数字。

---

## 2026-10-29（四族真机回归汇总落盘：原版 / Fabric / NeoForge 补齐 + BUGS 状态收口 + 两处「说过没落盘」补证据）

- 已完成：把这一轮**真机回归**的证据统一落到文档。原版与 Fabric 由本卡（`t_9e9040ed`）自己跑/采集，
  Forge（`t_f4d69bba`）与 NeoForge（`t_0ee0c2ff`）由父卡执行、本卡回读原文后归档 —— **每一条数字都对着
  `test-notes/regress/*/artifacts/` 原件核过**，没有照抄卡面摘要。
- 已完成：`docs/acceptance.md` 新开 **§14（原版 1.21.11）/ §15（Fabric 1.21.11）/ §16（NeoForge 21.11.48）/
  §17（四族汇总 + 证据分级口径 + harness 缺陷 + 未覆盖边界）**；§0–§13 正文未改写，只给 §13 追加
  **13.9 补证据**（把「日志变长后 14 条全部命中」这一行的落盘补上）。
- 已完成：`BUGS.md` —— BUG-002 / BUG-003 / BUG-004 的状态从「待真机回归」推进为
  **「已修复（真机已回归）」**（汇总表 3 行 + 索引 3 行 + 三条「状态」行），并各补一节「真机回归」：
  BUG-002 补原版/Fabric/NeoForge、BUG-003 补 NeoForge、BUG-004 补原版/Fabric/NeoForge（含 Fabric **2 次告警的定论**：
  两个独立连续段被 `Alex left the game` 打断 ⇒ 符合设计，**不开 BUG-006**）。
- 已完成：`test-notes/regress/vanilla-1.21.11/`、`fabric-1.21.11/`（README + `artifacts/` 全量逐字副本）新建；
  `regress/log-slice-events.txt`（四族事件行切片）新建；`forge-1.21.11/`、`neoforge-1.21.11/` 各补
  `check-new-latest.txt` / `check-old-latest.txt`。`test-notes/00-env.md` 补「实例目录跑完即清空 + 四族恢复配方」。
- 实测（真机）：原版 `check` 新模板 8/8 → **18/18**、旧模板 `FAIL 18 条中 8 命中 / 10 未命中`（8 = join 4 + quit 4）；
  Fabric 4/4 → **14/14**、旧模板 14 条中 6 命中 / 8 未命中；Forge 14/14、旧模板 14 条**全部未命中**；
  NeoForge 4/4 → **14/14（服务端在线时落盘，整条 `check` = `OK`）**、旧模板 9 条全部未命中。
  四族 E2E 均为 4 次真发送 = 3 类事件 + 1 条启动健康翻转，全部被 `api.sgroup.qq.com` 404 拒绝（预期）。
  看门狗：原版单段 1 次、Fabric 两段 2 次、Forge/NeoForge 单段 1 次；NeoForge 另做真机两段实验（2 段 ⇒ 2 次）。
- 已完成（口径）：新增 `docs/acceptance.md` §17.2 **证据分级表** —— 区分「服务端在线时的 `check`」「停服后补跑的
  `check`（只 `[日志模板]` 项有效，RCON 必 FAIL）」「`simulate` 逐行判读」「真客户端 E2E」「明确标注的合成行」，
  防止把补跑或合成行读成真机通过。
- 数字基线**未变**：本批只改文档与 `test-notes/`，`src/`、`tests/` 零改动；21:0x 重跑 `pytest` →
  **453 passed in 50.04s**、`Total coverage: 99.33%`、`ruff check .` 全过、`ruff format --check .` **46 文件**。
- 阻塞/待办：① `online-mode=true` 的签名聊天行仍未取证（四族实例都是 `online-mode=false`）；
  ② 四族各只打 1.21.11 一个点，Forge 1.21.3–26.3 / NeoForge 21.3–26.3 / 原版 26.2–26.3 / Fabric 其它组合仍只有格式取样；
  ③ QQ 真实投递属 S5；④ harness 的 `regress_start.sh` 起服判定（`"0\n0"` 致 `[: 0：需要整数表达式`）**只登记未修**，
  该行报成功/失败都不可信，真证据只看 `Done (…)` 行与端口。
- 本轮**没有机制变化**：`[log_patterns]`、看门狗、`check` 的语义与 `PLAN.md` §7.3/§7.4 登记的一致，
  故 `PLAN.md` 未动（无 §7.5 需要写）。
- 收尾：四族服务端均已停服（端口无监听、无 tmux 会话），可用内存 1583 → 1569 MB，磁盘余量 884 MB 未缩水。
- 载体：分支 `docs/regress-summary-four-families` → **PR #8**（https://github.com/YeeNg2333/Y33-Bot/pull/8），
  未直推 `main`；PR 正文含验收清单与四族实测表。

## 2026-10-29（真机回归 Forge 1.21.11：新出厂模板 14/14 命中 + `check` 三态 + 看门狗，BUG-002/003/004）

- 已完成：在 **Forge 61.2.0 / MC 1.21.11**（BUG-003 核心场景：加载器 logger 段 + `[Not Secure]`）上跑完整真机回归。
  被测副本 `~/Y33-Bot`＝main `8996a1d` 归档副本，`config.example.toml` / `src/y33bot/{service.py,mclog/watcher.py,mclog/patterns.py}` /
  `tests/test_log_patterns_real_lines.py` 的 sha256 与本机 main 工作树**逐一相等**。产品代码**零改动**（`src/`、`tests/` 未碰，本卡为验证 + 文档卡）。
  载体：`docs/acceptance.md` 新开 **§13**、`BUGS.md` BUG-002/003 各补「真机回归（Forge 1.21.11）」小节、
  原件 `test-notes/regress/forge-1.21.11/`（README + `artifacts/` 10 个逐字副本）。看板卡 `t_f4d69bba`。
- 实测（真机，20:15–20:31 +0800）：真行 `[2910月2026 20:28:31.611] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Steve joined the game`；
  新模板 `check` = `[日志模板 forge] OK 样例行 4 条全部命中（join 1 / quit 1 / chat 2）`，日志变长后 `OK 样例行 14 条全部命中（join 3 / quit 3 / chat 8）`；
  旧模板同一批行 `FAIL … 全部未命中` + `exit=1`；`simulate` join / `#` 聊天 / quit 均 `[群消息]`，普通聊天 `[忽略] 聊天非 # 开头，不转发`；
  真客户端 E2E（mineflayer，协议协商 1.21.11）产生 3 类出站 + 1 条启动健康翻转共 **4 次**打到 `api.sgroup.qq.com`，
  全部 404 `请求Query参数group_id无效`（假 `group_openid`，**预期成功信号**；归因实验 `run-healthonly.txt` 闭合差额）；
  旧模板看门狗 `[警告] 疑似事件行连续 3 条未匹配 [log_patterns]（forge）…` **只报 1 次**（连续 9 / 13 条仍是 1 次，模板正确时 0 次）。
- 已知：`check` 在「刚重启、日志里还没有事件行」时输出 `OK 未找到可判定的样例行，跳过` —— **跳过不算通过**，必须先把真客户端跑一遍。
- 阻塞/待办：① NeoForge（卡 `t_0ee0c2ff`）、原版 / Fabric、`online-mode=true` 的签名聊天行仍未回归；
  ② 看门狗「命中 → 重新武装 → 再报一段」的段间关系只有单测覆盖，真机没造出对齐点；
  ③ harness 两个脚本缺陷：`e2e_family.sh` 的 `re.sub` 字符串替换体在 Python 3.9 抛 `bad escape \d`
  （**已修**，服务器 `~/mc-test/harness/` 副本已更新，原件 `.bak-2026-10-29`）、`regress_start.sh` 的
  `grep -ac … || echo 0` 产出 `"0\n0"` 致误报 `启动结果: 失败`（**只登记未修**）。
- 收尾：**已停服**（端口 6 s 内消失、tmux 无会话、可用内存 747 → **1542 MB**、磁盘余量 1.1 GB 未缩水），NeoForge 卡可起服。
- 数字基线**未变**：`453 passed` / 覆盖率 `99.33%` / ruff `46 文件` / 真行 `361/361`（本卡不加用例，四处基线无需改）。

## 2026-10-29（日志模板改「四族通吃」+ 三方相等回归锁 + 全部文档载体同步）

- 已完成：出厂默认 `[log_patterns]` 三条模板换成「四族通吃」形态 —— 时间戳不再限 `HH:MM:SS`（吃 Forge 的
  `[1810月2026 …]`）、logger 段 `Server thread` / 旧版 `Async Chat Thread - #N` 二选一、可选模组加载器段
  `[…]`、`chat` 可选 `[Not Secure] ` 前缀；`encoding = "utf-8"` 显式声明。`config.example.toml`、
  `tests/conftest.py` 夹具常量、`PLAN.md` §3.5 样板三处**逐字同步**（卡 `t_2a31fd67` 出模板、`t_739a0487` 上锁）。
- 已完成：新增 `tests/test_log_patterns_real_lines.py`（28 例）= 三方逐字相等锁（6 例，§3.5 用 `tomllib` 解析）
  + 16 条内联行（13 条四族真机真行 + 3 条 ≤1.21.1 旧形态文档样例行）逐条断言 `kind`/`player`/`message`
  + 2 条非事件行不误判 + 2 条语义不变断言（卡 `t_739a0487`）。
- 已完成：`PLAN.md` §7.3 变更登记（原状 → 现行为 → 涉及文件），并明确登记「对 `IDEA.md:170` 冻结形态的偏离」
  （去 `time` 命名组、logger 二选一、新增可选 loader 段与 `[Not Secure] `）；§3.3 既有签名一行未动（卡 `t_33baa9bb`）。
- 已完成：`README.md` §5.1（三模板 + `encoding` 说明）/ §13 新增第 15 条 FAQ（群里收不到游戏内 `#` 聊天但进服
  通知正常 → 先看 `[log_patterns].chat`，含三种 dry-run 输出的处置表）/ §14 数字；`docs/smoke.md` S3 改为四族
  样例行并补「模板失配」表现、§7 两处数字；`docs/acceptance.md` 新开 §10（361/361 逐族命中表 + 改前 101/361
  对照 + pytest 数字），历史 §0–§9 只加「变更前记录」标注、原文未改写；本文件顶部基线表已更新。
- 实测（本机实跑）：`409 passed`、覆盖率 `99.33%`（门槛 70%）、`ruff check .` 与 `ruff format --check .` 全过
  （45 文件）；四族真行 **361/361** 命中（MISS 0，改前 101/361）；≤1.21.1 旧形态 **3/3**；红锁验证：回退
  `PLAN.md` §3.5 后三方相等 3 条全红，恢复后 28 例全绿。`src/` 零改动（`git diff main..HEAD -- src/` 为空）。
- 已完成：终局校验后推分支 `wt/t_e7da5bef` 并用 API 建 PR —— **PR #5**
  https://github.com/YeeNg2333/Y33-Bot/pull/5（标题 `fix(log_patterns): 出厂默认模板兼容 1.21.2+ 与
  Forge/NeoForge 布局`，正文首行 `Closes #1`，含「改前 101/361 → 改后 361/361」逐族对照表与真机「未执行 +
  原因 + 替代证据」）。推前在本卡工作树实跑：`409 passed` / `99.33%` / ruff 45 文件全过；`git diff main..HEAD
  -- src/` 与 `git diff main..HEAD -- IDEA.md 需求1.txt AGENTS.md` 均空。（卡 `t_e7da5bef`）
- 已完成：根卡 `t_13b9be2a` 终局复核（不引用子卡结论，全部重跑）：worktree 上 `git merge --no-ff 60db1aa`
  → 合并树 `e6efc29`（11 文件 / +706 −36），实跑 `409 passed` / 覆盖率 `99.33%`（门槛 70%）/ ruff check 全过 +
  format `45 files`；离线复扫出厂默认 **361/361**（MISS 0，改前同一批行 **101/361**）、≤1.21.1 旧形态 **3/3**；
  `git diff 73400e0..HEAD -- src/` 与 `-- IDEA.md 需求1.txt AGENTS.md` 均空。GitHub 侧：PR #5 `state=open`、
  `mergeable_state=clean`，head `60db1aa` 的 `test (3.12)` 两次运行 `success`；issue #1 仍 `open`（合并后由
  `Closes #1` 自动关闭）。`docs/acceptance.md` 增 §10.6 贴本轮复核实录，§1/§3 只加「变更后」指针标注
  （历史数字未改写）。
- 进行中：无。
- 阻塞 / 待办：**真机回归未执行** —— 本机没有四族 MC 服，真行取自 `test-notes/artifacts/` 的 2026-10-18 矩阵
  制品，不是本轮新采；有服环境后按 `docs/smoke.md` §3 回填。`docs/acceptance.md` §1/§3 保留「变更前记录」
  原文数字，只在旁边加指向 §10.4 的「变更后」标注；`IDEA.md` / `需求1.txt` 未改（偏离已在 `PLAN.md` §7.3 登记）。
- 遗留（需人工拍板）：`origin/main` 落后本地 main 20 个提交，PR #5 的 diff 因此含这些既有提交（797 文件，
  与 #4 同构）；是否 / 如何推 main 未擅自执行。`PLAN.md` §7.3 与 PR #4（BUG-005）撞号，后合并者顺延 §7.4。

---

## 2026-10-29（BUG-004 修复：日志零事件看门狗 + `check` 模板自检，issue #2）

- 已完成：issue #2 的四处改动全部落地（分支 `wt/t_5ce7f4af`，收口卡合并 3 个父分支）：
  - `src/y33bot/mclog/patterns.py` 新增与日志布局无关的 `looks_like_event`（`t_e2371cdc` / `a5d306b`）；
  - `src/y33bot/mclog/watcher.py` 零事件看门狗：只对**候选行**计数，连续 3 条未命中打**一次** `[警告]`，命中即清零重新武装；
  - `src/y33bot/service.py` `check` 新增 `[日志模板 <name>]`（`t_500f7787` / `19cbfef`）：全命中 OK、全未命中 FAIL、**部分命中 FAIL**、无候选 OK 跳过；
  - 契约与既有断言同步（`t_bf20a97b`：`PLAN.md` §3.4/§5 与 6 个测试文件）、新增 17 例（`t_ce82d1a3`）、文档（`t_c5c71e6c`：`README.md` / `BUGS.md`）。
- 已完成：本机实跑 —— `pytest` **398 passed**（381 → +17）、覆盖率 **99.36%**（99.33% → +0.03pp）、
  `ruff check .` / `ruff format --check .` 全绿（**44 文件**），`tests/` 无 skip/xfail；逐条输出见 `docs/acceptance.md` §10.1。
- 已完成：数字同步四处（`README.md` §14、`docs/smoke.md` §7 两处、`docs/acceptance.md` §1+§3、本文件基线表）；
  顺手补齐 `README.md` §7 两处旧 `check` 样例缺的 `[日志模板 main]` 行，并把 §13 第 15 条从「三种结果」改成实现真正的**四种结果**。
- 已完成：`BUGS.md` BUG-004「修复记录」按实际实现校对（三分支 → 四分支、新增用例数 5 → 17），原文与原始日志未改写。
- 真机对照（Forge 1.21.11）：**未执行** —— 测试机 `hermes@10.1.1.4` ping 通但 SSH 公钥认证全被拒
  （`~/.ssh` 下 4 把 key × `hermes`/`root` 均 `Permission denied`），本机只有 `.minecraft` 客户端、无 Forge 服务端。
  替代证据（Forge 真机逐字真行 + 离线真 CLI：旧模板 FAIL/exit=1 → 新模板 OK/exit=0）见 `docs/acceptance.md` §10.2 B/C，**不当作真机结论**。
- 已完成：PR **#6** —— <https://github.com/YeeNg2333/Y33-Bot/pull/6>，标题
  `feat(observability): 日志零事件看门狗 + check 模板自检`，正文首行 `Closes #2`；开 PR 时 CI `test (3.12)` 两条 check-run 均 `success`。
- 进行中：无。
- 阻塞 / 待办：① issue #1 的出厂模板改动仍在独立分支 `wt/t_2a31fd67`（未合 main），本 PR 不含它；
  ② 真机对照需具备 `10.1.1.4` 凭据的会话补跑一次。

---

## 2026-10-29（收口：BUG-005 合并树全量校验 + 数字四处同步 + PR）

- 已完成（卡 `t_1372eacc`）：把四个 BUG-005 卡分支合入本卡工作树（`t_d9445453` @ `89bba1e`、
  `t_1600b504` @ `e371613`、`t_f43e4dc9` @ `6c2da59`、`t_8688cbf6` @ `4396aff`；基线 main `73400e0`，**main 未动、0 冲突**），
  在合并树重跑 CI 同款：**403 passed / 覆盖率 99.39% / ruff 45 文件全过**。
- 已完成：数字同步四处 —— `README.md` §14、`docs/smoke.md` §7（粘贴块例数行 + 下方「覆盖度」段两处）、
  `docs/acceptance.md` §1 总表与 §3 逐文件表（新增 `tests/test_gateway_errors.py` 一行、bucket `237 → 250`），
  并在 acceptance 新开 **§10** 记本轮复验（含逐模块覆盖率与「真机未执行」三项）；本文件「当前基线」表同步。
  四处统一为 **403 / 99.39% / 45 文件**，增量出处写明（`test_gateway.py` 24 → 29、`test_service.py` 17 → 25）。
- 已完成：PR **#4** 已创建（https://github.com/YeeNg2333/Y33-Bot/pull/4，正文首行 `Closes #3`，
  标题 `fix(qq): 网关超时错误可读化 + 启动前探活（不做重试）`）；卡分支 `wt/t_1372eacc` 已 push
  （`d306591`），未改动 main。CI `test (3.12)` 在 `push` 与 `pull_request` 两个事件上均 success。
- 未执行（照实记）：**真机回归**——BUG-005 的平台超时随机、无法主动触发；本机无真 `app_secret` 跑 `run`；
  S5 真机 8 步前置缺失。详见 `docs/acceptance.md` §10.2，`BUGS.md` 的 BUG-005 仍是「已修复（待真机回归）」。
- 阻塞 / 待办：BUG-005 的「待真机回归」仍挂着；`t_739a0487` / `t_500f7787`（日志模板族，BUG-004）
  **不属于本批**，未合入本次 PR，按各自卡流程走。

## 2026-10-29（BUG-005 修复落地：文案可读化 / 去双前缀 / 启动前一次性探活）

- 已完成（文档，卡 `t_8688cbf6`）：`PLAN.md` 新增 **§7.3**（「原状 → 现行为 → 涉及文件」两行：
  X1 启动期一次性探活、X2 网关错误文案可读化 + 去 `start()` 双前缀），并写明「**不做启动期重试/退避**，
  `PLAN.md:85` N7 与 `PLAN.md:498` 口径不变，§5 S5 期望值不改」；`README.md` §13 FAQ 新增第 15 条
  （`run` 一启动 `exit=1` + `'NoneType' …` → 平台接口瞬时超时、**重跑即可、不是配置错**），
  并把 §7「凭据写错」示例里的旧双前缀 `QQ 网关启动失败: QQ 网关启动失败:` 改成单前缀；
  `BUGS.md` BUG-005 状态改「**已修复（待真机回归）**」并追加「修复记录」（三处改动 + 明确「未做重试」，
  原文证据未改写、未删除）。
- 已完成（代码，两条父卡，改动都在各自卡分支、**未合 main**）：`t_d9445453`（`89bba1e`，`qq/gateway.py`
  文案可读化 + 去双前缀）、`t_1600b504`（`e371613`，`Service.run()` 启动前探活一次即退出）；
  测试卡 `t_f43e4dc9`（`6c2da59`，`tests/test_gateway_errors.py` 9 例，已把两卡合入自己的分支）。
  本机实跑：各分支 387 / 388 / 403 passed；**BUG-005 三卡合并树（`wt/t_f43e4dc9` @ `6c2da59`）
  403 passed / 覆盖率 99.39% / ruff 干净（45 文件）**。文档卡只改 `*.md`，`src/` 零改动。
- 进行中：—（收口卡 `t_1372eacc` 已完成：合并本批分支、合并树重跑、数字四处同步、提 PR `Closes #3`，见上一条 2026-10-29 收口条目）。
- 阻塞 / 待办：**真机回归未执行**（平台超时随机、无法主动触发，见 `BUGS.md`「未能复现 / 信息不足清单」第 4 条）；
  合并树重跑 CI 同款与「当前基线」表更新已由收口卡完成（403 passed / 99.39% / 45 文件，见上一条）。

## 2026-10-28（文档整理：开发进度迁出 AGENTS.md）

- 已完成：新建本文件 `docs/progress.md`，把 `AGENTS.md` 的「开发进度」整节（2026-10-13 ~ 2026-10-15 四条，
  逐字保留）迁到这里，并补记 2026-10-18 实机测试矩阵一条（此前因 `AGENTS.md` 受保护而**缺失**的进度）。
- 已完成：`AGENTS.md` 的「开发进度」改为**指针**（只指向本文件 + 写进度的规矩），不再承载时间线与数字；
  同步更新该文件的引言、`仓库结构与职责` 表、`工作规则`（新增「记进度改本文件，不要改 AGENTS.md」）。
- 已完成：`BUGS.md`「根卡复核记录 / 未做的两件事」第 1 条加一行注记，说明 2026-10-18 的进度已在
  `docs/progress.md` 补记（原「请人工补一条 AGENTS.md 条目」的诉求已被本文件的机制取代）。
- 已完成：本机实跑 —— `pytest -q` **381 passed**；`ruff check .` / `ruff format --check .` 全绿（44 文件）。
  本次只改 `*.md`，`src/`、`tests/` 零改动。
- 进行中：无。
- 阻塞 / 待办：无。后续看板卡按下面「已迁移条目」的格式直接往本文件追加即可（**不要再改 `AGENTS.md`**）。

## 2026-10-18（实机测试矩阵：原版 / Fabric / Forge / NeoForge）

- 已完成：根卡 `t_d25d5a1d` 汇总六张实机测试卡，分支全部合入 main（`c5e617c`，6 个 merge、0 冲突）：
  - 环境基座 `t_a4c6c3ae` → `test-notes/00-env.md`（测试机 `hermes@10.1.1.4`，Rocky 9.7、2 vCPU / 2.6 GiB，
    Temurin JDK21（默认）+ JDK25，Python 3.12.8，源码 `f7fd5cb`，端口分配表见该文 §5.2）
  - 原版 `t_ac457fe1` → `test-notes/01-vanilla.md`（**15 个正式版 × 17 条用例 = 255 条，0 失败**；1.21.2–26.3）
  - Fabric `t_5bccfcd8` → `test-notes/02-fabric.md`（9 个版本 + loader 0.20.0 变体；1.21.2–26.3）
  - Forge `t_157ba7fe` → `test-notes/03-forge.md`（12 个版本 + D1–D4 补充观察；1.21.3–26.3）
  - NeoForge `t_efe57773` → `test-notes/04-neoforge.md`（9 个版本，T0–T9；1.21.3–26.3）
  - 汇总 `t_1c0e88a4` → 新增 `BUGS.md`（汇总表 + 逐条根因 + 测试矩阵与证据来源 + 未复现清单）
- 已完成：`BUGS.md` 新增四条实机缺陷，**全部「已复现，未修」**（汇总卡只做根因分析，不改代码）：
  - **BUG-002**（高）默认 `chat` 模板只认 ≤1.21.1 的 `[Async Chat Thread - #N/INFO]` 形态，
    1.21.2+ 的真实行 `[Not Secure] <Steve> #…` 一律不匹配 → 游戏内 `#` 聊天不进群；
    实证原版 15/15、Fabric 7/7，窗口内**无版本边界**（变更点 ≤ 1.21.1）。
  - **BUG-003**（高）Forge / NeoForge 自带的 log4j2 布局让 `join`/`quit`/`chat` **三个模板全不匹配**
    → MC→QQ 方向全哑；**加载器级、非版本级**（Forge 12/12、NeoForge 9/9）。
  - **BUG-004**（中）日志行 100% 未匹配时只有 DEBUG 级 `[忽略]`，没有「零事件」看门狗；
    是否按缺陷处理**待用户拍板口径**。
  - **BUG-005**（中）QQ 网关遇平台接口超时时 SDK 把超时吞成 `None` → 报错不可读（`'NoneType' …`）且
    **不重试**直接非 0 退出；触发随机（实测 Forge 5 次、NeoForge 3 次、原版 1 次）。
- 已完成：**BUG-001 复验**（R2-lite 契约在真机生效）—— 四张卡在真机上共触发 9 次「网关启动期失败 /
  网关任务结束」，每次都出现 `[错误]` + 非 0 退出，不再静默常驻；原始输出见 BUG-005「症状」。
- 已完成：根卡独立复核 —— 用本仓 `patterns.py` 离线复现 BUG-002/003，逐条抽查 `文件:行号`
  （`patterns.py:52-60/96`、`watcher.py:112-115`、`bridge.py:139/165-167`、`service.py:284-289`、
  `cli.py:221-225`、`config.example.toml:31-33`、`tests/conftest.py:19-21`），合并树上重跑
  **381 passed**、`ruff check .` + `ruff format --check .` 全绿（**44 文件**）。
- 已完成：数字与制品校正 —— 制品数量由卡面估算「771」改为树里实测 **761**（`00-env` 4、`vanilla` 107、
  `fabric` 162、`forge` 296、`neoforge` 192）；修 `test-notes/artifacts/neoforge/scripts/nf_patch_installer.py`
  的 lint（未用的 `import json` + 一处换行），`make lint` 回到全绿（这是本批唯一改动的非新增文件）。
- 已完成：零产品改动核验 —— `git diff f7fd5cb..HEAD -- src tests docs README.md PLAN.md IDEA.md config.example.toml`
  为**空**；五份 `test-notes/*.md` 是各卡分支同名文件的逐字副本（sha256 见 `test-notes/README.md`）。
- 进行中：无。
- 阻塞 / 待办：**BUG-002/003 的修复卡（只改 `[log_patterns]`，不用动代码）未开**；BUG-004 是否按缺陷处理待拍板；
  BUG-005 的重试/退避口径未定；`PLAN.md` §7 未登记（按「零产品改动」口径留给修复卡）。
  本条此前因 `AGENTS.md` 受保护、写不进去而**缺失**，2026-10-28 随进度迁出补记（见上一条）。

## 2026-10-15（BUG-001 修复：R2-lite + R5）

- 已完成：按 `BUGS.md` BUG-001「回复」的推荐（**R2 + R5**）与用户拍板口径「网关任务结束即视为故障：
  打 `[错误]` 并立即非 0 退出，交给 `systemd`/`nssm` 拉起，**不做退避重启**」完成修复（卡 `t_80249809`）：
  - **R2-lite**：`QQGateway` 协议新增 `wait_closed()`（`BotpyGateway` 用 done-callback 观测自己的网关任务，
    `FakeQQGateway` 等到 `close()`）；`Service.run()` 同时等「停止信号」与「网关任务结束」——
    网关先结束 → `[错误] QQ 网关已断开（收不到群消息），进程退出等待重启` + 走 `shutdown()` + 返回 **1**；
    收到停止信号 → 仍 **0**、不打 `[错误]`。改动文件：`src/y33bot/service.py`、`qq/gateway.py`、`qq/fakes.py`。
  - **R5**：新增 `src/y33bot/qq/probe.py`（`urllib` POST `getAppAccessToken`，超时 5s，可注入可 monkeypatch）；
    `check` 的 QQ 项默认**真探活**（成功 `[QQ] OK access_token 获取成功（有效期 Ns），…`；
    失败 `[QQ] FAIL access_token 获取失败: <原因>`），新增 `check --no-probe` 给离线/CI 用（文案写明「未探活」）。
- 已完成：登记与文档同步 —— `PLAN.md` §7.2 新增变更记录并同步 §3.1/§3.2/§3.3/§3.4/§3.6/§5 S1/S5；
  `README.md` §7/§8/§13（新增 FAQ14）/§14；`docs/smoke.md` §1/§6/§7；`docs/acceptance.md` 新增 §9 复验
  （§7/§8 历史粘贴与 348/352/357 未改写，只加标注；§1 总表已更新为 381）；`BUGS.md` BUG-001 改为**已修复** + 「修复记录」。
- 已完成：本机实跑 —— `pytest -q` **381 passed**（357 → +24）、覆盖率 **99.33%**、
  `ruff check .` / `ruff format --check .` 全绿（43 文件），`tests/` 无 skip/xfail。
- 已完成：真机能测的都测了（`docs/acceptance.md` §9）—— 离线前后对照：修复前网关结束后 `run()` 3s 内不返回、
  0 条 `[错误]`；修复后 `[错误] QQ 网关已断开…` + `exit=1`。`check` 真网络实测（假凭据）：
  修复前 `[QQ] OK app_id 已设置 …` → 修复后 `[QQ] FAIL access_token 获取失败: 平台返回错误: code=10004 message=机器人不存在`。
- 阻塞 / 待办：真机触发链路（Q1/Q3）与 `BUGS.md` 真机三步、S5 真机 8 步**仍未执行**（无真实 QQ 凭据/真 MC 服）；
  本次刻意不做退避重启与 SDK 重连驱动（R1/R3）；`check` 默认真探活意味着**离线环境请用 `--no-probe`**（CI 不跑 `check`，不受影响）。

## 2026-10-15（BUG-001 调查：QQ 网关静默失效）

- 已完成：登记并调查 **BUG-001**（用户真机观察：QQ 凭据/token 过期后群里无反应、进程还活着、日志没提示）。
  载体是仓库新增的 **`BUGS.md`**（含记录规则 / 索引 / 逐条模板 / 结论落在「回复」小节）：
  - 假设 H1 已由调查卡 `t_6cc56405` **离线复现并升级为结论：真缺陷**。链条：
    `ret_coro=True`（`PLAN.md:145` 的既有装配决定）让 SDK 自带的重连驱动
    `while not self._closed: multi_run(...)`（`botpy/client.py:217-223`）**不执行** → 会话被
    `on_closed` 回填后无人启动（`botpy/connection.py:57-67`）→ 网关协程**正常返回**（无异常 ⇒ 无日志，
    `src/y33bot/qq/gateway.py:132-138`）→ `Service.run()` 只等停止信号（`src/y33bot/service.py:215`）
    → 进程常驻、群里永久无反应、日志干净。
  - 5 个取证用例（`tests/test_bug001_reconnect.py` 新增 2 例 + `test_gateway.py` 2 例 + `test_service.py` 1 例）钉死上述行为；
    另实测 `check` 的 `[QQ] OK` 在**凭据完全无效时照样通过**（RCON 项真连 `/list`、QQ 项只查变量非空）。
  - **未执行**：真机触发链路（Q1 静默时的日志尾部、Q3 QQ 侧关码）——本机无真实 QQ 凭据与真 MC 服，
    已在 `BUGS.md` 如实标注，未编造替代输出。
- 已完成：卡分支 `y33-bot/t_6cc56405-bug-001-qq-token`（`ecf71b2`）合入 main（merge `e5b0782`）；
  复核确认 `src/` 一行未改。合并后 CI 同款实跑：**357 passed、覆盖率 99.30%、ruff 41 文件合规**。
- 已完成：用例数变化的文档同步 —— `README.md` §14、`docs/smoke.md` §7、`docs/acceptance.md` §1/§3
  与新增 §8.6（352 → 357，历史记录按原样保留并标注）。
- 已完成：口径已由用户拍板 —— **网关任务结束即视为故障：打 `[错误]` 并立即以非 0 退出**，交给
  `systemd`/`nssm` 拉起（不做退避重启）；另建议把 `check` 的 QQ 项改为真实探活。
- 进行中：修复要**另开卡**（R2-lite + R5），并走 `PLAN.md` §7 的变更登记；落地后先真机复现一次再验修复。
- 阻塞 / 待办：BUG-001 的真机触发链路（Q1/Q3）仍未验证；S5 真机 8 步仍未执行。

## 2026-10-13（v0.2：真机试跑反馈三条）

- 已完成：按 `需求1.txt` 第 53–55 行的三条真机反馈改造，并在 `PLAN.md` §7 登记为 **V1–V3**（含对
  IDEA §3.3/§3.8 的偏离说明；`IDEA.md`、`需求1.txt` 按规则未改动）。
  - **V1** MC→QQ 文案带来源服名（`[[mc_servers]].name`，不加 `【】`）：进出 `Steve进入了main` /
    `Steve退出了main`，游戏内 `#` 转发 `Steve@main: 你好`。
  - **V2** 取消游戏内 `[→QQ]` 回显：`#` 聊天只在群里出现一行，游戏内不再被注入（玩家自己那行已可见）；
    `ignored_chat_prefixes` 样板随之收窄为 `["[QQ]"]`。
  - **V3** 新增 `y33bot commands` 子命令，打印 QQ 管理端「指令配置」要填的「指令名 + 指令介绍」；
    `README.md` 新增 §5.3 记录平台事实（**管理端手工配置、无注册 API**，指令名 ≤8 中文字符/16 英文字符、
    介绍 ≤15/30、上限 24 条、无需单独提审）。`/list`（群内列举指令）明确**不做**。
- 已完成：本次实跑 —— `pytest -q` **352 passed**；`pytest -q --cov=y33bot --cov-fail-under=70`
  通过、总覆盖 **99.30%**；`ruff check .` 全过、`ruff format --check .` 40 文件合规；`tests/` 无 skip/xfail。
- 已完成：文档同步 —— `PLAN.md`（A4/A8/N13/R10/R11/R28、§3.4 CLI 契约加 `commands`、§3.5/§4.1 配置默认值、
  S3–S6 期望值、新增 §7 变更记录）、`README.md`（§2 功能表、§5.1/§5.3、§6 示例、§8 速查、§13 FAQ13、§14 实测数字）、
  `docs/smoke.md`（S2/S3/S4/S5/S6 片段、例数与覆盖度）、`docs/acceptance.md`（§0/§1、§2.3/§2.4 重跑更新、
  §7 标注为「变更前记录」、新增 §8 v0.2 复验）。
- 已完成：依赖装在仓库 `.venv`（不入库，靠 `requirements*.txt` 复现；pypi 直连超时，本次改用清华镜像
  安装，依赖版本声明未改）。
- 进行中：无。
- 阻塞 / 待办：**S5 真机 8 步仍未执行**（本机无真实 QQ 凭据、无 `enable-rcon=true` 的真 MC 服），
  结论维持「部分通过」（`docs/acceptance.md` §8.5）。待办：上线前按 `docs/smoke.md` 在真机跑一遍手工自测。
- 待办：`IDEA.md` §5「后期规划（不预留，仅记录）」4 项未实施（投票重启、插件式通信、热重载、自定义触发字符）——
  属明确不做，不要顺手扩大范围。

## 2026-10-13

- 已完成：PLAN.md §6 的 T1–T12 全部落地（骨架与依赖、配置与模型、持久化、RCON、日志、指令、
  业务桥与 QQ 适配、服务与 CLI、单元测试、端到端验收、README 与发布、T12 汇总复验）。
- 已完成：看板上 6 张前置卡（`t_8442a7d5`/`t_68925b93`/`t_7b86eb6b`/`t_bcf892eb`/`t_19583dfd`/
  `t_c3a76c90`）均为 done，本卡 `t_3367baf6` 是最后一张。
- 已完成：本次在 `f38b233` 上实跑 `pytest -q --cov=y33bot --cov-fail-under=70` ——
  **348 passed、总覆盖率 99.30%**（门槛 70%），`ruff check .` 全过、`ruff format --check .` 40 文件合规，
  `tests/` 无 skip/xfail。
- 已完成：验收场景 S1（环境与配置自检）、S2（QQ→MC 绑定与转发）、S3（MC→QQ 转发与回环防护）、
  S4（进出通知与健康翻转）、S6（日志轮转）**通过**；逐条证据见 `docs/acceptance.md`。
- 已完成：`v0.1.0` 已打 annotated tag（指向 `f0ddd4e`）；`README.md`、`docs/smoke.md`、
  `docs/acceptance.md` 齐备，文档里的命令与输出都是实测粘贴。
- 已完成：`origin/main` HEAD 已推进到 `f38b233`；据 `docs/acceptance.md` §7.9，`3c27803` 及其后续
  文档提交的 CI 均为 success（本地无 `gh`，CI 结论以该记录为准，本次未独立复核）。
- 已完成：把上述进度写入仓库根目录 `AGENTS.md`（当时进度还记在 `AGENTS.md`；2026-10-28 起迁到本文件），
  提交为 `docs: update development progress in AGENTS.md`。
- 阻塞 / 待办：**S5 真实端到端（真 QQ 群 + 真 MC 服）的 8 步未执行、不作通过声明** ——
  本机没有真实 QQ 机器人凭据，也没有 `enable-rcon=true` 的真 MC 服；步骤与判据留在 `PLAN.md` §5，
  具备环境后回填 `docs/acceptance.md` §2.5。
- 待办：上线前按 `docs/smoke.md` 在真机跑一遍手工自测（含常驻运行 S5 的离线可复现部分）。
- 待办：`IDEA.md` §5「后期规划（不预留，仅记录）」4 项未实施：投票重启服务器、插件式通信、
  热重载配置、自定义触发字符 —— 属于明确不做，不要顺手扩大范围。
