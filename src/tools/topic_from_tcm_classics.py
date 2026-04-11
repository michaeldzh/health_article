"""
选题来源（7）：AI自动从中医权威文献和知识中选取主题
搜索中医权威文献、经典著作等，生成适合中老年人的养生选题
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient, SearchClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def topic_from_tcm_classics() -> str:
    """
    AI自动从中医权威文献和知识中选取主题，生成适合中老年人的养生选题

    Returns:
        返回生成的选题建议列表的JSON字符串
    """
    ctx = request_context.get() or new_context(method="topic_from_tcm_classics")

    try:
        # 步骤1：搜索中医权威文献和知识
        search_client = SearchClient(ctx=ctx)

        # 搜索中医权威文献
        query = "中医 养生 黄帝内经 中老年人 经典著作"

        response = search_client.search(
            query=query,
            search_type="web",
            count=10,
            need_summary=True,
            time_range="6m"  # 最近6个月
        )

        if not response.web_items:
            return json.dumps({
                "success": False,
                "error": "未找到中医权威文献内容"
            }, ensure_ascii=False)

        # 整理搜索结果
        tcm_items = []
        for item in response.web_items[:8]:
            tcm_items.append({
                "title": item.title,
                "source": item.site_name,
                "summary": item.snippet,
                "url": item.url
            })

        # 步骤2：使用LLM分析并生成选题
        llm_client = LLMClient(ctx=ctx)

        system_prompt = """你是中老年养生内容策划专家，擅长从中医权威文献和知识中挖掘适合中老年人的养生选题。

请根据提供的中医权威文献内容，生成3-5个适合中老年人的养生选题。要求：
1. 基于中医经典理论（如黄帝内经等）的核心理念
2. 结合现代生活，选题要贴近中老年人的生活实际
3. 语言通俗易懂，将中医理论转化为生活化表达
4. 强调实用性和可操作性
5. 标题要吸引人，符合中老年人的阅读习惯

输出格式（必须严格遵循JSON格式）：
{
    "topic_suggestions": [
        {
            "title": "选题标题",
            "description": "选题描述（50-100字）",
            "keywords": ["关键词1", "关键词2", "关键词3"],
            "target_audience": "中老年养生人群",
            "value_points": ["价值点1", "价值点2", "价值点3"],
            "tcm_source": "中医来源说明（如：黄帝内经、伤寒论等）",
            "reason": "选题推荐理由（100字以内）"
        }
    ]
}"""

        # 构建中医文献内容文本
        tcm_text = "\n".join([
            f"标题：{item['title']}\n来源：{item['source']}\n摘要：{item['summary'][:150]}...\n"
            for item in tcm_items
        ])

        user_message = f"""以下是中医权威文献和知识内容：

{tcm_text}

请根据以上中医权威文献内容，生成3-5个适合中老年人的养生选题。"""

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
        suggestions_data = json.loads(content)
        suggestions = suggestions_data.get("topic_suggestions", [])

        return json.dumps({
            "success": True,
            "data": {
                "suggestions": suggestions,
                "tcm_count": len(tcm_items)
            },
            "message": f"成功基于中医权威文献生成{len(suggestions)}个选题建议"
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
            "error": f"基于中医权威文献生成选题失败：{str(e)}"
        }, ensure_ascii=False)
