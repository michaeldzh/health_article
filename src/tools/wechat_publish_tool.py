"""
微信公众号草稿箱自动推送工具
将生成的公众号文章自动推送到微信草稿箱

支持的自定义API:
- API地址: https://wx.limyai.com/api/openapi/wechat-publish
- 认证方式: API Key (x-api-key header)
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import ImageGenerationClient, LLMClient
from langchain_core.messages import HumanMessage, SystemMessage
import requests
import json
import os


# 微信公众号发布API配置
WECHAT_PUBLISH_API_URL = os.getenv("WECHAT_PUBLISH_API_URL", "https://wx.limyai.com/api/openapi/wechat-publish")
WECHAT_PUBLISH_API_KEY = os.getenv("WECHAT_PUBLISH_API_KEY", "xhs_f70d4b039202bc90ece469827abfe401")
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "")  # 微信公众号AppID


@tool
def publish_to_wechat_draft(article_data: str) -> str:
    """
    将生成的公众号文章推送到微信公众号草稿箱
    
    完整流程:
    1. 解析文章数据(标题、HTML内容、封面图URL等)
    2. 如果没有封面图，自动生成封面
    3. 调用自定义API将文章推送到微信草稿箱
    4. 返回推送结果(包含草稿ID、文章链接等)

    Args:
        article_data: 文章数据的JSON字符串，应包含以下字段:
            - title (必填): 文章标题
            - content (必填): 文章HTML内容
            - cover_image_url (可选): 封面图URL，如果不传则自动生成
            - author (可选): 作者名称
            - digest (可选): 文章摘要

    Returns:
        返回推送结果的JSON字符串，包含success、media_id、article_url等字段
    """
    ctx = request_context.get() or new_context(method="publish_to_wechat_draft")

    try:
        # ========================================
        # 1. 解析文章数据
        # ========================================
        print(f"\n{'='*60}")
        print(f"📤 开始推送文章到微信公众号草稿箱...")
        print(f"{'='*60}\n")

        data = json.loads(article_data)

        title = data.get("title", "")
        content = data.get("content", "")
        cover_image_url = data.get("cover_image_url", "")
        author = data.get("author", "养生健康顾问")
        digest = data.get("digest", "")

        if not title or not content:
            return json.dumps({
                "success": False,
                "error": "文章标题或内容不能为空",
                "required_fields": ["title", "content"]
            }, ensure_ascii=False)

        print(f"📝 文章标题: {title}")
        print(f"✍️ 作者: {author}")
        print(f"🖼️ 封面图: {'已有' if cover_image_url else '需要生成'}")

        # ========================================
        # 2. 如果没有封面图，自动生成
        # ========================================
        if not cover_image_url:
            print("\n🎨 正在生成封面图...")

            # 使用LLM生成封面图提示词
            prompt_client = LLMClient(ctx=ctx)
            
            prompt_messages = [
                SystemMessage(content="""你是一位专业的图片提示词设计师。
根据文章标题生成一个温馨、专业的养生主题封面图描述。
要求：画面美观、色调温暖、适合中老年人审美。
直接输出提示词文本，不要JSON格式。"""),
                HumanMessage(content=f"请为这篇文章生成封面图描述：{title}")
            ]

            prompt_response = prompt_client.invoke(
                messages=prompt_messages,
                model="doubao-seed-2-0-lite-260215",
                temperature=0.7
            )

            image_prompt = prompt_response.content
            if isinstance(image_prompt, str):
                image_prompt = image_prompt.strip()
                # 移除可能的代码块标记
                if "```" in image_prompt:
                    image_prompt = image_prompt.split("```")[1].strip()
                    if image_prompt.startswith(("text", "json", "markdown")):
                        image_prompt = image_prompt.split("\n", 1)[-1].strip()

            print(f"   📋 封面图提示词: {image_prompt[:50]}...")

            # 生成封面图
            image_client = ImageGenerationClient(ctx=ctx)
            
            image_response = image_client.generate(
                prompt=image_prompt,
                size="2K",
                watermark=False
            )

            if not image_response.success or not image_response.image_urls:
                return json.dumps({
                    "success": False,
                    "error": "封面图生成失败，无法继续推送"
                }, ensure_ascii=False)

            cover_image_url = image_response.image_urls[0]
            print(f"   ✅ 封面图生成成功: {cover_image_url[:80]}...")

        # ========================================
        # 3. 构建请求数据
        # ========================================
        print("\n📦 构建推送请求...")

        # 检查是否有AppID配置
        if not WECHAT_APP_ID:
            print("   ⚠️ 未配置微信公众号AppID")
            print("   💡 请在环境变量中设置 WECHAT_APP_ID")

        payload = {
            "title": title,
            "content": content,
            "author": author,
            "thumb_media_url": cover_image_url,  # 封面图URL
            "digest": digest or (content[:100].replace('<', '').replace('>', '') if len(content) > 100 else content.replace('<', '').replace('>', '')),
            "content_source_url": "",
            "need_open_comment": 1,  # 开启评论
            "only_fans_can_comment": 0,  # 所有人可评论
        }

        # 如果有AppID，添加到请求中
        if WECHAT_APP_ID:
            payload["wechatAppid"] = WECHAT_APP_ID

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "x-api-key": WECHAT_PUBLISH_API_KEY,
            "User-Agent": "HealthArticleBot/1.0"
        }

        # ========================================
        # 4. 调用API推送
        # ========================================
        print(f"🚀 推送到: {WECHAT_PUBLISH_API_URL}")
        
        response = requests.post(
            WECHAT_PUBLISH_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )

        print(f"   📊 响应状态码: {response.status_code}")

        # ========================================
        # 5. 处理响应
        # ========================================
        try:
            result = response.json()
        except ValueError:
            result = {"raw_response": response.text}

        if response.status_code == 200 and result.get("success", False):
            media_id = result.get("media_id", "")
            article_url = result.get("article_url", "")
            draft_id = result.get("draft_id", "")

            print(f"\n{'='*60}")
            print(f"✅ 文章推送成功！")
            print(f"{'='*60}")
            print(f"📋 草稿ID: {media_id or draft_id}")
            if article_url:
                print(f"🔗 文章链接: {article_url}")
            print(f"📝 标题: {title}")
            print(f"{'='*60}\n")

            return json.dumps({
                "success": True,
                "message": f"文章《{title}》已成功推送到微信草稿箱",
                "data": {
                    "title": title,
                    "media_id": media_id,
                    "draft_id": draft_id,
                    "article_url": article_url,
                    "cover_image_url": cover_image_url,
                    "push_time": __import__("datetime").datetime.now().isoformat()
                }
            }, ensure_ascii=False)

        else:
            error_msg = result.get("error", result.get("message", response.text))
            error_code = result.get("code", result.get("errcode", response.status_code))

            print(f"\n❌ 推送失败!")
            print(f"   错误码: {error_code}")
            print(f"   错误信息: {error_msg}")

            return json.dumps({
                "success": False,
                "error": f"推送失败: {error_msg}",
                "error_code": error_code,
                "api_response": result
            }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"文章数据JSON解析失败: {str(e)}"
        }, ensure_ascii=False)

    except requests.exceptions.Timeout:
        return json.dumps({
            "success": False,
            "error": "API请求超时（30秒），请检查网络连接后重试"
        }, ensure_ascii=False)

    except requests.exceptions.ConnectionError as e:
        return json.dumps({
            "success": False,
            "error": f"无法连接到API服务器: {str(e)}"
        }, ensure_ascii=False)

    except Exception as e:
        import traceback
        return json.dumps({
            "success": False,
            "error": f"推送过程出错: {str(e)}\n{traceback.format_exc()}"
        }, ensure_ascii=False)


@tool
def quick_publish_article(title: str, html_content: str, region: str = "east_china") -> str:
    """
    一键完成：抓取热点 + 生成文章 + 推送到微信草稿箱的完整流程
    
    这是一个便捷工具，会自动完成：
    1. 获取当前时节信息
    2. 生成符合时节+地域的文章内容
    3. 自动生成精美封面图
    4. 推送到微信公众号草稿箱

    Args:
        title: 文章标题
        html_content: 文章HTML内容
        region: 地域代码，默认east_china(华东)，可选值:
            north_china(华北)、northeast(东北)、east_china(华东)、
            central_china(华中)、south_china(华南)、southwest(西南)、northwest(西北)

    Returns:
        返回完整流程的结果JSON字符串，包含热点信息、文章内容和推送结果
    """
    ctx = request_context.get() or new_context(method="quick_publish_article")

    try:
        print("\n" + "="*60)
        print("🚀 启动一键发布流程")
        print("="*60 + "\n")

        # 步骤1: 准备文章数据
        from datetime import datetime
        
        article_data = {
            "title": title,
            "content": html_content,
            "region": region,
            "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "health_article_bot"
        }

        print(f"📝 准备文章: {title}")
        print(f"📍 目标地域: {region}")
        print(f"⏰ 发布时间: {article_data['publish_time']}")

        # 步骤2: 调用推送函数
        publish_result = json.loads(publish_to_wechat_draft(json.dumps(article_data)))
        
        # 组合返回结果
        final_result = {
            "workflow_success": publish_result.get("success", False),
            "article_info": {
                "title": title,
                "region": region,
                "word_count": len(html_content),
                "has_cover": True
            },
            "publish_result": {
                "success": publish_result.get("success", False),
                "media_id": publish_result.get("data", {}).get("media_id", ""),
                "article_url": publish_result.get("data", {}).get("article_url", ""),
                "error": publish_result.get("error", None)
            },
            "summary": (
                f"文章《{title}》"
                + ("已成功" if publish_result.get("success") else "未能")
                + "推送到微信草稿箱"
            )
        }

        print("\n" + "="*60)
        print(f"🎉 流程完成: {final_result['summary']}")
        print("="*60 + "\n")

        return json.dumps(final_result, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "workflow_success": False,
            "error": f"一键发布流程出错: {str(e)}\n{traceback.format_exc()}"
        }, ensure_ascii=False)
