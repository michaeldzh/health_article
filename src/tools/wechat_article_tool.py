"""
公众号文章生成工具
根据养生选题生成对应的公众号文章内容和封面图
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient, ImageGenerationClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def generate_wechat_article(topic_data: str) -> str:
    """
    根据养生选题生成对应的公众号文章内容和封面图

    Args:
        topic_data: 养生选题的JSON字符串，包含title、description、keywords等信息

    Returns:
        返回文章内容、封面图URL等信息的JSON字符串
    """
    ctx = request_context.get() or new_context(method="generate_wechat_article")

    try:
        # 解析选题数据
        topic = json.loads(topic_data)

        title = topic.get("title", "")
        description = topic.get("description", "")
        keywords = topic.get("keywords", [])
        season = topic.get("season", "")
        target_audience = topic.get("target_audience", "")

        # 使用LLM生成文章内容
        llm_client = LLMClient(ctx=ctx)

        system_prompt = """你是一位专业的养生内容作家，擅长撰写微信公众号文章。

请根据提供的养生主题，撰写一篇高质量的公众号文章。要求：
1. 文章结构清晰，包含：引言、正文（分3-4个小标题）、结语
2. 内容科学、实用、易懂
3. 语言生动、有趣、符合新媒体风格
4. 适当使用表情符号增加亲和力
5. 文章字数在800-1500字之间
6. 输出格式为HTML，使用<p>、<h3>、<strong>等标签
7. 可以在正文中适当位置插入图片占位符：<img src="IMAGE_PLACEHOLDER" />

输出格式：
直接输出HTML格式的文章内容，不需要其他说明。"""

        user_message = f"""
养生主题：{title}
主题描述：{description}
关键词：{', '.join(keywords)}
季节：{season}
目标人群：{target_audience}

请根据以上信息撰写一篇公众号文章。
"""

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
        article_html = llm_response.content
        if isinstance(article_html, str):
            article_html = article_html.strip()
            # 移除可能的代码块标记
            if article_html.startswith("```"):
                article_html = article_html.split("```")[1]
                if article_html.startswith("html"):
                    article_html = article_html[5:]
                article_html = article_html.strip()
            if article_html.endswith("```"):
                article_html = article_html[:-3].strip()

        # 生成封面图提示词
        cover_prompt_client = LLMClient(ctx=ctx)

        cover_prompt_messages = [
            SystemMessage(content="""你是一位专业的图片提示词设计师，擅长为养生主题生成高质量的图片描述。

请根据提供的养生主题，生成一个适合作为公众号封面图的图片提示词。要求：
1. 画面要美观、专业、有质感
2. 色调要温馨、舒适
3. 元素要与主题相关
4. 适合作为封面图（简洁、大气）

输出格式（纯文本，不要JSON格式，不要代码块）：
直接输出图片提示词，例如："温馨的室内场景，阳光透过窗户洒在瑜伽垫上，旁边放着鲜花和茶杯，色调温暖明亮，简约大气，4K画质" """),
            HumanMessage(content=f"""
养生主题：{title}
主题描述：{description}
关键词：{', '.join(keywords)}

请根据以上信息生成一个封面图提示词。
""")
        ]

        cover_prompt_response = cover_prompt_client.invoke(
            messages=cover_prompt_messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7
        )

        cover_prompt = cover_prompt_response.content
        if isinstance(cover_prompt, str):
            cover_prompt = cover_prompt.strip()
            if cover_prompt.startswith("```"):
                cover_prompt = cover_prompt.split("```")[1]
                if cover_prompt.startswith("json"):
                    cover_prompt = cover_prompt[4:]
                cover_prompt = cover_prompt.strip()
            if cover_prompt.endswith("```"):
                cover_prompt = cover_prompt[:-3].strip()

        # 生成封面图
        image_client = ImageGenerationClient(ctx=ctx)

        image_response = image_client.generate(
            prompt=cover_prompt,
            size="2K",
            watermark=True
        )

        if not image_response.success or not image_response.image_urls:
            return json.dumps({
                "success": False,
                "error": "封面图生成失败",
                "article_html": article_html
            }, ensure_ascii=False)

        cover_image_url = image_response.image_urls[0]

        return json.dumps({
            "success": True,
            "data": {
                "title": title,
                "article_html": article_html,
                "cover_image_url": cover_image_url,
                "cover_prompt": cover_prompt,
                "keywords": keywords,
                "word_count": len(article_html)
            },
            "message": f"成功生成公众号文章：{title}"
        }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"选题数据格式不正确：{str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"生成公众号文章失败：{str(e)}"
        }, ensure_ascii=False)
