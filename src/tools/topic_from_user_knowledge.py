"""
选题来源（8）：AI自动从用户知识库中选取主题
从用户的知识库中搜索养生相关内容，生成适合中老年人的养生选题
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient, KnowledgeClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def topic_from_user_knowledge() -> str:
    """
    AI自动从用户知识库中选取主题，生成适合中老年人的养生选题

    Returns:
        返回生成的选题建议列表的JSON字符串
    """
    ctx = request_context.get() or new_context(method="topic_from_user_knowledge")

    try:
        # 步骤1：从用户知识库中搜索养生相关内容
        knowledge_client = KnowledgeClient(ctx=ctx)

        # 搜索用户知识库中的养生相关内容
        # 搜索关键词：中老年养生、健康、保健等
        search_queries = [
            "中老年人养生",
            "健康保健",
            "慢性病管理",
            "饮食养生"
        ]

        knowledge_chunks = []
        for query in search_queries:
            response = knowledge_client.search(
                query=query,
                top_k=3,
                min_score=0.6
            )

            if response.code == 0 and response.chunks:
                for chunk in response.chunks:
                    knowledge_chunks.append({
                        "content": chunk.content,
                        "score": chunk.score,
                        "doc_id": chunk.doc_id
                    })

        if not knowledge_chunks:
            return json.dumps({
                "success": False,
                "error": "用户知识库中未找到养生相关内容"
            }, ensure_ascii=False)

        # 步骤2：使用LLM分析并生成选题
        llm_client = LLMClient(ctx=ctx)

        system_prompt = """你是中老年养生内容策划专家，擅长从用户知识库中挖掘适合中老年人的养生选题。

请根据提供的用户知识库内容，生成3-5个适合中老年人的养生选题。要求：
1. 基于知识库中的核心理念和内容
2. 选题要贴近中老年人的生活实际和健康需求
3. 语言通俗易懂、接地气，避免专业术语
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
            "knowledge_source": "知识库来源说明",
            "reason": "选题推荐理由（100字以内）"
        }
    ]
}"""

        # 构建知识库内容文本
        knowledge_text = "\n".join([
            f"内容：{item['content'][:200]}...\n相似度：{item['score']:.2f}\n"
            for item in knowledge_chunks[:10]
        ])

        user_message = f"""以下是用户知识库中的养生相关内容：

{knowledge_text}

请根据以上知识库内容，生成3-5个适合中老年人的养生选题。"""

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
                "knowledge_count": len(knowledge_chunks)
            },
            "message": f"成功基于用户知识库生成{len(suggestions)}个选题建议"
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
            "error": f"基于用户知识库生成选题失败：{str(e)}"
        }, ensure_ascii=False)
