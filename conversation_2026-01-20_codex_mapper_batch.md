# 对话记录：batch mapper 方案设计（Codex）
**日期**：2026-01-18
**参与者**：Meiqi + Codex (GPT-5)
**主题**：mapper.py 批量处理优化方案与实现（mapper2_from_codex.py）

---

## 需求背景
- 项目是“双语 Word 文档 Track Changes 同步引擎”，V2 方案中 mapper 负责将 source_before/source_after 的语义变化映射到 target_current。
- 现有 mapper 是逐行调用 API，速度慢、成本高。
- 目标：在保持稳定性的前提下最大化速度，并尽量减少资源浪费。

---

## 用户明确的前提条件（MVP 约束）
1. 双语文档为两列表格，源语言列/目标语言列各占一列。
2. 同一语义的源/目标文本严格对应同一行左右单元格。
3. source_before 与 target_current 在语义上严格一致（不存在空或不对应）。

这些前提影响预处理与容错策略（避免过度过滤）。

---

## 关键问题与共识
### 1) 为什么不能“强制输出到 max_tokens”？
- max_tokens 是“上限”，模型会在认为完成时提前停止（stop_reason = end_turn）。
- 无法强制模型“跑满”上限，否则会增加无意义输出与格式错误风险。
- 速度来自“减少 API 次数 + 输出刚好够用”，不是输出越长越快。

### 2) 预处理应更轻量
- 用户不接受“source_before/source_after 为空就跳过”。空行也可能是有效修订。
- 不强制“超长行单独处理”，而是用动态批次预算让长行占更多输出预算。

### 3) 正则抽取（salvage parsing）解释
- 如果模型输出被截断或 JSON 格式错误，整体解析会失败。
- “正则抽取”是从混乱文本中尽量捞出完整对象，保留成功项，失败行再重试。

---

## 设计理念（最终方案）
核心目标：**速度优先 + 精准重试 + JSON 直输入**

1) **动态批次（按输出预算）**
- 不是固定 10 行/20 行，而是估算每行输出 token 成本。
- 批次累积到“输出预算上限”就切分，避免输出截断。

2) **JSON 输入/输出**
- 直接使用 extractor 输出的 JSON，不做编号列表转化。
- 输出要求严格 JSON 数组，仅包含 row_index/target_after/confidence。

3) **容错解析 + 精准重试**
- 先尝试完整 JSON 解析。
- 失败则 salvage（正则抽取单条对象）。
- 仅重试失败行，不重试成功行。

4) **截断保护**
- 如果 stop_reason == "max_tokens"，默认最后一行不完整，丢弃并重试。

---

## 已落地实现（新文件）
**新增文件**：`src/mapper2_from_codex.py`

### 文件结构
- 顶部包含：架构图 + 设计说明
- `BatchRevisionMapper`：
  - `map_rows()`：主入口，批量映射 + 重试
  - `_build_batches()`：按输出预算切分批次
  - `_estimate_row_output_tokens()`：输出成本估算
  - `_map_batch()`：单批次调用 LLM
  - `_parse_batch_response()`：完整解析 + salvage

### 关键实现点
- **失败行检测**：
  - 用 “batch_ids - parsed_ids” 得到失败行
  - 只对这些行进入 retry
- **输出预算收缩**：
  - 每次重试降低输出预算（retry_shrink_ratio），降低截断风险

---

## 与 Claude 方案的差异
- Claude 方案倾向固定批次 + 整批降级重试。
- 本方案以“输出预算”为核心，动态批次，失败行精准重试。
- 更符合“速度优先 + 资源最省”的原则。

---

## 后续可讨论问题
1. 是否将 `mapper2_from_codex.py` 接入 `engine.py`，替换或并行于现有 mapper。
2. 是否需要更强 JSON 输出约束（例如 function call / tool output）。
3. 是否要将输出预算估算策略参数化（row_base_tokens/row_per_char）。

---

## 本次对话的结论
- 已确认采用“动态批次 + 精准重试 + JSON 直输入”的 mapper 设计。
- 已创建 `src/mapper2_from_codex.py` 作为实现落地版本。
