import streamlit as st
from utils.user_manager import user_manager
from custom_pages.utils.sidebar import render_sidebar
from config import LOGGER
from custom_pages.utils.welcome_message import display_welcome_message
from custom_pages.utils.bot_display import display_group_chat_area, display_inactive_bots, use_tool
from utils.chat_utils import get_response_from_bot_group
from config import GROUP_CHAT_EMOJI
from openai import OpenAI

def group_page():
    bot_manager = st.session_state.bot_manager
    bot_manager.load_data_from_file()  # 重新加载配置
    LOGGER.info(f"进入 group_page。用户名: {st.session_state.get('username')}")
    if not user_manager.verify_token(st.session_state.get('token')):
        st.error("用户未登录或会话已过期,请重新登录")
        st.session_state.page = "login_page"
        st.rerun()
    
    render_sidebar()

    input_box = st.container()
    st.markdown("---")
    output_box = st.container()

    is_current_history_empty = bot_manager.is_current_group_history_empty()
    enabled_bots = [bot for bot in st.session_state.bots if bot['enable']]

    with input_box:
        if is_current_history_empty:
            st.markdown(f"# {GROUP_CHAT_EMOJI}开始群聊吧\n所有 Bot 可以和你一起参与讨论。")
        
        col1, col2 = st.columns([9, 1], gap="small")
        
        with col1:
            prompt = st.chat_input("按Enter发送消息，按Shift+Enter换行")

        with col2:
            if st.button("新群聊", use_container_width=True):
                if bot_manager.create_new_group_history_version():
                    st.rerun()
                else:
                    st.toast("无法创建新群聊话题，当前话题可能为空")

    with output_box:
        group_history = bot_manager.get_current_group_history()

        if prompt and st.session_state.bots:
            bot_manager.add_message_to_group_history("user", prompt)
            group_history = bot_manager.get_current_group_history()  # 更新群聊历史
            if bot_manager.get_auto_speak():
                try:
                    if len(enabled_bots)>1:
                        use_tool('chat_pilot',False)
                    else:
                        raise ValueError("Bot数量太少，没有必要规划分工")
                except Exception as e:
                    for bot in enabled_bots:

                        group_user_prompt = bot_manager.get_chat_config().get('group_user_prompt')
                        if group_history[-1].get('role') == 'user':
                            group_user_prompt = ''

                        response_content = get_response_from_bot_group(group_user_prompt, bot, group_history)
                        
                        bot_manager.add_message_to_group_history("assistant", response_content, bot=bot)
                        group_history = bot_manager.get_current_group_history()  # 再次更新群聊历史

            bot_manager.fix_group_history_names()

        if not group_history:
            if st.session_state.bots:
                display_inactive_bots(bot_manager=bot_manager, show_bots=st.session_state.bots)
                st.markdown("---")
            display_welcome_message(bot_manager)
        else:
            # 检查是否选择了本地模型并需要显示独立问答界面
            if 'show_local_assistant' in st.session_state and st.session_state.show_local_assistant and 'selected_local_model' in st.session_state and st.session_state.selected_local_model:
                # 分开显示群聊和本地助手
                st.markdown("### 👫 群聊区域")
                display_group_chat_area(bot_manager=bot_manager, show_bots=st.session_state.bots, histories=group_history)
                
                # 显示分隔线
                st.markdown("---")
                
                # 显示独立问答界面
                model_info = st.session_state.selected_local_model
                st.markdown(f"### 🔒 {model_info['display_name']} 私人助手")
                st.markdown(f"使用本地Ollama的{model_info['name']}模型，无需联网，保护隐私")
                
                # 初始化聊天历史
                if 'local_chat_history' not in st.session_state:
                    st.session_state.local_chat_history = []
                
                # 显示聊天历史
                chat_container = st.container(height=300)
                with chat_container:
                    for msg in st.session_state.local_chat_history:
                        if msg['role'] == 'user':
                            st.markdown(f"**您:** {msg['content']}")
                        else:
                            st.markdown(f"**🤖 {model_info['display_name']}:** {msg['content']}")
                
                # 用户输入框
                local_prompt = st.text_area("向本地助手提问", height=100, key="local_assistant_input")
                
                # 发送和清除按钮并排
                col1, col2 = st.columns(2)
                with col1:
                    send_button = st.button("发送到本地助手", use_container_width=True, key="send_to_local_assistant")
                with col2:
                    clear_button = st.button("清除聊天", use_container_width=True, key="clear_local_chat")
                
                # 处理发送按钮点击
                if send_button and local_prompt:
                    # 添加用户消息到历史
                    st.session_state.local_chat_history.append({"role": "user", "content": local_prompt})
                    
                    with st.spinner("本地助手思考中..."):
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
                            for msg in st.session_state.local_chat_history[-10:]:
                                messages.append({"role": msg["role"], "content": msg["content"]})
                            
                            # 发送请求到本地Ollama
                            completion = client.chat.completions.create(
                                model=model_info['name'],  # 使用选择的模型
                                messages=messages,
                                temperature=0.7,
                            )
                            
                            # 获取回复
                            assistant_response = completion.choices[0].message.content
                            
                            # 添加助手回复到历史
                            st.session_state.local_chat_history.append({"role": "assistant", "content": assistant_response})
                            
                            # 重新加载页面显示新消息
                            st.rerun()
                        except Exception as e:
                            st.error(f"连接本地Ollama失败: {str(e)}\n请确保Ollama已安装并运行，且{model_info['name']}模型已下载。")
                            # 移除失败的消息
                            st.session_state.local_chat_history.pop()
                
                # 处理清除按钮点击
                if clear_button:
                    st.session_state.local_chat_history = []
                    st.rerun()
            else:
                # 如果没有选择本地模型或不需要显示独立问答界面，只显示群聊
                display_group_chat_area(bot_manager=bot_manager, show_bots=st.session_state.bots, histories=group_history)

    # 保存当前的 session_state 到文件
    bot_manager.save_data_to_file()
    user_manager.save_session_state_to_file()

    if prompt and group_history:
        st.rerun()