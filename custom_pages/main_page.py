# *-* coding:utf-8 *-*
import streamlit as st
import logging
import time
import datetime
from utils.user_manager import user_manager
from config import LOGGER
from custom_pages.utils.sidebar import render_sidebar
from custom_pages.utils.welcome_message import display_welcome_message
from custom_pages.utils.bot_display import display_active_bots, display_inactive_bots
from config import PRIVATE_CHAT_EMOJI
from openai import OpenAI

def main_page():
    bot_manager = st.session_state.bot_manager
    bot_manager.load_data_from_file()  # 重新加载配置
    
    LOGGER.info(f"Entering main_page. Username: {st.session_state.get('username')}")
    
    render_sidebar()

    # 检查是否选择了本地模型并需要显示独立问答界面
    if 'show_local_assistant' in st.session_state and st.session_state.show_local_assistant and 'selected_local_model' in st.session_state and st.session_state.selected_local_model:
        # 显示本地私人助手界面
        display_local_assistant()
    else:
        # 显示正常的多机器人聊天界面
        display_normal_chat_interface(bot_manager)

# 显示本地私人助手界面
def display_local_assistant():
    import time  # 添加time模块导入
    model_info = st.session_state.selected_local_model
    model_name = model_info['name']  # 当前选择的模型名称
    
    # 添加自定义CSS样式
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #1E3A8A 0%, #3B82F6 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .model-badge {
        background-color: rgba(255, 255, 255, 0.2);
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 0.8em;
        margin-left: 10px;
    }
    .chat-message {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        animation: fadeIn 0.5s;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
    }
    .user-message {
        background-color: #E3F2FD;
        border-left: 4px solid #2196F3;
        margin-left: 20px;
        margin-right: 5px;
    }
    .assistant-message {
        background-color: #F5F5F5;
        border-left: 4px solid #9E9E9E;
        margin-right: 20px;
        margin-left: 5px;
    }
    .message-header {
        font-weight: bold;
        margin-bottom: 5px;
        display: flex;
        align-items: center;
    }
    .message-time {
        font-size: 0.7em;
        color: #888;
        margin-left: 10px;
    }
    .input-area {
        background-color: #F9FAFB;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
    }
    .action-button {
        transition: all 0.3s;
    }
    .action-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(33, 150, 243, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(33, 150, 243, 0); }
        100% { box-shadow: 0 0 0 0 rgba(33, 150, 243, 0); }
    }
    .thinking {
        animation: pulse 2s infinite;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 标题和说明 - 使用自定义HTML
    st.markdown(f"""
    <div class="main-header">
        <div>
            <h2>🔒 {model_info['display_name']} 私人助手</h2>
            <p>本地私人助手，无需联网，保护隐私</p>
        </div>
        <div class="model-badge">{model_name}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 添加返回按钮
    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        if st.button("← 返回", key="return_from_local_assistant", use_container_width=True):
            st.session_state.show_local_assistant = False
            st.rerun()
    
    # 为每个模型创建单独的聊天历史
    if 'model_chat_histories' not in st.session_state:
        st.session_state.model_chat_histories = {}
    
    # 确保当前模型的历史存在
    if model_name not in st.session_state.model_chat_histories:
        st.session_state.model_chat_histories[model_name] = []
    
    # 显示当前模型的聊天历史
    chat_container = st.container(height=500)
    with chat_container:
        # 如果没有聊天历史，显示欢迎信息
        if not st.session_state.model_chat_histories[model_name]:
            st.markdown("""
            <div style="text-align: center; padding: 50px 20px; color: #888;">
                <img src="https://www.svgrepo.com/show/354443/telegram.svg" width="80" style="opacity: 0.5; margin-bottom: 20px;">
                <h3>欢迎使用本地私人助手</h3>
                <p>您的对话将完全在本地处理，不会发送到互联网。</p>
            </div>
            """, unsafe_allow_html=True)
        
        # 显示聊天消息
        import datetime
        for i, msg in enumerate(st.session_state.model_chat_histories[model_name]):
            # 生成一个伪时间戳，根据消息索引递增
            timestamp = datetime.datetime.now() - datetime.timedelta(minutes=(len(st.session_state.model_chat_histories[model_name])-i)*5)
            time_str = timestamp.strftime("%H:%M")
            
            if msg['role'] == 'user':
                st.markdown(f"""
                <div class="chat-message user-message">
                    <div class="message-header">
                        您 <span class="message-time">{time_str}</span>
                    </div>
                    {msg['content']}
                </div>
                """, unsafe_allow_html=True)
            else:
                # 使用消息中存储的模型名称
                st.markdown(f"""
                <div class="chat-message assistant-message">
                    <div class="message-header">
                        🤖 {msg['model_display_name']} <span class="message-time">{time_str}</span>
                    </div>
                    {msg['content']}
                </div>
                """, unsafe_allow_html=True)
    
    # 用户输入区域 - 使用自定义样式
    st.markdown("<div class='input-area'>", unsafe_allow_html=True)
    local_prompt = st.text_area("向本地助手提问...", height=100, key="main_local_assistant_input", 
                             placeholder="输入您的问题，按Enter发送，按Shift+Enter换行")
    
    # 按钮区域 - 使用更现代的布局
    col1, col2, col3 = st.columns([6, 3, 3])
    with col1:
        # 添加一些提示信息
        if st.session_state.model_chat_histories[model_name]:
            message_count = len(st.session_state.model_chat_histories[model_name])
            st.markdown(f"<div style='color:#888;font-size:0.8em;padding-top:8px;'>当前对话共 {message_count} 条消息</div>", unsafe_allow_html=True)
    with col2:
        send_button = st.button("🔔 发送消息", use_container_width=True, key="main_send_to_local_assistant", type="primary", 
                              help="发送消息到本地助手")
    with col3:
        clear_button = st.button("🗑️ 清除聊天", use_container_width=True, key="main_clear_local_chat",
                               help="清除当前所有聊天历史")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 处理发送按钮点击
    if send_button and local_prompt:
        # 添加用户消息到当前模型的历史
        st.session_state.model_chat_histories[model_name].append({"role": "user", "content": local_prompt})
        
        # 使用自定义动画效果的加载提示
        with st.spinner():
            # 显示一个动画效果的思考中消息
            thinking_placeholder = st.empty()
            thinking_placeholder.markdown(f"""
            <div class="chat-message assistant-message thinking" style="opacity:0.7;">
                <div class="message-header">
                    🤖 {model_info['display_name']}
                </div>
                <p>正在思考中...</p>
            </div>
            """, unsafe_allow_html=True)
            try:
                # 创建一个使用本地Ollama的客户端
                client = OpenAI(
                    api_key="ollama",  # Ollama不需要真正的API密钥
                    base_url="http://127.0.0.1:11434/v1",  # Ollama的本地地址
                )
                
                # 准备消息历史
                messages = [
                    {"role": "system", "content": model_info['system_prompt']}
                ]
                
                # 添加最近10条历史消息
                # 只取当前模型的历史消息
                user_assistant_messages = []
                for msg in st.session_state.model_chat_histories[model_name]:
                    if msg['role'] in ['user', 'assistant']:
                        user_assistant_messages.append({"role": msg["role"], "content": msg["content"]})
                
                # 只取最近10条消息
                for msg in user_assistant_messages[-10:]:
                    messages.append(msg)
                
                # 清除思考中的占位符
                thinking_placeholder.empty()
                
                # 创建一个新的占位符用于流式输出
                response_container = st.empty()
                
                # 创建一个空的响应字符串
                assistant_response = ""
                
                # 使用流式输出
                try:
                    # 创建一个临时的消息显示框
                    message_html = f"""
                    <div class="chat-message assistant-message">
                        <div class="message-header">
                            🤖 {model_info['display_name']}
                        </div>
                        <div id="streaming-content"></div>
                    </div>
                    """
                    
                    # 显示初始空消息框
                    response_container.markdown(message_html, unsafe_allow_html=True)
                    
                    # 使用流式API
                    for chunk in client.chat.completions.create(
                        model=model_info['name'],
                        messages=messages,
                        temperature=0.7,
                        stream=True
                    ):
                        # 检查是否有内容
                        if chunk.choices and hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                            # 获取当前块的内容
                            content_chunk = chunk.choices[0].delta.content
                            # 累加到完整响应
                            assistant_response += content_chunk
                            
                            # 更新显示内容
                            updated_message = f"""
                            <div class="chat-message assistant-message">
                                <div class="message-header">
                                    🤖 {model_info['display_name']}
                                </div>
                                {assistant_response}
                            </div>
                            """
                            response_container.markdown(updated_message, unsafe_allow_html=True)
                            
                            # 强制浏览器渲染
                            time.sleep(0.005)  # 更短的延迟以加快响应速度
                            
                except Exception as e:
                    st.error(f"流式输出错误: {str(e)}")
                    # 如果流式输出失败，回退到非流式方式
                    completion = client.chat.completions.create(
                        model=model_info['name'],
                        messages=messages,
                        temperature=0.7
                    )
                    assistant_response = completion.choices[0].message.content
                    
                    # 显示非流式响应
                    response_container.markdown(f"""
                    <div class="chat-message assistant-message">
                        <div class="message-header">
                            🤖 {model_info['display_name']}
                        </div>
                        {assistant_response}
                    </div>
                    """, unsafe_allow_html=True)
                
                # 添加助手回复到当前模型的历史，并存储模型名称
                st.session_state.model_chat_histories[model_name].append({
                    "role": "assistant", 
                    "content": assistant_response,
                    "model_display_name": model_info['display_name']  # 存储模型显示名称
                })
                
                # 不需要清除占位符，因为已经用于显示响应
                # 重新加载页面显示新消息
                st.rerun()
            except Exception as e:
                # 清除思考中的占位符
                thinking_placeholder.empty()
                # 显示错误信息，使用自定义样式
                st.markdown(f"""
                <div style="padding: 15px; background-color: #FEE2E2; border-left: 4px solid #EF4444; border-radius: 5px; margin: 10px 0;">
                    <h4 style="color: #B91C1C; margin: 0 0 10px 0;">连接失败</h4>
                    <p>连接本地Ollama失败: {str(e)}</p>
                    <p>请确保Ollama已安装并运行，且<code>{model_name}</code>模型已下载。</p>
                </div>
                """, unsafe_allow_html=True)
                # 移除失败的消息
                st.session_state.model_chat_histories[model_name].pop()
    
    # 处理清除按钮点击
    if clear_button:
        # 添加确认对话框
        confirm_clear = st.warning("确定要清除所有聊天历史吗？此操作不可恢复。")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("是，清除历史", key="confirm_clear", use_container_width=True):
                # 只清除当前模型的聊天历史
                st.session_state.model_chat_histories[model_name] = []
                st.success("聊天历史已清除")
                time.sleep(1)  # 显示成功消息一秒钟
                st.rerun()
        with col2:
            if st.button("取消", key="cancel_clear", use_container_width=True):
                st.rerun()

# 显示正常的多机器人聊天界面
def display_normal_chat_interface(bot_manager):
    # 添加更多自定义CSS样式
    st.markdown("""
    <style>
    .main-chat-header {
        background: linear-gradient(90deg, #4A148C 0%, #7B1FA2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .bot-card {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
        border-left: 4px solid #7B1FA2;
    }
    .bot-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .bot-header {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    .bot-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #f0f0f0;
        display: flex;
        justify-content: center;
        align-items: center;
        margin-right: 10px;
        font-size: 20px;
    }
    .bot-name {
        font-weight: bold;
        font-size: 1.1em;
    }
    .bot-model {
        font-size: 0.8em;
        color: #666;
        margin-left: 10px;
    }
    .chat-input-area {
        background-color: #F9FAFB;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
        margin-bottom: 20px;
    }
    .welcome-container {
        text-align: center;
        padding: 40px 20px;
        background-color: #F9FAFB;
        border-radius: 10px;
        margin: 20px 0;
    }
    .welcome-icon {
        font-size: 48px;
        margin-bottom: 20px;
        color: #7B1FA2;
    }
    .welcome-title {
        font-size: 24px;
        margin-bottom: 10px;
        color: #333;
    }
    .welcome-subtitle {
        color: #666;
        margin-bottom: 20px;
    }
    .topic-button {
        background-color: #7B1FA2;
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 5px;
        cursor: pointer;
        transition: all 0.3s;
        font-weight: bold;
    }
    .topic-button:hover {
        background-color: #9C27B0;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 创建容器
    header_box = st.container()
    input_box = st.container()
    output_box = st.container()

    enabled_bots = [bot for bot in st.session_state.bots if bot['enable']]
    
    # 标题区域
    with header_box:
        st.markdown(f"""
        <div class="main-chat-header">
            <h2>{PRIVATE_CHAT_EMOJI} 多机器人聊天</h2>
            <p>与多个 AI 助手同时对话，获取多元化的回答</p>
        </div>
        """, unsafe_allow_html=True)

    # 输入区域 - 使用现代化设计
    with input_box:
        st.markdown("<div class='chat-input-area'>", unsafe_allow_html=True)
        
        # 如果没有活跃的聊天，显示欢迎信息
        if not any(bot_manager.get_current_history_by_bot(bot) for bot in enabled_bots):
            st.markdown(f"""
            <div class="welcome-container">
                <div class="welcome-icon">🤖</div>
                <div class="welcome-title">开始您的多机器人对话</div>
                <div class="welcome-subtitle">发送消息后，可以同时和已启用的多个Bot聊天</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 输入框和按钮区域
        col1, col2 = st.columns([9, 1], gap="small")
        
        with col1:
            prompt = st.chat_input("输入您的消息，按Enter发送，按Shift+Enter换行")
            if prompt and not enabled_bots:
                st.warning("请至少启用一个机器人，才能进行对话")

        with col2:
            if st.button("💬 新话题", use_container_width=True, type="primary"):
                if bot_manager.create_new_history_version():
                    st.success("新话题已创建")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.toast("无法创建新话题，当前话题可能为空")
        
        # 显示当前启用的机器人
        if enabled_bots:
            st.markdown("<h4 style='margin-top:15px;'>当前启用的机器人</h4>", unsafe_allow_html=True)
            bot_cols = st.columns(min(4, len(enabled_bots)))
            for i, bot in enumerate(enabled_bots):
                with bot_cols[i % min(4, len(enabled_bots))]:
                    st.markdown(f"""
                    <div class="bot-card">
                        <div class="bot-header">
                            <div class="bot-avatar">🤖</div>
                            <div>
                                <div class="bot-name">{bot['name']}</div>
                                <div class="bot-model">{bot['model']}</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    # 输出区域 - 使用现代化设计
    with output_box:
        # 添加消息容器的样式
        st.markdown("""
        <div style="background-color: #FFFFFF; border-radius: 10px; padding: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
        """, unsafe_allow_html=True)
        
        if enabled_bots:
            # 显示活跃的机器人对话
            display_active_bots(bot_manager=bot_manager, prompt=prompt, show_bots=enabled_bots)
            
        if bot_manager.is_current_history_empty():
            # 如果当前历史为空，显示未激活的机器人和欢迎信息
            if st.session_state.bots:
                st.markdown("<h3 style='margin-top:20px;color:#555;'>可用的机器人</h3>", unsafe_allow_html=True)
                display_inactive_bots(bot_manager=bot_manager, show_bots=st.session_state.bots)
                
            # 使用现代化的欢迎信息
            st.markdown("<hr style='margin: 30px 0;border-color:#eee;'>", unsafe_allow_html=True)
            display_welcome_message(bot_manager)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
    
    # 保存当前的 session_state 到文件
    bot_manager.save_data_to_file()
    user_manager.save_session_state_to_file()

    if prompt and not bot_manager.is_current_history_empty():
        st.rerun()
