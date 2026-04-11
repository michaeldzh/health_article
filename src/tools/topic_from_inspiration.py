"""
选题来源（2）：用户给出灵感，AI基于大众健康价值定义生成选题
接收用户的灵感关键词，AI生成1个选题
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def topic_from_inspiration(inspiration: str) -> str:
    """
    基于用户提供的灵感，AI生成1个适合中老年人的养生选题

    Args:
        inspiration: 用户的灵感关键词或简短描述

    Returns:
        返回生成的选题信息的JSON字符串
    """
    ctx = request_context.get() or new_context(method="topic_from_inspiration")

    client = LLMClient(ctx=ctx)

    # 构建系统提示词
    system_prompt = """你是中老年养生内容策划专家，擅长从用户的灵感中挖掘有价值的中老年养生选题。

请根据用户提供的灵感关键词，生成1个适合中老年人的养生选题。要求：
1. 深入分析灵感的健康价值，结合大众健康需求
2. 选题要贴近中老年人的生活实际和健康需求
3. 语言通俗易懂、接地气，避免专业术语
4. 强调实用性和可操作性
5. 标题要吸引人，符合中老年人的阅读习惯

输出格式（必须严格遵循JSON格式）：
{
    "title": "生成的选题标题",
    "description": "选题描述（50-100字）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "target_audience": "中老年养生人群",
    "value_points": ["价值点1", "价值点2", "价值点3"],
    "reason": "选题推荐理由（100字以内）"
}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"用户的灵感：{inspiration}")
    ]

    try:
        response = client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.8
        )

        # 处理响应内容
        content = response.content
        if isinstance(content, str):
            content = content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

        # 验证JSON格式
        topic_data = json.loads(content)

        return json.dumps({
            "success": True,
            "data": topic_data,
            "message": f"成功基于用户灵感生成选题：{topic_data.get('title', '')}\n推荐理由：{topic_data.get('reason', '')}"
        }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"生成的选题格式不正确：{str(e)}",
            "raw_content": content
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"基于灵感生成选题失败：{str(e)}"
        }, ensure_ascii=False)
