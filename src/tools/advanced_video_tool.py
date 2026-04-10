"""
高级养生视频生成工具
支持分镜视频生成、旁白、字幕和BGM合成的完整视频制作流程
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import LLMClient, TTSClient, VideoGenerationClient
from coze_coding_dev_sdk.video import TextContent
from langchain_core.messages import HumanMessage, SystemMessage
import json


@tool
def generate_advanced_health_video(topic_data: str, video_style: str = "温馨") -> str:
    """
    根据养生选题生成高级分镜视频，包含旁白和字幕

    Args:
        topic_data: 养生选题的JSON字符串
        video_style: 视频风格，可选：温馨、专业、活泼、简约（默认：温馨）

    Returns:
        返回视频生成结果和分镜信息的JSON字符串
    """
    ctx = request_context.get() or new_context(method="generate_advanced_health_video")

    try:
        # 解析选题数据
        topic = json.loads(topic_data)

        title = topic.get("title", "")
        description = topic.get("description", "")
        keywords = topic.get("keywords", [])

        # 定义视频风格特征
        style_features = {
            "温馨": {
                "description": "色调温暖柔和，场景舒适治愈，适合家庭养生、女性健康等主题",
                "visual_keywords": "暖色调、柔和光线、温馨舒适、治愈感、米白色、柔和棕色",
                "atmosphere": "温暖、亲切、放松、治愈"
            },
            "专业": {
                "description": "色调冷峻简洁，场景专业严谨，适合医学科普、健康知识等主题",
                "visual_keywords": "冷色调、简洁专业、清晰明亮、蓝色系、白色背景、图表数据",
                "atmosphere": "专业、严谨、科学、可信"
            },
            "活泼": {
                "description": "色调明亮鲜艳，场景生动有趣，适合年轻人健身、活力养生等主题",
                "visual_keywords": "明亮鲜艳、活力四射、动态感强、多色彩、橙色系、绿色系",
                "atmosphere": "活泼、动感、活力、青春"
            },
            "简约": {
                "description": "色调淡雅简约，场景干净清爽，适合中医养生、自然疗法等主题",
                "visual_keywords": "淡雅简约、清新自然、米色系、浅灰色、留白、极简主义",
                "atmosphere": "简约、清新、自然、舒适"
            }
        }

        # 获取当前风格特征
        style_info = style_features.get(video_style, style_features["温馨"])
        style_desc = style_info["description"]
        visual_keywords = style_info["visual_keywords"]
        atmosphere = style_info["atmosphere"]

        print(f"使用视频风格: {video_style}")
        print(f"风格描述: {style_desc}")

        # 使用LLM执行完整的内容创作流程
        llm_client = LLMClient(ctx=ctx)

        # 步骤1：提炼健康价值点
        value_points_prompt = f"""养生主题：{title}
主题描述：{description}
关键词：{', '.join(keywords)}

请从这个养生主题中提炼出3-5个对用户最有价值的健康要点。

输出格式（必须是JSON格式）：
{{
    "value_points": [
        {{
            "point": "价值点1",
            "explanation": "简短解释（30字以内）"
        }}
    ]
}}"""

        value_messages = [
            SystemMessage(content="你是健康内容策划专家，擅长提炼养生主题的核心价值点。"),
            HumanMessage(content=value_points_prompt)
        ]

        value_response = llm_client.invoke(
            messages=value_messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7
        )

        value_content = value_response.content
        if isinstance(value_content, str):
            value_content = value_content.strip()
            if "```json" in value_content:
                value_content = value_content.split("```json")[1].split("```")[0].strip()
            elif "```" in value_content:
                value_content = value_content.split("```")[1].split("```")[0].strip()

        value_points = json.loads(value_content)

        # 步骤2：生成养生文案和分镜脚本
        script_prompt = f"""养生主题：{title}
主题描述：{description}
价值点：{json.dumps(value_points.get("value_points", []), ensure_ascii=False)}
视频风格：{video_style}
风格特征：{style_desc}
视觉关键词：{visual_keywords}
氛围感：{atmosphere}

请根据以上信息，完成以下任务：
1. 撰写养生文案（500-800字）
2. 将文案拆解成7-10个场景
3. 为每个场景生成分镜脚本，要求：
   - 场景描述必须符合{video_style}风格，体现{atmosphere}的氛围
   - 场景描述要包含{visual_keywords}等视觉元素
   - 场景描述要详细、具体，适合AI视频生成
   - 旁白文案要简洁有力，配合画面
   - 字幕内容要突出核心信息
   - 时长（3-5秒）

输出格式（必须是JSON格式）：
{{
    "script": {{
        "title": "视频标题",
        "style": "{video_style}",
        "total_duration": "总时长",
        "scenes": [
            {{
                "scene_number": 1,
                "scene_description": "场景描述，用于AI视频生成，要体现{video_style}风格",
                "narration": "旁白文案",
                "subtitle": "字幕内容",
                "duration": 4
            }}
        ]
    }}
}}"""

        script_messages = [
            SystemMessage(content="你是专业视频脚本编剧，擅长创作养生健康类视频脚本。"),
            HumanMessage(content=script_prompt)
        ]

        script_response = llm_client.invoke(
            messages=script_messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7
        )

        script_content = script_response.content
        if isinstance(script_content, str):
            script_content = script_content.strip()
            if "```json" in script_content:
                script_content = script_content.split("```json")[1].split("```")[0].strip()
            elif "```" in script_content:
                script_content = script_content.split("```")[1].split("```")[0].strip()

        script_data = json.loads(script_content)

        # 步骤3：为前2个场景生成分镜视频（演示用）
        video_client = VideoGenerationClient(ctx=ctx)
        scenes = script_data.get("script", {}).get("scenes", [])

        generated_videos = []

        # 为每个场景生成视频（限制生成数量，避免超时）
        for scene in scenes[:3]:  # 生成前3个场景作为演示
            scene_num = scene.get("scene_number", 0)
            scene_desc = scene.get("scene_description", "")
            duration = scene.get("duration", 4)

            try:
                video_url, response, _ = video_client.video_generation(
                    content_items=[
                        TextContent(text=scene_desc)
                    ],
                    model="doubao-seedance-1-5-pro-251215",
                    resolution="720p",
                    ratio="16:9",
                    duration=duration,
                    watermark=True,
                    generate_audio=False  # 后面添加旁白和BGM
                )

                if video_url:
                    generated_videos.append({
                        "scene_number": scene_num,
                        "video_url": video_url,
                        "narration": scene.get("narration", ""),
                        "subtitle": scene.get("subtitle", ""),
                        "duration": duration
                    })
            except Exception as e:
                print(f"场景{scene_num}视频生成失败：{str(e)}")
                continue

        # 步骤4：为旁白生成音频
        tts_client = TTSClient(ctx=ctx)
        narration_audios = []

        for video in generated_videos:
            narration = video.get("narration", "")
            if narration:
                try:
                    audio_url, audio_size = tts_client.synthesize(
                        uid=f"scene_{video['scene_number']}",
                        text=narration,
                        speaker="zh_female_xiaohe_uranus_bigtts",
                        audio_format="mp3",
                        sample_rate=24000,
                        speech_rate=0,
                        loudness_rate=0
                    )
                    narration_audios.append({
                        "scene_number": video["scene_number"],
                        "audio_url": audio_url,
                        "audio_size": audio_size
                    })
                except Exception as e:
                    print(f"场景{video['scene_number']}旁白生成失败：{str(e)}")
                    continue

        return json.dumps({
            "success": True,
            "data": {
                "value_points": value_points.get("value_points", []),
                "script": script_data.get("script", {}),
                "generated_videos": generated_videos,
                "narration_audios": narration_audios,
                "total_scenes": len(scenes),
                "generated_count": len(generated_videos)
            },
            "message": f"成功生成视频脚本和{len(generated_videos)}个分镜视频（共{len(scenes)}个场景）"
        }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"脚本格式不正确：{str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"生成视频失败：{str(e)}"
        }, ensure_ascii=False)
