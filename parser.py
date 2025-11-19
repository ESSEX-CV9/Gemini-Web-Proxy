"""
解析 Gemini 响应格式并转换为 OpenAI 格式
"""
import json
import re
from typing import Generator, Optional


class GeminiResponseParser:
    """Gemini 响应解析器"""
    
    def __init__(self):
        self.conversation_id = None
        self.response_id = None
        
    def parse_stream_chunk(self, chunk: str) -> Optional[dict]:
        """
        解析单个流式响应块
        返回包含思维链和正文的字典，如果没有则返回 None
        
        返回格式：
        {
            "thinking": "思维链内容" or None,
            "content": "正文内容" or None
        }
        
        响应格式（三层JSON嵌套）：
        )]}'
        
        216
        [["wrb.fr",null,"内部JSON字符串"]]
        806
        [["wrb.fr",null,"内部JSON字符串"]]
        ...
        
        内部JSON字符串格式：
        [null, ["c_xxx", "r_xxx"], null, null, [[实际内容]], ...]
        
        实际内容格式：
        ["rc_xxx", ["文本内容"], ..., [思维链内容在索引43], ...]
        """
        if not chunk or len(chunk) < 10:
            return None
            
        try:
            # 去掉 Google 的安全前缀
            cleaned = chunk.replace(")]}'\n", "").strip()
            if not cleaned:
                return None
            
            # 分割成行
            lines = cleaned.split('\n')
            if config.DEBUG:
                print(f"[DEBUG] 解析响应: 共 {len(lines)} 行")
            
            # 动态处理所有行，提取最后一次有效的文本
            # 因为流式响应会不断更新，每次都是完整文本
            last_valid_text = None
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # 跳过空行
                if not line:
                    i += 1
                    continue
                
                # 如果是纯数字，跳过（这是长度标记）
                if line.isdigit():
                    if config.DEBUG:
                        print(f"   行 {i}: 跳过长度标记 {line}")
                    i += 1
                    continue
                
                # 尝试解析 JSON（第一层）
                try:
                    outer_data = json.loads(line)
                    
                    # 验证外层结构：[["wrb.fr", null, "..."]]
                    if not isinstance(outer_data, list) or len(outer_data) == 0:
                        i += 1
                        continue
                    
                    # 提取中层数据：["wrb.fr", null, "..."]
                    middle_data = outer_data[0]
                    if not isinstance(middle_data, list) or len(middle_data) < 3:
                        i += 1
                        continue
                    
                    # 检查是否是 wrb.fr 数据
                    if middle_data[0] != "wrb.fr":
                        i += 1
                        continue
                    
                    if config.DEBUG:
                        print(f"   行 {i}: [OK] 找到 wrb.fr 数据")
                    
                    # 提取内层JSON字符串（第二层解析）
                    inner_json_str = middle_data[2]
                    if not isinstance(inner_json_str, str):
                        i += 1
                        continue
                    
                    # 解析内层JSON
                    inner_data = json.loads(inner_json_str)
                    
                    if config.DEBUG:
                        print(f"   内层数据类型: {type(inner_data)}, 长度: {len(inner_data) if isinstance(inner_data, list) else 'N/A'}")
                    
                    # 提取文本内容（第三层）- 返回结构化数据
                    extracted_data = self._extract_text_from_data(inner_data)
                    if extracted_data:
                        last_valid_text = extracted_data
                        if config.DEBUG:
                            if isinstance(extracted_data, dict):
                                thinking = extracted_data.get('thinking', '')
                                content = extracted_data.get('content', '')
                                print(f"   [OK] 提取到数据:")
                                if thinking:
                                    print(f"      思维链 ({len(thinking)} 字符): {thinking[:50]}...")
                                if content:
                                    print(f"      正文 ({len(content)} 字符): {content[:50]}...")
                            else:
                                print(f"   [OK] 提取到文本 ({len(str(extracted_data))} 字符): {str(extracted_data)[:50]}...")
                    
                except json.JSONDecodeError as e:
                    if config.DEBUG:
                        print(f"   行 {i}: JSON 解析失败 - {str(e)[:50]}")
                except Exception as e:
                    if config.DEBUG:
                        print(f"   行 {i}: 处理错误 - {str(e)[:50]}")
                
                i += 1
            
            # 返回最后一次提取到的有效文本
            return last_valid_text
                    
        except Exception as e:
            print(f"[ERROR] 解析错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_text_from_data(self, data) -> Optional[dict]:
        """
        从嵌套的数据结构中提取文本
        
        返回格式：
        {
            "thinking": "思维链内容" or None,
            "content": "正文内容" or None
        }
        
        支持三种格式：
        1. 普通文本：data[4][0][1][0]
        2. Canvas文档：data[4][0][12] 或其他位置包含文档内容
        3. Think内容：data[4][0][43] 包含思考过程
        
        数据结构：
        [null, ["c_xxx", "r_xxx"], null, null, [[response_data], ...], ...]
        
        response_data 格式：
        ["rc_xxx", ["文本内容"], ..., [think_data], ..., [canvas_data], ...]
        """
        if not isinstance(data, list) or len(data) < 5:
            return None
        
        try:
            # 提取 data[4]（包含响应数据的数组）
            if not isinstance(data[4], list) or len(data[4]) == 0:
                return None
            
            # 提取 data[4][0]（第一个响应块）
            response_block = data[4][0]
            if not isinstance(response_block, list) or len(response_block) < 2:
                return None
            
            # 验证是否是有效的响应块（以 rc_ 开头）
            if not isinstance(response_block[0], str) or not response_block[0].startswith('rc_'):
                return None
            
            # 首先尝试提取 think 内容 data[4][0][43]
            think_text = self._extract_think_content(response_block)
            
            # 然后提取普通文本 data[4][0][1][0]
            text_array = response_block[1]
            basic_text = None
            
            if isinstance(text_array, list) and len(text_array) > 0:
                if isinstance(text_array[0], str):
                    basic_text = text_array[0]
            elif isinstance(text_array, str):
                basic_text = text_array
            
            # 检查是否包含Canvas链接
            has_canvas = basic_text and 'googleusercontent.com/immersive_entry_chip' in basic_text
            
            if has_canvas:
                # 尝试提取Canvas文档内容
                canvas_text = self._extract_canvas_content(response_block)
                if canvas_text:
                    # 返回结构化数据
                    return {
                        "thinking": think_text,
                        "content": canvas_text
                    }
            
            # 返回结构化数据
            return {
                "thinking": think_text,
                "content": basic_text
            }
                            
        except (IndexError, TypeError, KeyError) as e:
            if config.DEBUG:
                print(f"   [WARN] 提取文本错误: {e}")
                print(f"      数据结构: {str(data)[:200]}...")
            return None
    
    def _extract_canvas_content(self, response_block: list) -> Optional[str]:
        """
        从响应块中提取Canvas文档内容
        
        Canvas数据通常在response_block的某个位置（如索引12或13）
        格式：[["filename.txt", "uuid", "title", null, "content...", ...], ...]
        """
        try:
            # 遍历response_block查找Canvas内容
            for item in response_block:
                if not isinstance(item, list):
                    continue
                
                # 查找包含文档内容的数组
                for sub_item in item:
                    if isinstance(sub_item, list) and len(sub_item) > 4:
                        # 检查是否包含文件名（.txt结尾）
                        if isinstance(sub_item[0], str) and '.txt' in sub_item[0]:
                            # 提取标题和内容
                            title = sub_item[2] if len(sub_item) > 2 else None
                            content = sub_item[4] if len(sub_item) > 4 else None
                            
                            if content and isinstance(content, str):
                                # 组合标题和内容
                                if title:
                                    return f"# {title}\n\n{content}"
                                return content
            
            return None
            
        except Exception as e:
            if config.DEBUG:
                print(f"   [WARN] 提取Canvas内容错误: {e}")
            return None
    
    def _extract_think_content(self, response_block: list) -> Optional[str]:
        """
        从响应块中动态提取思维链内容
        
        策略: 遍历整个 response_block,通过内容特征识别思维链
        
        思维链特征:
        1. 是一个列表类型
        2. 包含嵌套数组结构
        3. 不在索引1位置(索引1是正文内容)
        
        格式示例:
        [[\"**标题**\\n\\n内容\"], [[[\"**标题**\\n\\n内容\"],\"\",\"\",\"\"]], ...]
        """
        try:
            all_think_texts = []
            
            # 遍历 response_block 的所有元素(跳过索引0和1)
            for idx, item in enumerate(response_block):
                # 跳过索引0(rc_id)和索引1(正文内容)
                if idx <= 1:
                    continue
                
                # 检查是否是思维链数据
                if self._is_thinking_data(item):
                    # 提取思维链文本
                    texts = self._extract_texts_from_thinking_data(item)
                    all_think_texts.extend(texts)
            
            if all_think_texts:
                # 合并所有思维链文本
                combined_text = "\n\n".join(all_think_texts)
                if config.DEBUG:
                    print(f"   [OK] 动态提取到 {len(all_think_texts)} 个思维链块 ({len(combined_text)} 字符)")
                    print(f"      预览: {combined_text[:100]}...")
                return combined_text
            
            return None
            
        except Exception as e:
            if config.DEBUG:
                print(f"   [WARN] 提取思维链内容错误: {e}")
            return None
    
    def _is_thinking_data(self, data) -> bool:
        """
        判断数据是否为思维链数据
        
        判断依据:
        1. 必须是列表
        2. 包含字符串内容(任意长度,任意内容)
        
        注意: 不再检查 "**" 标记和文本长度,因为:
        - 思维链可能没有标题
        - 思维链可能很短
        """
        if not isinstance(data, list) or len(data) == 0:
            return False
        
        # 递归检查是否包含字符串内容
        def contains_text(obj, depth=0, max_depth=5):
            """递归检查是否包含文本内容"""
            if depth > max_depth:
                return False
            
            if isinstance(obj, str):
                # 只要是非空字符串就认为是有效内容
                return len(obj.strip()) > 0
            elif isinstance(obj, list):
                for item in obj:
                    if contains_text(item, depth + 1, max_depth):
                        return True
            return False
        
        return contains_text(data)
    
    def _extract_texts_from_thinking_data(self, data) -> list:
        """
        从思维链数据中提取所有文本
        
        支持多层嵌套结构:
        - ["text"]
        - [["text"]]
        - [[["text"], "", "", ""]]
        
        提取所有非空字符串,不限制长度和格式
        """
        texts = []
        
        def extract_recursive(obj, depth=0, max_depth=5):
            """递归提取文本"""
            if depth > max_depth:
                return
            
            if isinstance(obj, str):
                # 提取所有非空字符串
                stripped = obj.strip()
                if stripped:
                    texts.append(stripped)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item, depth + 1, max_depth)
        
        extract_recursive(data)
        return texts
    
    def to_openai_format(self, data_chunk, is_done: bool = False, model: str = "gemini-pro") -> str:
        """
        转换为 OpenAI SSE 格式
        
        Args:
            data_chunk: 文本块或结构化数据 {"thinking": str, "content": str}
            is_done: 是否完成
            model: 模型名称
        """
        if is_done:
            return "data: [DONE]\n\n"
        
        # 构建delta对象
        delta = {}
        
        # 处理结构化数据
        if isinstance(data_chunk, dict):
            thinking = data_chunk.get('thinking')
            content = data_chunk.get('content')
            
            # 根据配置选择格式
            if config.ENABLE_THINKING and config.THINKING_FORMAT == "reasoning_content":
                # o1系列格式：使用单独的reasoning_content字段
                if thinking:
                    delta["reasoning_content"] = thinking
                if content:
                    delta["content"] = content
            elif config.ENABLE_THINKING and config.THINKING_FORMAT == "inline":
                # 内联格式：在content中用<think>标签包裹
                combined_content = ""
                if thinking:
                    combined_content = f"<think>\n{thinking}\n</think>"
                if content:
                    if combined_content:
                        combined_content += f"\n\n{content}"
                    else:
                        combined_content = content
                if combined_content:
                    delta["content"] = combined_content
            else:
                # 不启用思维链，只返回content
                if content:
                    delta["content"] = content
        else:
            # 兼容旧格式：直接是字符串
            if data_chunk:
                delta["content"] = str(data_chunk)
        
        # 如果delta为空，不发送
        if not delta:
            return ""
        
        response = {
            "id": f"chatcmpl-{self.response_id or 'unknown'}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": None
                }
            ]
        }
        
        return f"data: {json.dumps(response)}\n\n"


import time
import config
