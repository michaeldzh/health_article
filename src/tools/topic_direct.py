"""
选题来源（1）：用户直接给出选题
接收用户直接提供的选题，规范化处理
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def topic_from_direct(topic_title: str, topic_description: str = "") -> str:
    """
    用户直接给出选题，规范化处理并补充完整信息

    Args:
        topic_title: 用户直接提供的选题标题
        topic_description: 可选的选题描述（如果用户有提供）

    Returns:
        返回规范化的选题信息的JSON字符串
    """
    ctx = request_context.get() or new_context(method="topic_from_direct")

    client = LLMClient(ctx=ctx)

    # 构建系统提示词
    system_prompt = """你是中老年养生内容策划专家，负责规范化用户提供的选题。

请根据用户提供的选题标题，补充完善选题信息，要求：
1. 保持用户原标题的核心意图
2. 补充简短描述，说明选题的价值和适用人群
3. 提取3-5个相关关键词
4. 明确目标人群（必须是中老年人）
5. 分析选题的健康价值点

输出格式（必须严格遵循JSON格式）：
{
    "title": "规范化后的标题",
    "description": "选题描述（50-100字）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "target_audience": "中老年养生人群",
    "value_points": ["价值点1", "价值点2", "价值点3"]
}"""

    # 构建用户消息
    user_message = f"""用户提供的选题标题：{topic_title}"""
    if topic_description:
        user_message += f"\n用户提供的描述：{topic_description}"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]

    try:
        response = client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7
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
            "message": f"成功处理用户直接提供的选题：{topic_data.get('title', '')}"
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
            "error": f"处理用户选题失败：{str(e)}"
        }, ensure_ascii=False)
