"""
================================================================================
LLM 映射器 - 使用大语言模型将修订映射到目标语言
================================================================================

模块定位
--------
这是三模块管道中唯一调用外部 API 的模块：

    extractor.py ──→ mapper.py ──→ applier.py
    (提取修订)       (LLM映射)      (应用修订)
                        ↓
                   Anthropic API

核心职责
--------
1. 理解源语言修订前后的语义差异
2. 在目标语言中做最小改动以反映相同的语义变化
3. 返回目标语言的修订后完整文本

数据流
------
输入（来自 extractor）:
    {
        'source_before': '修订前的源语言文本',
        'source_after': '修订后的源语言文本',
        'target_current': '目标语言当前文本'
    }

输出（给 applier）:
    {
        'target_after': 'LLM 生成的目标语言修订后文本',
        'explanation': 'LLM 的解释',
        'confidence': 0.95
    }

设计原则
--------
- 语义驱动：翻译是语义对应，不是词汇对应
- 最小改动：只改必须改的部分
- 确定性输出：temperature=0.0 保证相同输入得到相同输出

性能优化：Prompt Caching
------------------------
使用 Anthropic Prompt Caching 功能优化 API 调用效率：

    优化前：每行都发送完整 prompt（~600 tokens）
    ┌─────────────────────────────────────────────┐
    │ [角色+背景+原则+格式] + [数据]  → API 调用 1 │
    │ [角色+背景+原则+格式] + [数据]  → API 调用 2 │
    │ ...重复发送相同的固定内容...                │
    └─────────────────────────────────────────────┘

    优化后：固定部分缓存，只发送变化数据
    ┌─────────────────────────────────────────────┐
    │ [system prompt 创建缓存] + [数据] → 调用 1  │
    │ [读取缓存(0.1x成本)] + [数据]     → 调用 2  │
    │ ...后续调用节省约 60% 成本...               │
    └─────────────────────────────────────────────┘

关键实现：
- system 参数：固定内容（角色、原则、示例），带 cache_control 标记
- messages 参数：变化内容（每行的 before/after/current）
- 缓存有效期：5 分钟（Anthropic 默认）
================================================================================
"""

import anthropic
from typing import Dict, List
import json


class RevisionMapper:
    """
    使用 LLM 将修订从源语言映射到目标语言

    结构图
    ------
    RevisionMapper
    ├── __init__(api_key, model)           # 初始化客户端 + 缓存变量
    │
    ├── map_row_pairs()                    # 主入口：处理 extractor 输出的行对
    ├── map_text_revision()                # 单行映射：调用 LLM API（使用缓存）
    │
    ├── _parse_text_response()             # 解析 JSON 响应
    │
    └── Prompt Caching 相关
        ├── _build_system_prompt()         # 构建可缓存的系统提示（固定部分）
        └── _build_user_message()          # 构建用户消息（变化部分）
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        初始化映射器

        Args:
            api_key: Anthropic API 密钥（从环境变量 ANTHROPIC_API_KEY 获取）
            model: 使用的模型，默认 claude-sonnet-4-20250514
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Prompt Caching：缓存当前文档的 system prompt
        # 同一文档内 source_lang/target_lang 固定，可以复用
        self._cached_system_prompt = None
        self._cached_source_lang = None
        self._cached_target_lang = None

    def map_text_revision(
        self,
        source_before: str,
        source_after: str,
        target_current: str,
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> Dict:
        """
        将源语言的文本修订映射到目标语言（使用 Prompt Caching）

        Args:
            source_before: 源语言修订前的完整文本
            source_after: 源语言修订后的完整文本
            target_current: 目标语言的当前文本
            source_lang: 源语言名称
            target_lang: 目标语言名称

        Returns:
            {
                'target_after': 目标语言修订后应该是什么,
                'explanation': LLM 的解释,
                'confidence': 置信度 (0-1)
            }

        优化说明:
            - system 参数包含固定内容，带 cache_control 标记
            - messages 参数只包含每行变化的数据
            - 首次调用创建缓存，后续调用读取缓存，节省约 60% 成本
        """
        # 检查是否需要更新缓存的 system prompt
        # 当语言对变化时，需要重新构建
        if (self._cached_system_prompt is None or
            self._cached_source_lang != source_lang or
            self._cached_target_lang != target_lang):
            self._cached_system_prompt = self._build_system_prompt(source_lang, target_lang)
            self._cached_source_lang = source_lang
            self._cached_target_lang = target_lang

        # 构建变化的用户消息
        user_message = self._build_user_message(
            source_before, source_after, target_current, source_lang, target_lang
        )

        # 使用 Prompt Caching 调用 API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.0,  # 确定性输出
            system=self._cached_system_prompt,  # 固定部分，带缓存标记
            messages=[{"role": "user", "content": user_message}]  # 变化部分
        )

        result = self._parse_text_response(response.content[0].text)
        return result

    def map_row_pairs(
        self,
        row_pairs: List[Dict],
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> List[Dict]:
        """
        主入口：处理 extractor 输出的行对列表

        Args:
            row_pairs: extractor.extract_row_pairs() 的输出
                       每项含 {row_index, source_before, source_after, target_current}
            source_lang: 源语言名称
            target_lang: 目标语言名称

        Returns:
            映射结果列表，每项含：
            {
                'row_index': 行号,
                'target_current': 目标语言当前文本,
                'target_after': 目标语言修订后文本,
                'explanation': LLM 的解释,
                'confidence': 置信度
            }
        """
        results = []

        for pair in row_pairs:
            row_idx = pair['row_index']

            mapped = self.map_text_revision(
                source_before=pair['source_before'],
                source_after=pair['source_after'],
                target_current=pair['target_current'],
                source_lang=source_lang,
                target_lang=target_lang
            )

            mapped['row_index'] = row_idx
            mapped['target_current'] = pair['target_current']
            results.append(mapped)

        return results

    def _parse_text_response(self, response_text: str) -> Dict:
        """解析 LLM 的 JSON 响应"""
        try:
            # 提取 JSON 代码块
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            else:
                json_str = response_text.strip()

            result = json.loads(json_str)

            # 验证必要字段
            if 'target_after' not in result:
                raise ValueError("响应缺少 target_after 字段")

            # 设置默认值
            if 'confidence' not in result:
                result['confidence'] = 0.8
            if 'explanation' not in result:
                result['explanation'] = ''

            return result

        except Exception as e:
            print(f"解析响应失败: {e}")
            print(f"原始响应: {response_text}")

            return {
                'target_after': '',
                'confidence': 0.0,
                'explanation': '',
                'error': str(e)
            }

    def _build_system_prompt(self, source_lang: str, target_lang: str) -> list:
        """
        构建可缓存的系统提示（固定部分）

        使用 Anthropic Prompt Caching 功能：
        - 将不变的内容（角色、背景、原则、格式、示例）放入 system prompt
        - 添加 cache_control 标记，让 API 缓存这部分内容
        - 后续调用只需发送变化的数据，节省约 60% 成本

        Args:
            source_lang: 源语言名称（如"中文"）
            target_lang: 目标语言名称（如"英文"）

        Returns:
            符合 Anthropic API system 参数格式的列表
        """
        system_text = f"""你是一个专业的双语法律文档翻译专家。

## 任务背景

一份双语文档中，{source_lang}版本进行了修订。你需要将这些修订同步到{target_lang}版本。

## 你的任务

1. 理解{source_lang}从"修订前"到"修订后"发生了什么**语义变化**
2. 在{target_lang}当前文本的基础上，做**最小的改动**来反映相同的语义变化
3. 返回{target_lang}修订后的**完整文本**

## 重要原则

- **语义对应**：翻译是语义对应，不是词汇对应。例如中文删除"正在"，英文可能需要改变时态而非删除某个词
- **最小改动**：只改必须改的部分，保持其他内容不变
- **语法正确**：确保修订后的{target_lang}文本语法正确、表达自然

## 输出格式

请以 JSON 格式返回：
```json
{{
  "target_after": "修订后的{target_lang}完整文本",
  "explanation": "简要说明你理解的语义变化，以及你在{target_lang}中做了什么改动",
  "confidence": 0.95
}}
```

## 参考示例

### 示例 1：时态变化
- {source_lang}修订前："AI正在改变我们的生活"
- {source_lang}修订后："AI改变了我们的生活"
- {target_lang}当前："AI is changing our life"
- {target_lang}修订后："AI has changed our life"
- 解释：从进行时变为完成时，英文相应调整时态

### 示例 2：数量修改
- {source_lang}修订前："协议有效期为一年"
- {source_lang}修订后："协议有效期为两年"
- {target_lang}当前："The agreement is valid for one year"
- {target_lang}修订后："The agreement is valid for two years"
- 解释：只修改数量词，保持其他部分不变

### 示例 3：法律用语调整
- {source_lang}修订前："甲方应当支付"
- {source_lang}修订后："甲方须支付"
- {target_lang}当前："Party A should pay"
- {target_lang}修订后："Party A shall pay"
- 解释：语气从"应当"变为"须"，英文用 shall 表达强制性"""

        return [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"}  # 标记为可缓存
            }
        ]

    def _build_user_message(
        self,
        source_before: str,
        source_after: str,
        target_current: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """
        构建每行变化的用户消息（不缓存）

        只包含每行修订的具体数据，配合缓存的 system prompt 使用。

        Args:
            source_before: 源语言修订前的文本
            source_after: 源语言修订后的文本
            target_current: 目标语言当前文本
            source_lang: 源语言名称
            target_lang: 目标语言名称

        Returns:
            用户消息字符串
        """
        return f"""## {source_lang}的变化

**修订前：**
{source_before}

**修订后：**
{source_after}

## {target_lang}当前文本

{target_current}

请分析语义变化并返回{target_lang}修订后的完整文本。"""

# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    import os

    # 从环境变量获取 API 密钥
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("请设置 ANTHROPIC_API_KEY 环境变量")
        print("Windows: set ANTHROPIC_API_KEY=your-key-here")
        print("Linux/Mac: export ANTHROPIC_API_KEY='your-key-here'")
        exit(1)

    mapper = RevisionMapper(api_key)

    # ========== 示例 1：单行映射 ==========
    print("=" * 60)
    print("示例 1：单行映射 (map_text_revision)")
    print("=" * 60)

    source_before = "AI正在改变我们的生活。"
    source_after = "AI改变了我们的生活。"
    target_current = "AI is changing our life."

    print(f"\n输入:")
    print(f"  源语言修订前: {source_before}")
    print(f"  源语言修订后: {source_after}")
    print(f"  目标语言当前: {target_current}")

    result = mapper.map_text_revision(
        source_before=source_before,
        source_after=source_after,
        target_current=target_current,
        source_lang="中文",
        target_lang="英文"
    )

    print(f"\n输出:")
    print(f"  目标语言修订后: {result['target_after']}")
    print(f"  置信度: {result['confidence']}")
    print(f"  说明: {result.get('explanation', '')}")

    # ========== 示例 2：批量映射（模拟 extractor 输出）==========
    print("\n" + "=" * 60)
    print("示例 2：批量映射 (map_row_pairs)")
    print("=" * 60)

    # 模拟 extractor.extract_row_pairs() 的输出
    row_pairs = [
        {
            'row_index': 0,
            'source_before': '本协议由甲方和乙方签订。',
            'source_after': '本协议由甲方与乙方签订。',
            'target_current': 'This agreement is signed by Party A and Party B.'
        },
        {
            'row_index': 1,
            'source_before': '协议有效期为一年。',
            'source_after': '协议有效期为两年。',
            'target_current': 'The agreement is valid for one year.'
        }
    ]

    print(f"\n输入: {len(row_pairs)} 行修订")

    results = mapper.map_row_pairs(row_pairs, source_lang="中文", target_lang="英文")

    print(f"\n输出:")
    for r in results:
        print(f"\n  行 {r['row_index']}:")
        print(f"    当前: {r['target_current']}")
        print(f"    修订后: {r['target_after']}")
        print(f"    置信度: {r['confidence']}")
