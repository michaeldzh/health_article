"""
养生选题工具
根据当前时间、季节或用户关键词生成养生主题选题
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def generate_health_topic(user_keyword: str = "") -> str:
    """
    根据当前时间、季节或用户关键词生成养生主题选题

    Args:
        user_keyword: 用户可选的主题关键词（如"夏季养生"、"减肥"、"睡眠"等），为空则自动生成

    Returns:
        返回包含选题标题和描述的JSON字符串
    """
    ctx = request_context.get() or new_context(method="generate_health_topic")

    client = LLMClient(ctx=ctx)

    # 构建系统提示词 - 明确面向中老年人
    system_prompt = """你是一位专业的中老年养生内容策划师，擅长根据季节、时间和用户需求创作适合中老年人的养生主题选题。

请生成一个中老年养生主题，要求：
1. **目标人群**：必须是中老年人（50岁以上），内容贴近他们的生活实际
2. **选题方向**：慢性病管理、日常保健、饮食调理、运动养生、心理养生、节气养生等
3. **语言风格**：通俗易懂、接地气，避免专业术语，要有亲切感
4. **实用性**：选择日常可操作、成本低的养生方法，避免过度养生
5. **时效性**：要结合当前季节、节气特点
6. 标题要吸引人，符合中老年人的阅读习惯

输出格式（必须严格遵循JSON格式）：
{
    "title": "选题标题",
    "description": "选题描述（50-100字）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "season": "当前季节",
    "target_audience": "中老年养生人群"
}"""

    # 构建用户消息
    if user_keyword:
        user_message = f"请根据用户关键词：{user_keyword}，生成一个养生主题选题"
    else:
        user_message = "请根据当前季节和时间，自动生成一个养生主题选题"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
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

            # 尝试提取JSON部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

        # 验证JSON格式
        topic_data = json.loads(content)

        return json.dumps({
            "success": True,
            "data": topic_data,
            "message": f"成功生成养生选题：{topic_data.get('title', '')}"
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
            "error": f"生成养生选题失败：{str(e)}"
        }, ensure_ascii=False)
