"""
网络热点抓取工具
抓取网络上的养生健康相关热点，并给出选题建议
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import SearchClient, LLMClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def fetch_health_trends(topic_keyword: str = "") -> str:
    """
    抓取网络上的养生健康相关热点，并给出选题建议

    Args:
        topic_keyword: 可选的关键词（如"睡眠"、"减肥"、"秋季养生"等），为空则搜索综合热点

    Returns:
        返回热点列表和选题建议的JSON字符串
    """
    ctx = request_context.get() or new_context(method="fetch_health_trends")

    try:
        # 搜索养生健康热点
        search_client = SearchClient(ctx=ctx)

        # 构建搜索关键词
        if topic_keyword:
            query = f"{topic_keyword} 养生 健康 热点"
        else:
            query = "养生健康 热点 最新 2025"

        # 执行搜索，获取最近一周的热点
        response = search_client.search(
            query=query,
            search_type="web",
            count=10,
            need_summary=True,
            time_range="1w"
        )

        if not response.web_items:
            return json.dumps({
                "success": False,
                "error": "未找到相关热点内容"
            }, ensure_ascii=False)

        # 整理热点信息
        trends = []
        for item in response.web_items:
            trend = {
                "content": item.title,
                "author": item.site_name,
                "description": item.snippet,
                "url": item.url,
                "publish_time": item.publish_time,
                "rank_score": item.rank_score
            }
            trends.append(trend)

        # 使用LLM分析热点并给出选题建议
        llm_client = LLMClient(ctx=ctx)

        system_prompt = """你是一位专业的养生内容策划师，擅长从网络热点中挖掘有价值的养生选题。

请根据提供的热点列表，分析并给出选题建议。要求：
1. 优先选择与养生健康相关的热点
2. 选题要有实用性和传播性
3. 给出3-5个选题建议
4. 每个选题要说明推荐理由

输出格式（必须是JSON格式）：
{
    "topic_suggestions": [
        {
            "title": "选题标题",
            "reason": "推荐理由（50-100字）",
            "key_points": ["价值点1", "价值点2", "价值点3"],
            "target_audience": "目标人群"
        }
    ]
}"""

        # 构建热点描述文本
        trends_text = "\n".join([
            f"{i+1}. 标题：{t['content']}\n   来源：{t['author']}\n   描述：{t['description'][:100]}...\n   时间：{t.get('publish_time', '未知')}\n"
            for i, t in enumerate(trends[:8])
        ])

        user_message = f"""以下是从网络抓取的养生健康热点：

{trends_text}

请根据这些热点，给出3-5个适合制作养生视频的选题建议。"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]

        llm_response = llm_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7
        )

        # 处理响应内容
        content = llm_response.content
        if isinstance(content, str):
            content = content.strip()
            # 尝试提取JSON部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

        suggestions = json.loads(content)

        return json.dumps({
            "success": True,
            "data": {
                "trends": trends,
                "suggestions": suggestions.get("topic_suggestions", []),
                "total_trends": len(trends)
            },
            "message": f"成功抓取{len(trends)}个热点，并给出{suggestions.get('topic_suggestions', len([]))}个选题建议"
        }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"选题建议格式不正确：{str(e)}",
            "raw_content": content
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"抓取热点失败：{str(e)}"
        }, ensure_ascii=False)
