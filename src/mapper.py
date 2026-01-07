"""
LLM映射器 - 使用大语言模型将修订映射到目标语言

核心功能：
1. 理解源语言修订前后的语义差异
2. 在目标语言中做最小改动以反映相同的语义变化
3. 返回目标语言的修订后完整文本

V2 重塑说明：
- 不再传递 deletion/insertion 碎片
- 传递源语言的 before_text 和 after_text
- 让 LLM 理解语义差异，而非词汇对应
"""

import anthropic
from typing import Dict, List
import json


class RevisionMapper:
    """使用LLM将修订从源语言映射到目标语言"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        初始化映射器

        Args:
            api_key: Anthropic API密钥
            model: 使用的模型
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    # ========== V2 新方法 ==========

    def map_text_revision(
        self,
        source_before: str,
        source_after: str,
        target_current: str,
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> Dict:
        """
        将源语言的文本修订映射到目标语言（V2 新方法）

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
        """
        prompt = self._build_text_mapping_prompt(
            source_before, source_after, target_current, source_lang, target_lang
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.0,  # 确定性输出
            messages=[{"role": "user", "content": prompt}]
        )

        result = self._parse_text_response(response.content[0].text)
        return result

    def map_text_revisions_batch(
        self,
        source_items: List[Dict],
        target_items: List[Dict],
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> List[Dict]:
        """
        批量映射多行文本修订（V2 新方法）

        Args:
            source_items: 源语言列表，每项含 {row_index, before_text, after_text, has_revisions}
            target_items: 目标语言列表，每项含 {row_index, current_text}
            source_lang: 源语言名称
            target_lang: 目标语言名称

        Returns:
            映射结果列表
        """
        results = []

        # 按 row_index 配对
        target_by_row = {item['row_index']: item for item in target_items}

        for source in source_items:
            if not source.get('has_revisions', False):
                # 没有修订的行跳过
                continue

            row_idx = source['row_index']
            target = target_by_row.get(row_idx)

            if not target:
                print(f"警告: 行 {row_idx} 在目标语言列中未找到对应文本")
                continue

            mapped = self.map_text_revision(
                source_before=source['before_text'],
                source_after=source['after_text'],
                target_current=target['current_text'],
                source_lang=source_lang,
                target_lang=target_lang
            )

            mapped['row_index'] = row_idx
            mapped['target_current'] = target['current_text']
            results.append(mapped)

        return results

    def _build_text_mapping_prompt(
        self,
        source_before: str,
        source_after: str,
        target_current: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """构建 V2 新 prompt"""

        prompt = f"""你是一个专业的双语法律文档翻译专家。

## 任务背景

一份双语文档中，{source_lang}版本进行了修订。现在需要将这个修订同步到{target_lang}版本。

## {source_lang}的变化

**修订前：**
{source_before}

**修订后：**
{source_after}

## {target_lang}当前文本

{target_current}

## 你的任务

1. 首先理解{source_lang}从"修订前"到"修订后"发生了什么**语义变化**
2. 然后在{target_lang}当前文本的基础上，做**最小的改动**来反映相同的语义变化
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
"""
        return prompt

    def _parse_text_response(self, response_text: str) -> Dict:
        """解析 V2 响应"""
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

    # ========== V1 旧方法（保留以便对比） ==========

    def map_revision(
        self,
        source_revision: Dict,
        target_text: str,
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> Dict:
        """
        将单个修订映射到目标语言（V1 旧方法）

        Args:
            source_revision: 源语言的修订信息
            target_text: 目标语言的完整文本
            source_lang: 源语言名称
            target_lang: 目标语言名称

        Returns:
            包含目标语言修订的字典：
            {
                'deletion': 要删除的目标语言文本,
                'insertion': 要插入的目标语言文本,
                'confidence': 置信度 (0-1)
            }
        """
        prompt = self._build_mapping_prompt(
            source_revision, target_text, source_lang, target_lang
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        # 解析响应
        result = self._parse_response(response.content[0].text)

        return result

    def map_revisions_batch(
        self,
        source_revisions: List[Dict],
        target_texts: List[str],
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> List[Dict]:
        """
        批量映射多个修订（V1 旧方法）

        Args:
            source_revisions: 源语言修订列表
            target_texts: 对应的目标语言文本列表
            source_lang: 源语言名称
            target_lang: 目标语言名称

        Returns:
            目标语言修订列表
        """
        results = []

        for revision, target_text in zip(source_revisions, target_texts):
            mapped = self.map_revision(
                revision, target_text, source_lang, target_lang
            )
            results.append(mapped)

        return results

    def _build_mapping_prompt(
        self,
        source_revision: Dict,
        target_text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """构建发送给LLM的提示（V1 旧方法）"""

        prompt = f"""你是一个专业的双语法律文档翻译专家。现在需要将{source_lang}文档中的一个track change（修订）同步应用到对应的{target_lang}翻译文本中。

**{source_lang}的修订信息：**
- 删除的文本: "{source_revision['deletion']}"
- 插入的文本: "{source_revision['insertion']}"
- 修订前的上下文: "{source_revision['context_before']}"
- 修订后的上下文: "{source_revision['context_after']}"

**{target_lang}的当前完整文本：**
"{target_text}"

**任务：**
请在{target_lang}文本中找到对应的部分，并提供应该进行的修订。

**要求：**
1. 保持翻译的准确性和专业性
2. 修订应该与{source_lang}的修订在语义上完全对应
3. 只标记实际改变的部分，不要包含不变的文本
4. 确保修订后的文本仍然符合{target_lang}的语法和表达习惯

**请以JSON格式返回结果：**
```json
{{
  "deletion": "要删除的{target_lang}文本",
  "insertion": "要插入的{target_lang}文本",
  "explanation": "简要说明这个映射的理由",
  "confidence": 0.95
}}
```

注意：
- deletion是{target_lang}中要删除的部分
- insertion是{target_lang}中要插入的新文本
- confidence是你对这个映射的置信度（0-1之间）
"""

        return prompt

    def _parse_response(self, response_text: str) -> Dict:
        """解析LLM的响应"""
        try:
            # 提取JSON代码块
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_str = response_text[start:end].strip()
            else:
                json_str = response_text.strip()
            
            result = json.loads(json_str)
            
            # 验证必要字段
            if 'deletion' not in result or 'insertion' not in result:
                raise ValueError("响应缺少必要字段")
            
            # 设置默认置信度
            if 'confidence' not in result:
                result['confidence'] = 0.8
            
            return result
            
        except Exception as e:
            print(f"解析响应失败: {e}")
            print(f"原始响应: {response_text}")
            
            # 返回一个默认值
            return {
                'deletion': '',
                'insertion': '',
                'confidence': 0.0,
                'error': str(e)
            }


# 使用示例
if __name__ == "__main__":
    import os

    # 从环境变量获取API密钥
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("请设置ANTHROPIC_API_KEY环境变量")
        exit(1)

    mapper = RevisionMapper(api_key)

    print("=" * 50)
    print("V2 新方法：基于语义差异的映射")
    print("=" * 50)

    # V2 示例：传递完整的修订前后文本
    source_before = "AI正在改变我们的生活。"
    source_after = "AI改变了我们的生活。"
    target_current = "AI is changing our life."

    result = mapper.map_text_revision(
        source_before=source_before,
        source_after=source_after,
        target_current=target_current,
        source_lang="中文",
        target_lang="英文"
    )

    print(f"\n源语言修订前: {source_before}")
    print(f"源语言修订后: {source_after}")
    print(f"目标语言当前: {target_current}")
    print(f"\n映射结果:")
    print(f"  目标语言修订后: {result['target_after']}")
    print(f"  置信度: {result['confidence']}")
    print(f"  说明: {result.get('explanation', '')}")

    print("\n" + "=" * 50)
    print("V1 旧方法（保留以便对比）")
    print("=" * 50)

    # V1 示例：传递 deletion/insertion 碎片
    source_revision = {
        'deletion': '天气',
        'insertion': '空气质量',
        'context_before': '你好！今天',
        'context_after': '怎么样？'
    }

    target_text = "Hello! How's the weather today?"

    result = mapper.map_revision(
        source_revision,
        target_text,
        source_lang="中文",
        target_lang="英文"
    )

    print("映射结果:")
    print(f"  删除: {result['deletion']}")
    print(f"  插入: {result['insertion']}")
    print(f"  置信度: {result['confidence']}")
    if 'explanation' in result:
        print(f"  说明: {result['explanation']}")
