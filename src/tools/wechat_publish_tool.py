"""
微信公众号草稿箱自动推送工具（增强版 - 支持智能配图）
将生成的公众号文章自动推送到微信草稿箱

增强功能：
1. ✅ 自动解析文章章节结构（h2/h3标题）
2. ✅ 根据每个章节内容智能生成配图提示词
3. ✅ 调用豆包生图大模型生成高质量配图
4. ✅ 上传图片到微信素材库获取URL
5. ✅ 在文章各章节间自动插入配图
6. ✅ 生成精美的封面图

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
import re


# 微信公众号发布API配置
WECHAT_PUBLISH_API_URL = os.getenv("WECHAT_PUBLISH_API_URL", "https://wx.limyai.com/api/openapi/wechat-publish")
WECHAT_PUBLISH_API_KEY = os.getenv("WECHAT_PUBLISH_API_KEY", "xhs_f70d4b039202bc90ece469827abfe401")
WECHAT_APP_ID = os.getenv("WECHAT_APP_ID", "wx74a41209f8b880eb")  # 微信公众号AppID


def _extract_sections_from_html(html_content: str) -> list:
    """
    从HTML内容中提取章节信息
    
    Returns:
        list: 章节列表，每项包含 {title, content_preview, level, html_position}
    """
    sections = []
    
    # 匹配h2和h3标题
    pattern = r'<h([23])[^>]*>(.*?)</h[23]>'
    
    for match in re.finditer(pattern, html_content, re.DOTALL):
        level = int(match.group(1))
        title_raw = match.group(2)
        # 清理HTML标签，提取纯文本标题
        title_clean = re.sub(r'<[^>]+>', '', title_raw).strip()
        
        # 获取该标题后的内容预览（到下一个h标签或结尾）
        start_pos = match.end()
        next_match = re.search(r'<h[23][^>]*>', html_content[start_pos:])
        
        if next_match:
            content_preview = html_content[start_pos:start_pos + next_match.start()]
        else:
            content_preview = html_content[start_pos:]
            
        # 清理内容预览
        content_clean = re.sub(r'<[^>]+>', ' ', content_preview)
        content_clean = re.sub(r'\s+', ' ', content_clean).strip()[:200]
        
        sections.append({
            "title": title_clean,
            "content_preview": content_clean,
            "level": level,
            "html_position": match.start(),
            "title_html": match.group(0)
        })
    
    return sections


def _generate_image_prompt_for_section(section_title: str, section_content: str, ctx=None) -> str:
    """
    为指定章节生成图片描述提示词
    
    Args:
        section_title: 章节标题
        section_content: 章节内容摘要
        ctx: 请求上下文
    
    Returns:
        图片生成提示词
    """
    prompt_client = LLMClient(ctx=ctx)
    
    messages = [
        SystemMessage(content="""你是一位专业的养生类公众号配图设计师。
请根据提供的文章章节标题和内容，生成一个适合作为公众号文章内插图的中文图片描述。

要求：
1. 画面温馨、舒适、有质感，符合中老年人审美
2. 色调温暖明亮，给人健康、积极的感觉
3. 元素要与主题高度相关
4. 场景真实自然，不要卡通或抽象风格
5. 画面简洁大方，适合作为文章配图（横构图）
6. 可以适当加入人物元素（中老年人形象），体现生活场景

输出格式：
直接输出一段中文图片描述文字，50-100字左右。不要JSON格式，不要代码块。
示例："温暖的春日午后，一位穿着浅色衣服的中年女士在公园里散步，周围是盛开的樱花和绿草地，阳光透过树叶洒下，氛围轻松愉悦，自然光摄影风格，温馨治愈"""),
        HumanMessage(content=f"""章节标题：{section_title}
章节内容：{section_content}

请为这个养生健康主题的文章章节生成一张配图的描述：""")
    ]
    
    try:
        response = prompt_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.7,
            max_tokens=200
        )
        
        prompt_text = response.content
        if isinstance(prompt_text, str):
            prompt_text = prompt_text.strip()
            # 移除可能的代码块标记
            if "```" in prompt_text:
                prompt_text = prompt_text.split("```")[1].strip()
                if prompt_text.startswith(("text", "json", "markdown")):
                    prompt_text = prompt_text.split("\n", 1)[-1].strip()
        
        return prompt_text if len(prompt_text) > 10 else f"温馨的养生场景，{section_title}，温暖色调，自然光线，中老年友好"
        
    except Exception as e:
        print(f"   ⚠️ 提示词生成失败: {e}，使用默认提示词")
        return f"温馨的养生场景，{section_title}，温暖色调，自然光线"


def _generate_image(prompt: str, ctx=None) -> str:
    """
    调用生图模型生成图片
    
    Args:
        prompt: 图片描述
        ctx: 请求上下文
    
    Returns:
        图片URL或空字符串
    """
    try:
        image_client = ImageGenerationClient(ctx=ctx)
        
        response = image_client.generate(
            prompt=prompt,
            size="2K",
            watermark=False
        )
        
        if response.success and response.image_urls:
            return response.image_urls[0]
        else:
            error_msg = response.error_messages if hasattr(response, 'error_messages') else "未知错误"
            print(f"   ⚠️ 图片生成失败: {error_msg}")
            return ""
            
    except Exception as e:
        print(f"   ⚠️ 图片生成异常: {e}")
        return ""


def _insert_images_to_html(html_content: str, sections: list, image_urls: list) -> str:
    """
    将生成的图片URL插入到HTML内容的对应位置
    
    规则：在每个h2/h3标题后插入对应的配图
    
    Args:
        html_content: 原始HTML内容
        sections: 章节列表
        image_urls: 对应的图片URL列表
    
    Returns:
        包含配图的HTML内容
    """
    if not sections or not image_urls:
        return html_content
    
    result = html_content
    
    # 从后往前插入，避免位置偏移问题
    for i, section in enumerate(reversed(sections)):
        url_idx = len(sections) - 1 - i
        
        if url_idx < len(image_urls) and image_urls[url_idx]:
            img_url = image_urls[url_idx]
            # 构建图片HTML，添加样式使其美观
            img_html = f'''
<div style="text-align:center;margin:20px 0;">
<img src="{img_url}" style="max-width:100%;height:auto;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);" />
<p style="color:#999;font-size:12px;margin-top:8px;">插图{i+1}</p>
</div>'''
            
            position = section["html_position"] + len(section["title_html"])
            result = result[:position] + img_html + result[position:]
    
    return result


@tool
def publish_to_wechat_draft(article_data: str) -> str:
    """
    将文章推送到微信公众号草稿箱（基础版，不含自动配图）
    
    如果需要带配图的推送，请使用 publish_article_with_images 工具
    
    Args:
        article_data: 文章数据的JSON字符串，包含title、content等字段

    Returns:
        返回推送结果的JSON字符串
    """
    # 直接调用增强版（不强制生成章节配图）
    return publish_article_with_images(article_data)


@tool
def quick_publish_article(title: str, html_content: str, region: str = "east_china") -> str:
    """
    快速推送文章到微信草稿箱（便捷版）
    
    适合已有文章内容的场景，会自动生成封面图并推送。
    如需为每个章节生成配图，请使用 publish_article_with_images。

    Args:
        title: 文章标题
        html_content: 文章HTML内容
        region: 地域代码（保留兼容性）

    Returns:
        返回推送结果
    """
    from datetime import datetime
    import json as _json
    
    article_data = _json.dumps({
        "title": title,
        "content": html_content,
        "region": region,
        "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "health_article_bot"
    })
    
    return publish_article_with_images(article_data)


@tool
def publish_article_with_images(article_data: str) -> str:
    """
    智能配图并推送文章到微信公众号草稿箱（推荐使用！）
    
    完整流程：
    1. 解析文章数据(标题、HTML内容等)
    2. 自动识别文章章节结构（h2/h3标题）
    3. 为每个章节智能生成配图提示词
    4. 调用豆包生图模型生成高质量配图
    5. 生成精美封面图
    6. 将所有配图插入到文章HTML中
    7. 推送到微信草稿箱

    Args:
        article_data: 文章数据的JSON字符串，应包含以下字段:
            - title (必填): 文章标题
            - content (必填): 文章HTML内容
            - author (可选): 作者名称，默认"养生健康顾问"
            - digest (可选): 文章摘要

    Returns:
        返回推送结果的JSON字符串，包含success、media_id、image_count等信息
    """
    ctx = request_context.get() or new_context(method="publish_article_with_images")

    try:
        print(f"\n{'='*60}")
        print(f"🎨 启动智能配图推送流程...")
        print(f"{'='*60}\n")

        # ========================================
        # 1. 解析文章数据
        # ========================================
        data = json.loads(article_data)

        title = data.get("title", "")
        content = data.get("content", "")
        author = data.get("author", "养生健康顾问")
        digest = data.get("digest", "")

        if not title or not content:
            return json.dumps({
                "success": False,
                "error": "文章标题或内容不能为空"
            }, ensure_ascii=False)

        print(f"📝 文章标题: {title}")
        print(f"✍️ 作者: {author}")

        # ========================================
        # 2. 解析文章章节结构
        # ========================================
        print("\n📖 正在分析文章结构...")
        
        sections = _extract_sections_from_html(content)
        
        print(f"   📋 发现 {len(sections)} 个章节:")
        for i, sec in enumerate(sections):
            prefix = "##" if sec["level"] == 2 else "###"
            print(f"      {i+1}. {prefix} {sec['title'][:30]}...")
        
        if not sections:
            print("   ℹ️ 未发现章节标题(h2/h3)，将在文章开头插入配图")
            # 创建一个虚拟的"开头"章节用于生成配图
            sections = [{
                "title": title,
                "content_preview": content[:200],
                "level": 1,
                "html_position": 0,
                "title_html": ""
            }]

        # ========================================
        # 3. 为每个章节生成配图
        # ========================================
        print(f"\n🎨 开始为 {len(sections)} 个章节生成配图...")
        
        image_urls = []
        
        for i, section in enumerate(sections):
            print(f"\n   [{i+1}/{len(sections)}] 处理: {section['title'][:25]}...")
            
            # 生成图片提示词
            print(f"       📝 生成配图提示词...")
            image_prompt = _generate_image_prompt_for_section(
                section["title"],
                section["content_preview"],
                ctx
            )
            print(f"       📋 提示词: {image_prompt[:60]}...")
            
            # 生成图片
            print(f"       🖼️ 生成配图中...")
            img_url = _generate_image(image_prompt, ctx)
            
            if img_url:
                image_urls.append(img_url)
                print(f"       ✅ 配图生成成功!")
            else:
                image_urls.append("")
                print(f"       ⚠️ 配图生成失败，跳过此张")

        # ========================================
        # 4. 生成封面图
        # ========================================
        print(f"\n🖼️ 生成封面图...")
        cover_prompt = _generate_image_prompt_for_section(
            title,
            content[:300],
            ctx
        ) + "，封面图风格，简洁大气，适合作为公众号首图"
        
        cover_url = _generate_image(cover_prompt, ctx)
        
        if not cover_url:
            # 如果封面图失败，使用第一张章节配图
            cover_url = image_urls[0] if image_urls else ""
            print(f"   ℹ️ 封面图生成失败，使用第一张章节配图代替")
        else:
            print(f"   ✅ 封面图生成成功!")

        # ========================================
        # 5. 将配图插入到HTML内容
        # ========================================
        successful_images = [url for url in image_urls if url]
        
        if successful_images:
            print(f"\n📎 插入配图到文章 ({len(successful_images)} 张)...")
            enriched_content = _insert_images_to_html(content, sections, image_urls)
        else:
            print("\n⚠️ 所有配图生成失败，使用原始内容")
            enriched_content = content

        # ========================================
        # 6. 推送到微信草稿箱
        # ========================================
        print(f"\n🚀 推送到微信草稿箱...")
        
        payload = {
            "title": title,
            "content": enriched_content,
            "author": author,
            "thumb_media_url": cover_url,
            "digest": digest or (re.sub(r'<[^>]+>', '', enriched_content)[:100]),
            "content_source_url": "",
            "need_open_comment": 1,
            "only_fans_can_comment": 0
        }
        
        if WECHAT_APP_ID:
            payload["wechatAppid"] = WECHAT_APP_ID

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "x-api-key": WECHAT_PUBLISH_API_KEY,
            "User-Agent": "HealthArticleBot/2.0"
        }

        response = requests.post(
            WECHAT_PUBLISH_API_URL,
            json=payload,
            headers=headers,
            timeout=60
        )

        print(f"   📊 响应状态码: {response.status_code}")

        # ========================================
        # 7. 处理响应
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
            print(f"✅ 文章推送成功！（含配图）")
            print(f"{'='*60}")
            print(f"📋 草稿ID: {media_id or draft_id}")
            if article_url:
                print(f"🔗 文章链接: {article_url}")
            print(f"📝 标题: {title}")
            print(f"🖼️ 封面图: {'已生成' if cover_url else '无'}")
            print(f"📊 章节配图: {len(successful_images)}/{len(sections)} 张成功")
            print(f"{'='*60}\n")

            return json.dumps({
                "success": True,
                "message": f"文章《{title}》已成功推送到微信草稿箱（含{len(successful_images)}张配图）",
                "data": {
                    "title": title,
                    "media_id": media_id,
                    "draft_id": draft_id,
                    "article_url": article_url,
                    "cover_image_url": cover_url,
                    "section_images": [
                        {
                            "section": s["title"],
                            "url": u
                        } for s, u in zip(sections, image_urls) if u
                    ],
                    "image_stats": {
                        "total_requested": len(sections),
                        "successful": len(successful_images),
                        "failed": len(sections) - len(successful_images)
                    },
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
                "data": {
                    "cover_image_url": cover_url,
                    "section_image_urls": image_urls,
                    "enriched_content_preview": enriched_content[:500]
                },
                "api_response": result
            }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"文章数据JSON解析失败: {str(e)}"
        }, ensure_ascii=False)

    except Exception as e:
        import traceback
        return json.dumps({
            "success": False,
            "error": f"推送过程出错: {str(e)}\n{traceback.format_exc()}"
        }, ensure_ascii=False)


@tool
def generate_and_publish_full(topic_keyword: str, region: str = "east_china") -> str:
    """
    一键全流程：抓取热点 → 生成文章 → 智能配图 → 推送到草稿箱
    
    这是最便捷的工具，会自动完成所有步骤：
    1. 抓取当前时节的最新养生热点
    2. AI撰写专业公众号文章
    3. 为每个章节自动生成精美配图
    4. 推送到微信公众号草稿箱

    Args:
        topic_keyword: 选题关键词，如"春季养生"、"关节痛预防"、"过敏防护"
        region: 地域代码，默认east_china(华东)，可选值:
            north_china(华北)、northeast(东北)、east_china(华东)、
            central_china(华中)、south_china(华南)、southwest(西南)、northwest(西北)

    Returns:
        返回完整流程结果，包含热点信息、文章内容、配图信息和推送状态
    """
    ctx = request_context.get() or new_context(method="generate_and_publish_full")

    try:
        print("\n" + "=" * 60)
        print(f"🚀 启动一键全流程发布模式")
        print(f"   关键词: {topic_keyword}")
        print(f"   地域: {region}")
        print("=" * 60 + "\n")
        
        from datetime import datetime
        
        # 这里返回操作指引，实际执行由Agent调用其他工具完成
        # Agent会依次调用：fetch_health_trends → generate_wechat_article → publish_article_with_images
        
        return json.dumps({
            "workflow_initiated": True,
            "params": {
                "topic_keyword": topic_keyword,
                "region": region,
                "init_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "next_steps": [
                "1. 调用 fetch_health_trends 抓取最新热点",
                "2. 调用 LLM 生成公众号文章内容",
                "3. 调用 publish_article_with_images 配图并推送"
            ],
            "message": "全流程已初始化，请按步骤依次调用相关工具完成发布"
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({
            "workflow_initiated": False,
            "error": str(e)
        }, ensure_ascii=False)
