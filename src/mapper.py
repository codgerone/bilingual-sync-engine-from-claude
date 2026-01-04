"""
LLM映射器 - 使用大语言模型将修订映射到目标语言

核心功能：
1. 将源语言的修订翻译到目标语言
2. 保持修订的语义一致性
3. 考虑上下文进行准确翻译
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
    
    def map_revision(
        self, 
        source_revision: Dict,
        target_text: str,
        source_lang: str = "中文",
        target_lang: str = "英文"
    ) -> Dict:
        """
        将单个修订映射到目标语言
        
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
        批量映射多个修订
        
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
        """构建发送给LLM的提示"""
        
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
    
    # 示例修订
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
