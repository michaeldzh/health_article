"""
选题来源（3）：用户给出网上的文章链接，AI提炼并基于健康价值重塑后生成选题
抓取文章内容，提炼核心信息，生成适合中老年人的养生选题
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient, FetchClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def topic_from_article(article_url: str) -> str:
    """
    基于用户提供的文章链接，AI提炼内容并基于健康价值重塑后生成适合中老年人的养生选题

    Args:
        article_url: 网上的文章链接

    Returns:
        返回生成的选题信息的JSON字符串
    """
    ctx = request_context.get() or new_context(method="topic_from_article")

    try:
        # 步骤1：抓取文章内容
        fetch_client = FetchClient(ctx=ctx)
        response = fetch_client.fetch(url=article_url)

        if response.status_code != 0:
            return json.dumps({
                "success": False,
                "error": f"文章抓取失败：{response.status_message}"
            }, ensure_ascii=False)

        # 提取文章文本内容
        article_text = "\n".join(
            item.text for item in response.content if item.type == "text"
        )

        if not article_text or len(article_text) < 100:
            return json.dumps({
                "success": False,
                "error": "文章内容不足，无法生成选题"
            }, ensure_ascii=False)

        # 步骤2：使用LLM提炼内容并生成选题
        llm_client = LLMClient(ctx=ctx)

        system_prompt = """你是中老年养生内容策划专家，擅长从文章中提炼内容并基于健康价值重塑，生成适合中老年人的养生选题。

请根据提供的文章内容，完成以下任务：
1. 提炼文章的核心观点和健康价值
2. 分析内容对中老年人的健康意义
3. 基于提炼的价值，重塑生成1个适合中老年人的养生选题
4. 语言要通俗易懂、接地气，避免专业术语
5. 标题要吸引人，符合中老年人的阅读习惯

输出格式（必须严格遵循JSON格式）：
{
    "title": "重塑后的选题标题",
    "description": "选题描述（50-100字）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "target_audience": "中老年养生人群",
    "value_points": ["价值点1", "value点2", "价值点3"],
    "original_summary": "原文核心观点总结（50字以内）",
    "reason": "选题推荐理由（100字以内）"
}"""

        # 截取文章内容，避免过长
        article_text_for_prompt = article_text[:3000] if len(article_text) > 3000 else article_text

        user_message = f"""文章标题：{response.title}
文章链接：{article_url}
文章内容：

{article_text_for_prompt}

请根据以上文章内容，提炼核心健康价值，重塑生成1个适合中老年人的养生选题。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        llm_response = llm_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.8
        )

        # 处理响应内容
        content = llm_response.content
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
            "message": f"成功基于文章内容生成选题：{topic_data.get('title', '')}\n原文标题：{response.title}\n推荐理由：{topic_data.get('reason', '')}"
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
            "error": f"基于文章生成选题失败：{str(e)}"
        }, ensure_ascii=False)
