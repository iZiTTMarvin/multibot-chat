# *-* coding:utf-8 *-*
import streamlit as st
import logging
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
    model_info = st.session_state.selected_local_model
    model_name = model_info['name']  # 当前选择的模型名称
    
    # 标题和说明
    st.markdown(f"## 🔒 {model_info['display_name']} 私人助手")
    st.markdown(f"使用本地Ollama的{model_name}模型，无需联网，保护隐私")
    
    # 为每个模型创建单独的聊天历史
    if 'model_chat_histories' not in st.session_state:
        st.session_state.model_chat_histories = {}
    
    # 确保当前模型的历史存在
    if model_name not in st.session_state.model_chat_histories:
        st.session_state.model_chat_histories[model_name] = []
    
    # 显示当前模型的聊天历史
    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.model_chat_histories[model_name]:
            if msg['role'] == 'user':
                st.markdown(f"**您:** {msg['content']}")
            else:
                # 使用消息中存储的模型名称，而不是当前选择的模型
                st.markdown(f"**🤖 {msg['model_display_name']}:** {msg['content']}")
    
    # 用户输入区域
    st.markdown("---")
    local_prompt = st.text_area("向本地助手提问", height=100, key="main_local_assistant_input")
    
    # 按钮区域
    col1, col2 = st.columns(2)
    with col1:
        send_button = st.button("发送到本地助手", use_container_width=True, key="main_send_to_local_assistant")
    with col2:
        clear_button = st.button("清除聊天", use_container_width=True, key="main_clear_local_chat")
    
    # 处理发送按钮点击
    if send_button and local_prompt:
        # 添加用户消息到当前模型的历史
        st.session_state.model_chat_histories[model_name].append({"role": "user", "content": local_prompt})
        
        with st.spinner(f"{model_info['display_name']}思考中..."):
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
                
                # 发送请求到本地Ollama
                completion = client.chat.completions.create(
                    model=model_info['name'],  # 使用选择的模型
                    messages=messages,
                    temperature=0.7,
                )
                
                # 获取回复
                assistant_response = completion.choices[0].message.content
                
                # 添加助手回复到当前模型的历史，并存储模型名称
                st.session_state.model_chat_histories[model_name].append({
                    "role": "assistant", 
                    "content": assistant_response,
                    "model_display_name": model_info['display_name']  # 存储模型显示名称
                })
                
                # 重新加载页面显示新消息
                st.rerun()
            except Exception as e:
                st.error(f"连接本地Ollama失败: {str(e)}\n请确保Ollama已安装并运行，且{model_name}模型已下载。")
                # 移除失败的消息
                st.session_state.model_chat_histories[model_name].pop()
    
    # 处理清除按钮点击
    if clear_button:
        # 只清除当前模型的聊天历史
        st.session_state.model_chat_histories[model_name] = []
        st.rerun()

# 显示正常的多机器人聊天界面
def display_normal_chat_interface(bot_manager):
    input_box = st.container()
    st.markdown("---")
    output_box = st.container()

    enabled_bots = [bot for bot in st.session_state.bots if bot['enable']]

    with input_box:
        if not any(bot_manager.get_current_history_by_bot(bot) for bot in enabled_bots):
            st.markdown(f"# {PRIVATE_CHAT_EMOJI}开始对话吧\n发送消息后，可以同时和已启用的多个Bot聊天。")
        
        col1, col2 = st.columns([9, 1], gap="small")
        
        with col1:
            prompt = st.chat_input("按Enter发送消息，按Shift+Enter换行")
            if prompt and not enabled_bots:
                st.warning("请至少启用一个机器人，才能进行对话")

        with col2:
            if st.button("新话题", use_container_width=True):
                if bot_manager.create_new_history_version():
                    st.rerun()
                else:
                    st.toast("无法创建新话题，当前话题可能为空")

    with output_box:

        if enabled_bots:
            display_active_bots(bot_manager=bot_manager, prompt=prompt, show_bots=enabled_bots)
            
        if bot_manager.is_current_history_empty():
            if st.session_state.bots:
                display_inactive_bots(bot_manager=bot_manager, show_bots=st.session_state.bots)
                st.markdown("---")
            display_welcome_message(bot_manager)
        
    
    # 保存当前的 session_state 到文件
    bot_manager.save_data_to_file()
    user_manager.save_session_state_to_file()

    if prompt and not bot_manager.is_current_history_empty():
        st.rerun()
