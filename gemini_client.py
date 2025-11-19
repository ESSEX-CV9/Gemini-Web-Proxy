"""
Gemini 浏览器自动化客户端
"""
import asyncio
import time
from typing import AsyncGenerator, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import config
from parser import GeminiResponseParser
import html2text


class GeminiClient:
    """Gemini 浏览器自动化客户端"""
    
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_initialized = False
        self.parser = GeminiResponseParser()
        self._response_chunks = []
        self._response_complete = False
        # 初始化html2text转换器
        self.html_converter = html2text.HTML2Text()
        self.html_converter.body_width = 0  # 不自动换行
        self.html_converter.ignore_links = False  # 保留链接
        self.html_converter.ignore_images = False  # 保留图片
        self.html_converter.ignore_emphasis = False  # 保留强调（加粗、斜体）
    
    def _format_messages_to_prompt(self, messages: list) -> str:
        """
        将OpenAI格式的消息数组转换为单个提示词
        
        格式化策略：
        - system消息作为上下文说明（过滤掉不需要的提示词）
        - 对话历史按 "User: xxx\nAssistant: xxx" 格式组织
        - 最后一条用户消息单独列出
        """
        prompt_parts = []
        
        # 提取system消息（不进行过滤）
        system_messages = []
        for msg in messages:
            if msg.get('role') == 'system':
                content = msg.get('content', '')
                if content:
                    system_messages.append(content)
        
        if system_messages:
            system_content = '\n'.join(system_messages)
            prompt_parts.append(f"[系统说明]\n{system_content}\n")
        
        # 提取对话历史（排除system和最后一条user消息）
        conversation_history = []
        last_user_message = None
        
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '')
            
            if role == 'system':
                continue
            elif role == 'user':
                last_user_message = content
            elif role == 'assistant':
                if last_user_message:
                    conversation_history.append(f"User: {last_user_message}")
                    last_user_message = None
                conversation_history.append(f"Assistant: {content}")
        
        # 添加对话历史
        if conversation_history:
            prompt_parts.append("[对话历史]")
            prompt_parts.extend(conversation_history)
            prompt_parts.append("")
        
        # 添加当前用户消息
        if last_user_message:
            prompt_parts.append(f"{last_user_message}")
        
        return '\n'.join(prompt_parts)
    
        
    async def initialize(self):
        """初始化浏览器"""
        if self.is_initialized:
            return
            
        print("🚀 初始化 Playwright...")
        self.playwright = await async_playwright().start()
        
        print(f"🌐 启动 Chrome 浏览器...")
        print(f"   用户数据目录: {config.CHROME_USER_DATA}")
        
        try:
            # 使用用户的 Chrome 配置（保留登录态）
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=config.CHROME_USER_DATA,
                headless=config.HEADLESS,
                channel="chrome",  # 使用系统安装的 Chrome
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ],
                # 移除硬编码的代理设置，使用系统网络设置（包括VPN）
                timeout=config.TIMEOUT,
            )
            
            # 创建新页面
            self.page = await self.context.new_page()
            
            # 设置默认超时
            self.page.set_default_timeout(config.TIMEOUT)
            
            # 设置监听器
            self._setup_response_listener()
            
            print(f"📱 打开 Gemini 页面...")
            
            # 重试逻辑
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    print(f"   尝试导航到 {config.GEMINI_URL} (第 {attempt + 1} 次)")
                    response = await self.page.goto(config.GEMINI_URL, wait_until="domcontentloaded", timeout=config.TIMEOUT)
                    print(f"   页面状态: {response.status if response else 'Unknown'}")
                    print(f"   当前 URL: {self.page.url}")
                    
                    # 检查是否真的到了 Gemini 页面
                    if "gemini.google.com" in self.page.url:
                        print("✅ 成功加载 Gemini 页面")
                        break
                    else:
                        print(f"⚠️  URL 不正确: {self.page.url}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3)
                        else:
                            raise Exception(f"无法导航到 Gemini 页面，当前 URL: {self.page.url}")
                            
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️  页面加载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                        print("   重试中...")
                        await asyncio.sleep(2)
                    else:
                        print(f"❌ 所有重试失败")
                        raise
            
            # 等待页面加载完成
            print("⏳ 等待页面完全加载...")
            await asyncio.sleep(5)
            
            # 检查是否已经登录
            print("🔍 检查登录状态...")
            textarea = await self.page.query_selector('textarea')
            
            if textarea:
                print("✅ 已登录 Gemini，可以使用！")
            else:
                print("⚠️  未检测到输入框，可能需要登录")
                print("   如果页面显示登录界面，请手动登录后重试")
            
            self.is_initialized = True
            print("✅ 浏览器初始化完成！")
            
        except Exception as e:
            print(f"❌ 浏览器初始化失败: {e}")
            print(f"💡 提示：")
            print(f"   1. 确保没有其他浏览器进程占用 browser_data 目录")
            print(f"   2. 可以删除 browser_data 目录后重试")
            print(f"   3. 设置 config.py 中 HEADLESS=False 查看浏览器")
            raise
    
    def _setup_response_listener(self):
        """设置网络响应监听器 - 使用流式读取"""
        async def handle_response(response):
            url = response.url
            
            # 只监听 StreamGenerate 请求
            if "StreamGenerate" in url:
                try:
                    # 使用 text() 而不是 body()，避免缓存被清除的问题
                    text = await response.text()
                    
                    # 保存响应块
                    self._response_chunks.append(text)
                    
                    print(f"📥 收到响应块 ({len(text)} bytes)")
                    # 总是打印前300个字符用于调试
                    print(f"   内容预览: {text[:300]}...")
                        
                except Exception as e:
                    # 忽略缓存清除错误，这是正常现象
                    if "evicted from inspector cache" in str(e):
                        print(f"ℹ️  响应体已从缓存清除（正常现象，响应已处理）")
                    else:
                        print(f"⚠️  响应处理错误: {e}")
        
        self.page.on("response", handle_response)
    async def _select_model(self, page: Page, model: str):
        """
        在Gemini页面中选择模型
        
        Args:
            page: Playwright页面对象
            model: 模型名称 ("gemini-pro" 或 "gemini-flash")
        """
        try:
            print(f"🎯 选择模型: {model}")
            
            # 验证模型是否有效
            if model not in config.AVAILABLE_MODELS:
                print(f"⚠️  未知模型 {model}，使用默认模型 {config.DEFAULT_MODEL}")
                model = config.DEFAULT_MODEL
            
            model_info = config.AVAILABLE_MODELS[model]
            target_text = model_info["selector_text"]
            
            # 步骤1: 点击模型选择按钮（触发下拉菜单）
            button_selectors = [
                'div[data-test-id="bard-mode-menu-button"]',
                'div[role="button"][data-test-id="bard-mode-menu-button"]',
                'button.input-area-switch:has-text("思考")',
                'button.input-area-switch:has-text("快速")',
                'div.pill-ui-logo-container',
            ]
            
            button_clicked = False
            for selector in button_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=3000, state='visible')
                    if button:
                        await button.click()
                        print(f"✅ 点击了模型选择按钮: {selector}")
                        button_clicked = True
                        break
                except Exception as e:
                    if config.DEBUG:
                        print(f"   尝试选择器 {selector} 失败: {e}")
                    continue
            
            if not button_clicked:
                print("⚠️  未找到模型选择按钮，使用当前默认模型")
                return
            
            # 步骤2: 等待下拉菜单出现
            await asyncio.sleep(1)
            
            # 步骤3: 根据model参数点击对应的选项
            option_selectors = [
                f'button[data-test-id="bard-mode-option-{target_text}"]',
                f'button:has-text("{target_text}")',
                f'button.bard-mode-list-button:has-text("{target_text}")',
                f'button.mat-mdc-menu-item:has-text("{target_text}")',
            ]
            
            option_clicked = False
            for selector in option_selectors:
                try:
                    option = await page.wait_for_selector(selector, timeout=3000, state='visible')
                    if option:
                        await option.click()
                        print(f"✅ 选择了模型: {target_text} ({model})")
                        option_clicked = True
                        break
                except Exception as e:
                    if config.DEBUG:
                        print(f"   尝试选择器 {selector} 失败: {e}")
                    continue
            
            if not option_clicked:
                print(f"⚠️  未找到模型选项 '{target_text}'，使用当前默认模型")
            
            # 等待选择生效
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️  模型选择失败: {e}")
            print("   将使用当前默认模型继续")
    
    
    async def _monitor_dom_updates(self, page: Page, use_streaming: bool = True) -> AsyncGenerator[dict, None]:
        """
        实时监控DOM更新并流式返回
        
        Args:
            page: Playwright页面对象
            use_streaming: 是否使用流式模式（True=DOM监听，False=等待完成后返回）
        
        Returns:
            AsyncGenerator yielding dict with format:
            {
                "thinking": "思维链内容" or None,
                "content": "正文内容" or None
            }
        """
        print(f"🔍 开始监控DOM更新 (流式模式: {use_streaming})")
        
        # 等待正文容器出现
        try:
            await page.wait_for_selector('message-content .markdown', timeout=10000)
            print("✅ 正文容器已出现")
        except Exception as e:
            print(f"⚠️ 等待正文容器超时: {e}")
        
        last_thinking = ""
        last_content = ""
        stable_count = 0
        max_stable_count = int(config.DOM_STABLE_TIMEOUT / config.DOM_POLL_INTERVAL)
        
        # 检查并点击思维链按钮（如果存在）
        thinking_button_clicked = False
        
        while True:
            try:
                # 1. 检查思维链按钮
                if not thinking_button_clicked:
                    thinking_button = await page.query_selector('button[data-test-id="thoughts-header-button"]')
                    if thinking_button:
                        # 检查按钮是否可见和可点击
                        is_visible = await thinking_button.is_visible()
                        if is_visible:
                            try:
                                await thinking_button.click()
                                print("✅ 已点击思维链展开按钮")
                                thinking_button_clicked = True
                                await asyncio.sleep(0.3)  # 等待展开动画
                            except Exception as e:
                                if config.DEBUG:
                                    print(f"⚠️ 点击思维链按钮失败: {e}")
                
                # 2. 提取思维链内容（保留格式）
                current_thinking = None
                if thinking_button_clicked:
                    thinking_elements = await page.query_selector_all('model-thoughts[data-test-id="model-thoughts"] .thoughts-content .markdown')
                    if thinking_elements:
                        thinking_texts = []
                        for elem in thinking_elements:
                            # 使用inner_html获取HTML内容，然后转换为Markdown
                            html_content = await elem.inner_html()
                            if html_content and html_content.strip():
                                # 转换HTML为Markdown
                                markdown_text = self.html_converter.handle(html_content).strip()
                                if markdown_text:
                                    thinking_texts.append(markdown_text)
                        if thinking_texts:
                            current_thinking = "\n\n".join(thinking_texts)
                
                # 3. 提取正文内容（保留格式）
                current_content = None
                content_elements = await page.query_selector_all('message-content[class*="model-response-text"] .markdown')
                if content_elements:
                    content_texts = []
                    for elem in content_elements:
                        # 使用inner_html获取HTML内容，然后转换为Markdown
                        html_content = await elem.inner_html()
                        if html_content and html_content.strip():
                            # 转换HTML为Markdown
                            markdown_text = self.html_converter.handle(html_content).strip()
                            if markdown_text:
                                content_texts.append(markdown_text)
                    if content_texts:
                        current_content = "\n\n".join(content_texts)
                
                # 4. 检测变化
                has_change = False
                
                if current_thinking != last_thinking:
                    has_change = True
                    last_thinking = current_thinking
                    if config.DEBUG and current_thinking:
                        print(f"📝 思维链更新: {current_thinking[:50]}...")
                
                if current_content != last_content:
                    has_change = True
                    last_content = current_content
                    if config.DEBUG and current_content:
                        print(f"📝 正文更新: {current_content[:50]}...")
                
                # 5. 返回数据
                if has_change:
                    stable_count = 0  # 重置稳定计数
                    
                    if use_streaming:
                        # 流式模式：返回增量或完整数据
                        yield {
                            "thinking": current_thinking,
                            "content": current_content
                        }
                else:
                    stable_count += 1
                
                # 6. 检测完成
                # 方法1: 文本稳定一段时间
                if stable_count >= max_stable_count:
                    print(f"✅ 文本已稳定 {config.DOM_STABLE_TIMEOUT} 秒，判定完成")
                    # 返回最终数据
                    if not use_streaming:
                        yield {
                            "thinking": current_thinking,
                            "content": current_content
                        }
                    break
                
                # 方法2: 检测"停止生成"按钮消失（备用）
                stop_button = await page.query_selector('button[aria-label*="Stop"], button[aria-label*="停止"]')
                if not stop_button and stable_count > 5:  # 按钮消失且文本稳定一段时间
                    print("✅ 停止按钮已消失，判定完成")
                    if not use_streaming:
                        yield {
                            "thinking": current_thinking,
                            "content": current_content
                        }
                    break
                
                # 等待下次轮询
                await asyncio.sleep(config.DOM_POLL_INTERVAL)
                
            except Exception as e:
                print(f"⚠️ DOM监控错误: {e}")
                if config.DEBUG:
                    import traceback
                    traceback.print_exc()
                await asyncio.sleep(config.DOM_POLL_INTERVAL)
    
    
    async def send_message(self, messages: list, model: str = "gemini-pro") -> AsyncGenerator[str, None]:
        """
        发送消息到 Gemini 并流式返回响应
        每次都在新标签页中发送，避免对话混杂
        
        Args:
            messages: OpenAI格式的消息数组，例如:
                [
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "How are you?"}
                ]
            model: 模型名称 ("gemini-pro" 或 "gemini-flash")
        """
        if not self.is_initialized:
            await self.initialize()
        
        # 格式化对话历史为单个提示词
        formatted_prompt = self._format_messages_to_prompt(messages)
        
        # 创建新标签页用于本次对话
        print(f"📄 创建新标签页...")
        new_page = await self.context.new_page()
        new_page.set_default_timeout(config.TIMEOUT)
        
        # 为新页面设置响应监听器 - 使用流式读取
        response_chunks = []
        response_lock = asyncio.Lock()  # 添加锁保护并发访问
        
        async def handle_response(response):
            url = response.url
            if "StreamGenerate" in url:
                try:
                    # 使用 text() 而不是 body()，避免缓存被清除的问题
                    text = await response.text()
                    
                    # 使用锁保护列表操作
                    async with response_lock:
                        response_chunks.append(text)
                    
                    print(f"📥 收到响应块 ({len(text)} bytes)")
                    if config.DEBUG:
                        print(f"   内容预览: {text[:300]}...")
                except Exception as e:
                    # 忽略缓存清除错误，这是正常现象
                    if "evicted from inspector cache" in str(e):
                        print(f"ℹ️  响应体已从缓存清除（正常现象，响应已处理）")
                    else:
                        print(f"⚠️  响应处理错误: {e}")
        
        new_page.on("response", handle_response)
        
        found_selector = None  # 定义在函数开头
        
        try:
            # 导航到 Gemini 页面
            print(f"🌐 在新标签页中打开 Gemini...")
            await new_page.goto(config.GEMINI_URL, wait_until="domcontentloaded", timeout=config.TIMEOUT)
            
            # 等待页面加载
            await asyncio.sleep(3)
            
            # 选择模型
            await self._select_model(new_page, model)
            
            print(f"📝 发送消息 ({len(messages)} 条对话历史)")
            print(f"   格式化后的提示词: {formatted_prompt[:100]}...")
            
            # 调试：打印页面标题和 URL
            print(f"🔍 当前页面: {await new_page.title()}")
            print(f"🔍 页面 URL: {new_page.url}")
            
            # 调试：检查页面上的输入元素
            print("🔍 查找输入框...")
            
            # 尝试多种可能的选择器
            possible_selectors = [
                'div.ql-editor[contenteditable="true"]',  # Gemini 的实际输入框
                'div[role="textbox"]',
                'div[contenteditable="true"]',
                'textarea',
                'textarea[placeholder*="输入"]',
                'textarea[placeholder*="Enter"]',
                'textarea.ql-editor',
                'input[type="text"]',
            ]
            
            found_selector = None
            for selector in possible_selectors:
                try:
                    element = await new_page.query_selector(selector)
                    if element:
                        print(f"✅ 找到输入框: {selector}")
                        found_selector = selector
                        break
                except:
                    continue
            
            if not found_selector:
                # 调试：保存页面 HTML 到文件
                html = await new_page.content()
                with open('debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print("❌ 未找到输入框！")
                print("💡 页面 HTML 已保存到 debug_page.html，请检查")
                print("💡 请在浏览器中手动查看页面，右键点击输入框 → 检查元素")
                raise Exception("找不到输入框元素")
            
            # 等待输入框加载
            print(f"⏳ 等待输入框加载: {found_selector}")
            await new_page.wait_for_selector(found_selector, timeout=config.TIMEOUT)
            
            # 输入消息 - 使用JavaScript直接设置内容（避免换行触发发送）
            print(f"💬 输入消息...")
            
            # 获取输入框元素
            input_element = await new_page.query_selector(found_selector)
            
            # 使用JavaScript设置内容
            # 对于contenteditable的div，需要设置innerText或textContent
            # 对于textarea，设置value
            await input_element.evaluate('''(element, text) => {
                if (element.tagName.toLowerCase() === 'textarea') {
                    element.value = text;
                } else if (element.contentEditable === 'true') {
                    // 对于contenteditable元素，设置textContent
                    element.textContent = text;
                    // 触发input事件，让页面知道内容已更改
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }
                // 将光标移到末尾
                if (element.setSelectionRange) {
                    element.setSelectionRange(text.length, text.length);
                }
            }''', formatted_prompt)
            
            print(f"✅ 内容已设置 ({len(formatted_prompt)} 字符)")
            await asyncio.sleep(0.5)
            
            # 查找并点击发送按钮
            print("🔍 查找发送按钮...")
            send_button_selectors = [
                'button[aria-label*="Send"]',
                'button[aria-label*="发送"]',
                'button.send-button',
                'button[data-test-id="send-button"]',
                'button[type="submit"]',
                '[aria-label*="Send message"]',
                'button:has-text("Send")',
                'button:has-text("发送")',
            ]
            
            button_clicked = False
            for selector in send_button_selectors:
                try:
                    # 等待按钮出现（短超时）
                    button = await new_page.wait_for_selector(selector, timeout=2000, state='visible')
                    if button:
                        # 检查按钮是否可点击
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            print(f"✅ 找到发送按钮: {selector}")
                            await button.click()
                            button_clicked = True
                            print(f"✅ 消息已发送")
                            break
                        else:
                            print(f"⚠️  按钮不可用: {selector} (visible={is_visible}, enabled={is_enabled})")
                except Exception as e:
                    if config.DEBUG:
                        print(f"⚠️  尝试按钮 {selector} 失败: {e}")
                    continue
            
            if not button_clicked:
                # 备用方案：按 Enter 键发送
                print("⚠️  未找到发送按钮，尝试按 Enter 键...")
                await new_page.keyboard.press('Enter')
                print("✅ 已按 Enter 键发送")
            
            # 等待响应开始
            await asyncio.sleep(2)
            
            # 判断使用哪种方式获取响应
            use_dom_streaming = config.USE_DOM_STREAMING
            
            if use_dom_streaming:
                # 使用DOM监听方式（真流式）
                print(f"🔄 使用DOM监听模式获取响应")
                async for data in self._monitor_dom_updates(new_page, use_streaming=True):
                    if data:
                        yield data
            else:
                # 使用原有的网络监听方式（假流式）
                print(f"🔄 使用网络监听模式获取响应")
                max_wait_minutes = config.RESPONSE_TIMEOUT // 60
                print(f"⏳ 等待响应（最长等待{max_wait_minutes}分钟，包含thinking时间）...")
                last_text = ""
                retry_count = 0
                max_retries = config.RESPONSE_TIMEOUT * 2  # 每0.5秒检查一次，所以乘以2
                chunks_processed = 0
                
                while retry_count < max_retries:
                    # 使用锁安全访问 response_chunks
                    async with response_lock:
                        current_chunk_count = len(response_chunks)
                    
                    if current_chunk_count > chunks_processed:
                        print(f"📦 处理响应块 {chunks_processed + 1}-{current_chunk_count}")
                        
                        # 处理新的响应块
                        for i in range(chunks_processed, current_chunk_count):
                            async with response_lock:
                                chunk = response_chunks[i]
                            
                            parsed_data = self.parser.parse_stream_chunk(chunk)
                            
                            if parsed_data:
                                # 处理结构化数据
                                if isinstance(parsed_data, dict):
                                    thinking = parsed_data.get('thinking', '')
                                    content = parsed_data.get('content', '')
                                    
                                    if config.DEBUG:
                                        if thinking:
                                            print(f"✅ 解析到思维链: {thinking[:50]}...")
                                        if content:
                                            print(f"✅ 解析到正文: {content[:50]}...")
                                    
                                    # 直接yield整个结构化数据，让parser.to_openai_format处理增量
                                    # 这里简化处理，每次都返回完整数据
                                    yield parsed_data
                                    last_text = parsed_data
                                else:
                                    # 兼容旧格式
                                    print(f"✅ 解析到文本: {str(parsed_data)[:50]}...")
                                    if parsed_data != last_text:
                                        yield parsed_data
                                        last_text = parsed_data
                        
                        chunks_processed = current_chunk_count
                        
                        # 检查是否完成
                        async with response_lock:
                            last_chunk = response_chunks[-1] if response_chunks else ""
                        
                        if '"di"' in last_chunk or 'af.httprm' in last_chunk:
                            print("✅ 响应完成")
                            break
                    
                    await asyncio.sleep(0.5)
                    retry_count += 1
                
                if retry_count >= max_retries:
                    timeout_message = f"⚠️ 响应超时：等待了{max_wait_minutes}分钟仍未收到完整响应。收到了 {len(response_chunks)} 个响应块。"
                    print(timeout_message)
                    # 将超时信息作为文本返回给用户
                    yield f"\n\n{timeout_message}\n\n如果问题持续，请尝试：\n1. 简化问题描述\n2. 重新发送请求\n3. 检查网络连接"
                
        except Exception as e:
            print(f"❌ 发送消息失败: {e}")
            raise
        finally:
            # 关闭新标签页
            try:
                await new_page.close()
                print(f"🗑️  已关闭标签页")
            except:
                pass
    
    async def close(self):
        """关闭浏览器"""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.is_initialized = False
        print("👋 浏览器已关闭")


# 全局客户端实例（单例模式）
_client = None

async def get_client() -> GeminiClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = GeminiClient()
        await _client.initialize()
    return _client