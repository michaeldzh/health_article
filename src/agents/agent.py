"""
养生视频智能体
根据用户指令自动生成养生视频和公众号文章
"""
import os
import json
from typing import Annotated
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
from coze_coding_utils.runtime_ctx.context import default_headers
from storage.memory.memory_saver import get_memory_saver

# 导入工具
# 选题来源工具
from tools.topic_direct import topic_from_direct
from tools.topic_from_inspiration import topic_from_inspiration
from tools.topic_from_article import topic_from_article
from tools.topic_from_video import topic_from_video
from tools.health_trends_tool import fetch_health_trends
from tools.topic_from_authority_health import topic_from_authority_health
from tools.topic_from_tcm_classics import topic_from_tcm_classics
from tools.topic_from_user_knowledge import topic_from_user_knowledge
from tools.health_topic_tool import generate_health_topic
from tools.health_video_tool import generate_health_video
from tools.wechat_article_tool import generate_wechat_article
from tools.advanced_video_tool import generate_advanced_health_video
from tools.video_composite_tool import composite_health_video

LLM_CONFIG = "config/agent_llm_config.json"

# 默认保留最近 20 轮对话 (40 条消息)
MAX_MESSAGES = 40

def _windowed_messages(old, new):
    """滑动窗口: 只保留最近 MAX_MESSAGES 条消息"""
    return add_messages(old, new)[-MAX_MESSAGES:]  # type: ignore

class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]

def build_agent(ctx=None):
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    config_path = os.path.join(workspace_path, LLM_CONFIG)

    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")

    llm = ChatOpenAI(
        model=cfg['config'].get("model"),
        api_key=api_key,
        base_url=base_url,
        temperature=cfg['config'].get('temperature', 0.7),
        streaming=True,
        timeout=cfg['config'].get('timeout', 600),
        extra_body={
            "thinking": {
                "type": cfg['config'].get('thinking', 'disabled')
            }
        },
        default_headers=default_headers(ctx) if ctx else {}
    )

    return create_agent(
        model=llm,
        system_prompt=cfg.get("sp"),
        tools=[
            # 选题来源工具（8种）
            topic_from_direct,
            topic_from_inspiration,
            topic_from_article,
            topic_from_video,
            fetch_health_trends,
            topic_from_authority_health,
            topic_from_tcm_classics,
            topic_from_user_knowledge,
            # 视频和文章生成工具
            generate_health_topic,
            generate_health_video,
            generate_wechat_article,
            generate_advanced_health_video,
            composite_health_video
        ],
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )
