# *-* coding:utf-8 *-*

# 主程序入口，Streamlit应用的核心逻辑

import streamlit as st
import os
import importlib
from utils.user_manager import user_manager  # 确保这行导入存在
from config import LOGGER
from bot.bot_session_manager import BotSessionManager
from tools.tool_manager import ToolManager
import sys

LOGGER.info(sys.executable)

# 打印 Python 可执行文件的路径
st.set_page_config(page_title="多Bot聊天", page_icon="🤖", layout="wide")

# 加载自定义CSS
def load_css():
    try:
        css_file = os.path.join(os.path.dirname(__file__), "static/css/custom.css")
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"""
            <style>
            {f.read()}
            </style>
            """, unsafe_allow_html=True)
        LOGGER.info(f"CSS文件已加载: {css_file}")
    except Exception as e:
        LOGGER.error(f"加载CSS文件时出错: {e}")

def load_page(page_name):
    module = importlib.import_module(f"custom_pages.{page_name}")
    return getattr(module, page_name)

if __name__ == "__main__":
    bot_manager = None
    tool_manager = ToolManager()
    st.session_state.tool_manager = tool_manager
    
    # 加载自定义CSS
    load_css()
    
    # 使用Streamlit原生组件设置标题和样式
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🤖 MultiBot-Chat")
    with col2:
        st.markdown("<div style='text-align: right; padding-top: 10px;'>高级智能对话平台</div>", unsafe_allow_html=True)
    
    # 添加分隔线
    st.divider()
    
    # 确保用户配置目录存在
    if not os.path.exists("user_config"):
        os.makedirs("user_config")
    
    # 初始化会话状态
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ''

    # 处理 URL 参数中的 token
    query_params = st.query_params
    if 'token' in query_params:
        token = query_params['token']
        if user_manager.verify_token(token):
            st.session_state['token'] = token
            st.session_state.logged_in = True
            st.session_state.username = user_manager.get_logged_in_username()
            bot_manager = BotSessionManager(st.session_state.username)
            st.session_state.bot_manager = bot_manager
            st.session_state.bots = bot_manager.bots
            st.session_state.group_history_versions = bot_manager.group_history_versions
            st.session_state.current_group_history_version_idx = bot_manager.current_group_history_version_idx
            if 'page' not in st.session_state:
                st.session_state.page = bot_manager.get_last_visited_page()
            st.session_state.chat_config = bot_manager.get_chat_config()
            st.session_state.current_history_version_idx = bot_manager.current_history_version_idx
            LOGGER.info(f"使用token登录成功. Username: {st.session_state.username}")
        else:
            LOGGER.warning("无效的token")
            st.session_state.logged_in = False
            st.session_state.username = ''
    else:
        st.session_state['token'] = ''
        st.session_state.logged_in = False
        st.session_state.username = ''
        
    if 'page' not in st.session_state:
        st.session_state.page = "login_page"

    col_empty, col_center, col_empty = st.columns([1, 1, 1], gap="small")
    if st.session_state.logged_in:
        if st.session_state.page == "change_password_page":
            change_password_page = load_page("change_password_page")
            with col_center:
                change_password_page()
        elif st.session_state.page == "group_page":
            group_page = load_page("group_page")
            group_page()
        elif st.session_state.page == "main_page":
            main_page = load_page("main_page")
            main_page()
        else:
            st.session_state.page = "group_page"
            group_page = load_page("group_page")
            group_page()
        
        # 更新最后访问的页面
        bot_manager.set_last_visited_page(st.session_state.page)
    else:
        if st.session_state.page == "register_page":
            register_page = load_page("register_page")
            with col_center:
                register_page()
        else:
            st.session_state.page = "login_page"
            login_page = load_page("login_page")
            with col_center:
                login_page()

    github_link = "https://github.com/iZiTTMarvin?tab=projects"  # 用户指定的GitHub链接
    
    # 使用Streamlit原生组件添加页脚
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f'<div style="text-align: center;"><a href="{github_link}" target="_blank">MultiBot-Chat by zm</a></div>', unsafe_allow_html=True)

    if st.session_state.logged_in and bot_manager:
        bot_manager.update_chat_config(st.session_state.chat_config)
        bot_manager.save_data_to_file()
