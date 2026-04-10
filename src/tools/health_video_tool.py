"""
养生视频生成工具
根据养生选题生成对应的养生视频
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient
from coze_coding_dev_sdk.video import VideoGenerationClient, TextContent
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def generate_health_video(topic_data: str) -> str:
    """
    根据养生选题生成对应的养生视频

    Args:
        topic_data: 养生选题的JSON字符串，包含title、description、keywords等信息

    Returns:
        返回视频URL和生成信息的JSON字符串
    """
    ctx = request_context.get() or new_context(method="generate_health_video")

    try:
        # 解析选题数据
        topic = json.loads(topic_data)

        title = topic.get("title", "")
        description = topic.get("description", "")
        keywords = topic.get("keywords", [])

        # 使用LLM生成视频提示词
        llm_client = LLMClient(ctx=ctx)

        system_prompt = """你是一位专业的视频内容策划师，擅长将养生主题转化为视频提示词。

请根据提供的养生主题，生成一个适合AI视频生成的提示词。要求：
1. 画面要美观、专业、符合养生主题
2. 场景描述要具体、细节丰富
3. 考虑视频的动态效果和流畅性
4. 画面色调要温馨、舒适、有质感
5. 人物动作要自然、优雅

输出格式（必须是纯文本，不要JSON格式，不要代码块）：
直接输出视频提示词，例如：
"温馨的室内场景，阳光透过窗户洒在木质地板上，一位中年女性正在做瑜伽，穿着舒适的白色运动服，动作柔和流畅，背景是绿植和简约的装饰，色调温暖明亮，4K画质，电影感光线" """

        user_message = f"""
养生主题：{title}
主题描述：{description}
关键词：{', '.join(keywords)}

请根据以上信息生成一个适合AI视频生成的提示词。
"""

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
        prompt = llm_response.content
        if isinstance(prompt, str):
            prompt = prompt.strip()
            # 移除可能的代码块标记
            if prompt.startswith("```"):
                prompt = prompt.split("```")[1]
                if prompt.startswith("json"):
                    prompt = prompt[4:]
                prompt = prompt.strip()
            if prompt.endswith("```"):
                prompt = prompt[:-3].strip()

        # 使用视频生成工具生成视频
        video_client = VideoGenerationClient(ctx=ctx)

        video_url, response, _ = video_client.video_generation(
            content_items=[
                TextContent(text=prompt)
            ],
            model="doubao-seedance-1-5-pro-251215",
            resolution="720p",
            ratio="16:9",
            duration=5,
            watermark=True,
            generate_audio=True
        )

        if video_url:
            return json.dumps({
                "success": True,
                "data": {
                    "video_url": video_url,
                    "topic_title": title,
                    "prompt": prompt,
                    "video_info": {
                        "resolution": response.get("resolution"),
                        "duration": response.get("duration"),
                        "ratio": response.get("ratio")
                    }
                },
                "message": f"成功生成养生视频：{title}"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": "视频生成失败",
                "response": response
            }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"选题数据格式不正确：{str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"生成养生视频失败：{str(e)}"
        }, ensure_ascii=False)
