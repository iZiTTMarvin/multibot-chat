import streamlit as st
import random
from config import EMOJI_OPTIONS, SHOW_SECRET_INFO, GUEST_USERNAMES
from utils.user_manager import user_manager
from custom_pages.utils.dialogs import edit_bot, add_new_bot, edit_bot_config
import logging
import re
from openai import OpenAI
import subprocess
import json
import time
import requests

LOGGER = logging.getLogger(__name__)

def render_sidebar():
    bot_manager = st.session_state.bot_manager
    chat_config = bot_manager.get_chat_config()

    with st.sidebar:

        with st.expander("我的"):
            st.markdown(f"当前用户：{st.session_state.username}")
            st.warning("不要把您的密码告诉任何人，以免大模型密钥被盗用！")
            
            if st.session_state.username not in GUEST_USERNAMES:
                if SHOW_SECRET_INFO or not st.session_state.bots:
                    if st.button("导入配置", use_container_width=True):
                        edit_bot_config()
                if st.button("修改密码", use_container_width=True):
                    st.session_state.page = "change_password_page"
                    st.rerun()

            if st.button("退出登录", use_container_width=True):
                confirm_action_logout()
        
        with st.expander("聊天设置", expanded=True):

            if st.session_state.page == "group_page":
                if st.button("返回对话模式",use_container_width=True):
                    st.session_state.page = "main_page"
                    bot_manager.set_last_visited_page("main_page")
                    st.rerun()
            else:
                if st.button("切换到群聊模式",use_container_width=True, type='primary'):
                    st.session_state.page = "group_page"
                    bot_manager.set_last_visited_page("group_page")
                    st.rerun()

            new_config = {}
            force_system_prompt = st.text_area("强制系统提示词", value=chat_config.get('force_system_prompt', ''), key="force_system_prompt", placeholder='强制所有Bot使用此提示词，如果留空则遵循Bot设置')
            if force_system_prompt != chat_config.get('force_system_prompt'):
                chat_config['force_system_prompt'] = force_system_prompt
                bot_manager.update_chat_config(chat_config)
                bot_manager.save_data_to_file()  # 立即保存到文件
                LOGGER.info(f"Updated and saved force_system_prompt: {force_system_prompt}")

            if st.session_state.page == "group_page":
                new_config['group_user_prompt'] = st.text_area("群聊接力提示词", value=chat_config.get('group_user_prompt',''), height=68, placeholder='提示Bot在群聊时应该如何接力，如果留空则由Bot自由发挥')
                new_config['group_history_length'] = st.slider("群聊携带对话条数", min_value=1, max_value=20, value=chat_config['group_history_length'], help="Bot在参与群聊时可以看到多少条历史消息")
            else:
                new_config['history_length'] = st.slider("携带对话条数", min_value=1, max_value=20, value=chat_config['history_length'])
            
            bot_manager.update_chat_config(new_config)

        if st.session_state.page == "group_page":
            with st.expander("群聊历史话题", expanded=True):
                group_history_options = [f"{v['name']}" for v in bot_manager.group_history_versions]
                
                current_index = min(bot_manager.current_group_history_version_idx, len(group_history_options) - 1)
                
                new_index = st.selectbox(
                    "可以回到旧话题继续聊天",
                    options=range(len(group_history_options)),
                    format_func=lambda i: group_history_options[i],
                    index=current_index
                )

                if new_index != bot_manager.current_group_history_version_idx:
                    bot_manager.current_group_history_version_idx = new_index
                    bot_manager.save_data_to_file()
                    st.rerun()

                if st.button("清理所有历史话题", use_container_width=True):
                    confirm_action_clear_grouop_histsorys()

        else:
            if st.session_state.page == "main_page":
                with st.expander("历史话题", expanded=True):
                    history_versions = bot_manager.history_versions
                    history_options = [f"{v['name']}" for v in history_versions]
                    
                    # 确保 current_history_version_idx 在有效范围内
                    current_history_version_idx = min(bot_manager.current_history_version_idx, len(history_options) - 1)
                    
                    def on_history_change():
                        new_version_index = st.session_state.history_version_selector
                        participating_bots = bot_manager.get_participating_bots(new_version_index)
                        
                        # 更新 bot_manager 的 current_history_version_idx
                        bot_manager.current_history_version_idx = new_version_index
                        
                        # 更新机器人状态：启用所有参与聊天的机器人
                        for bot in bot_manager.bots:
                            bot['enable'] = bot['id'] in participating_bots and bot_manager.get_current_history_by_bot(bot)
                        
                        # 保存更新后的数据
                        bot_manager.save_data_to_file()

                    st.selectbox(
                        "可以回到旧话题继续聊天",
                        options=range(len(history_options)),
                        format_func=lambda i: history_options[i],
                        index=current_history_version_idx,
                        key="history_version_selector",
                        on_change=on_history_change
                    )

                    if st.button("清理所有历史话题", use_container_width=True):
                        confirm_action_clear_historys()

        # 添加本地私人助手区域
        with st.expander("🔒 本地私人助手", expanded=True):
            st.markdown("选择本地Ollama模型，无需联网，保护隐私")
            
            # 初始化会话状态
            if 'selected_local_model' not in st.session_state:
                st.session_state.selected_local_model = None
            
            # 检查Ollama服务是否运行
            def check_ollama_running():
                try:
                    client = OpenAI(
                        api_key="ollama",
                        base_url="http://127.0.0.1:11434/v1",
                    )
                    # 尝试获取模型列表
                    response = requests.get("http://127.0.0.1:11434/api/tags")
                    return True, response.json().get('models', [])
                except Exception as e:
                    return False, str(e)
            
            # 检查模型是否已下载
            def is_model_downloaded(model_name, model_list):
                return any(model.get('name') == model_name for model in model_list)
            
            # 运行模型
            def run_model(model_name):
                try:
                    # 使用subprocess运行命令
                    process = subprocess.Popen(
                        ["ollama", "run", model_name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                    
                    # 模型运行成功
                    st.success(f"模型 {model_name} 已启动!")
                    return True
                except Exception as e:
                    st.error(f"启动模型时出错: {str(e)}")
                    return False
            
            # 检查Ollama服务状态
            ollama_running, model_list = check_ollama_running()
            
            # 定义常用模型的显示名称和系统提示词
            model_display_names = {
                "qwen2.5:3b": "🤖 独特小Q",
                "llama3.2.8b:latest": "🐋 Meta Llama 3",
                "mistral:latest": "🌟 Mistral AI",
                "gemma:latest": "💎 Gemma",
                "phi3:latest": "🔮 Phi-3",
                "llama3:latest": "🦙 Llama 3",
                "codellama:latest": "👨‍💻 Code Llama",
                "dolphin-mistral:latest": "🐬 Dolphin"
            }
            
            # 默认系统提示词模板
            default_system_prompt = "你是一个有用的本地私人助手，基于Ollama的{model_name}模型。你要记住当用户询问你是谁时，你要回答你是许皓辰的私人模型。你会尽可能提供有用、安全和诚实的回答。"
            
            if ollama_running:
                # 从Ollama获取可用模型列表
                available_models = []
                for model in model_list:
                    model_name = model.get('name')
                    # 使用预定义名称或原始名称
                    display_name = model_display_names.get(model_name, f"📦 {model_name}")
                    available_models.append({"name": model_name, "display_name": display_name})
                
                # 如果有可用模型
                if available_models:
                    # 创建选择模型的下拉框
                    st.markdown("### 选择本地模型")
                    
                    # 准备下拉框选项
                    model_options = [f"{m['display_name']} ({m['name']})" for m in available_models]
                    selected_model_index = 0
                    
                    # 如果已经选择了模型，找到它在列表中的索引
                    if st.session_state.selected_local_model:
                        current_model_name = st.session_state.selected_local_model['name']
                        for i, m in enumerate(available_models):
                            if m['name'] == current_model_name:
                                selected_model_index = i
                                break
                    
                    # 显示下拉框
                    selected_option = st.selectbox(
                        "可用的本地模型",
                        options=range(len(model_options)),
                        format_func=lambda i: model_options[i],
                        index=selected_model_index,
                        key="local_model_selector"
                    )
                    
                    # 获取选择的模型信息
                    selected_model = available_models[selected_option]
                    
                    # 添加自定义系统提示词
                    system_prompt = st.text_area(
                        "系统提示词", 
                        value=st.session_state.selected_local_model.get('system_prompt', default_system_prompt.format(model_name=selected_model['name'])) if st.session_state.selected_local_model else default_system_prompt.format(model_name=selected_model['name']),
                        key="local_model_system_prompt",
                        height=100
                    )
                    
                    # 启动模型按钮
                    if st.button("启动选中的模型", use_container_width=True, key="start_selected_model"):
                        # 运行模型
                        if run_model(selected_model['name']):
                            # 设置选中的模型
                            st.session_state.selected_local_model = {
                                "name": selected_model['name'],
                                "display_name": selected_model['display_name'],
                                "system_prompt": system_prompt
                            }
                            # 设置标志来指示应该显示独立问答界面
                            st.session_state.show_local_assistant = True
                            st.rerun()
                else:
                    st.warning("未检测到已安装的Ollama模型。请使用'ollama pull <model_name>'命令安装模型。")
                    st.code("ollama pull llama3.2.8b:latest", language="bash")
                    st.code("ollama pull qwen2.5:3b", language="bash")
            else:
                st.error("Ollama服务未运行，请先启动Ollama服务")
                st.code("ollama serve", language="bash")
            
            # 显示当前选择的模型
            if st.session_state.selected_local_model:
                st.success(f"当前选择的模型: {st.session_state.selected_local_model['display_name']} ({st.session_state.selected_local_model['name']})")
            
            # 显示Ollama状态
            if ollama_running:
                st.success("Ollama服务正在运行")
                # 显示已下载的模型
                if model_list:
                    st.markdown("**已下载的模型:**")
                    for model in model_list:
                        st.markdown(f"- **{model.get('name')}** ({model.get('size', '?')}MB)")
            else:
                st.error("Ollama服务未运行，请先启动Ollama服务")
            
            # 添加说明
            st.markdown("**使用说明:**")
            st.markdown("1. 下载并安装[Ollama](https://ollama.com/)")
            st.markdown("2. 启动Ollama服务")
            st.markdown("3. 点击上方模型按钮，在右侧显示独立问答界面")
            
            # 初始化独立问答界面标志
            if 'show_local_assistant' not in st.session_state:
                st.session_state.show_local_assistant = False

        with st.expander("Bot管理"):
            with st.container():
                for i, bot in enumerate(st.session_state.bots):
                    bot_name_display = f"{bot.get('avatar', '') or '🤖'} **{bot['name']}**" if bot['enable'] else f"{bot.get('avatar', '🤖')} ~~{bot['name']}~~"
                    system_prompt = bot.get('system_prompt','')
                    system_prompt_warp = re.sub(r'((?:[\u0100-\u9fff]|[^\u0000-\u00ff]{1,2}){1,20})', r'\1\n\n', system_prompt[0:100])
                    if st.button(bot_name_display, key=f"__edit_bot_{i}", help=f"{system_prompt_warp}\n\n***【点击按钮可编辑】***".strip(), use_container_width=True):
                        edit_bot(bot)
    
            if st.button("新增Bot", type="primary", use_container_width=True):
                st.session_state.avatar = random.choice(EMOJI_OPTIONS)
                add_new_bot()


@st.dialog('清空所有历史对话', width='small')
def confirm_action_clear_historys():
    bot_manager = st.session_state.bot_manager
    st.markdown('确定要清理所有历史话题吗？')
    st.warning('此操作不可撤销。', icon="⚠️")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认", key="confirm_button", use_container_width=True):
            bot_manager.clear_all_histories()
            st.rerun()
    with col2:
        if st.button("取消", key="cancel_button", use_container_width=True):
            st.rerun()


@st.dialog('清空所有历史群聊', width='small')
def confirm_action_clear_grouop_histsorys():
    bot_manager = st.session_state.bot_manager
    st.markdown('确定要清理所有群聊历史话题吗？')
    st.warning('此操作不可撤销。', icon="⚠️")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认", key="confirm_button", use_container_width=True):
            bot_manager.clear_all_group_histories()
            st.rerun()
    with col2:
        if st.button("取消", key="cancel_button", use_container_width=True):
            st.rerun()

@st.dialog('退出登录', width='small')
def confirm_action_logout():
    st.markdown('确定要退出吗？')
    col1, col2 = st.columns(2)
    with col1:
        if st.button("确认", key="confirm_button", use_container_width=True):
            # 清除会话状态
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            # 重置必要的状态
            st.session_state.logged_in = False
            st.session_state.page = "login_page"
            # 销毁token
            user_manager.destroy_token()
            st.rerun()
    with col2:
        if st.button("取消", key="cancel_button", use_container_width=True):
            st.rerun()
            