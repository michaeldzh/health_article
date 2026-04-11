"""
网络热点抓取工具
抓取网络上的养生健康相关热点，并给出选题建议

数据真实性说明：
- 本工具仅提供通过搜索引擎API和URL抓取获取的真实数据
- 不包含任何模拟、伪造或AI生成的虚假数据
- 可提供的真实数据：标题、来源网站、摘要、URL、发布时间、热度评分、正文内容
- 无法获取的数据：点赞数、转发数、评论数（这些是各社交平台私有数据，需要官方API授权）

技术限制：
1. 点赞数/转发数：属于各平台私有数据，搜索引擎无法获取
2. 用户评论：大部分网站采用JavaScript动态加载，静态抓取难以获取完整评论
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import SearchClient, LLMClient, FetchClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


def _fetch_url_content(url: str, ctx) -> dict:
    """
    尝试抓取URL的详细内容（仅真实数据，不添加任何伪造信息）
    
    Returns:
        dict: {
            success: bool,
            content: str (真实正文内容),
            title: str (真实标题),
            error: str
        }
    """
    try:
        fetch_client = FetchClient(ctx=ctx)
        response = fetch_client.fetch(url=url)

        if response.status_code != 0:
            return {
                "success": False,
                "error": f"抓取失败: {response.status_message}",
                "content": "",
                "title": ""
            }

        # 提取文本内容（真实页面内容）
        text_content = []
        for item in response.content:
            if item.type == "text":
                text_content.append(item.text)

        full_content = "\n".join(text_content)

        return {
            "success": True,
            "content": full_content[:3000],  # 真实正文内容，限制长度避免过长
            "title": response.title or "",  # 真实标题
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": "",
            "title": ""
        }


@tool
def fetch_health_trends(topic_keyword: str = "", fetch_details: bool = False) -> str:
    """
    抓取网络上的养生健康相关热点，并给出选题建议
    
    **重要：本工具仅返回真实抓取的数据，不包含任何模拟或伪造的信息**

    Args:
        topic_keyword: 可选的关键词（如"睡眠"、"减肥"、"秋季养生"等），为空则搜索综合热点
        fetch_details: 是否抓取热点详情的真实正文内容（默认False，开启后会抓取前3个热点的原文）

    Returns:
        返回JSON字符串，包含：
        - trends_summary: 热点列表，每条包含：
            * content: 标题（真实）
            * author: 来源网站名称（真实）
            * description: 摘要（真实）
            * url: 原文链接（真实）
            * publish_time: 发布时间（真实）
            * rank_score: 热度评分0-1（搜索引擎算法计算，真实）
            * channel: 渠道分类（真实）
            * health_value: 养生价值分析（AI基于真实内容分析，仅供参考）
            * detail_info: 详情内容（可选，fetch_details=True时包含真实正文）
        - suggestions: 基于真实热点的选题建议
        
    关于数据来源的说明：
        ✅ 可以获取（真实数据）：
        - 文章标题、来源网站、发布时间
        - 文章摘要、正文内容（开启详情抓取时）
        - 热度评分（搜索引擎综合排序分）
        
        ❌ 无法获取（技术限制）：
        - 点赞数、转发数、阅读量（平台私有数据）
        - 用户评论（JavaScript动态加载，静态抓取不可用）
    """
    ctx = request_context.get() or new_context(method="fetch_health_trends")

    try:
        # 定义多渠道搜索列表
        channels = {
            "综合搜索": None,  # 不限制网站，全网搜索
            "权威官方": "nhc.gov.cn,chinacdc.cn,people.com.cn,xinhuanet.com",
            "主流媒体": "sohu.com,sina.com.cn,qq.com,163.com,ifeng.com",
            "专业健康": "39.net,99.com.cn,ydyy.cn,jkzx.cn",
            "社交平台": "weibo.com,zhihu.com",
            "生活方式": "xiaohongshu.com,bilibili.com"
        }

        # 搜索养生健康热点
        search_client = SearchClient(ctx=ctx)
        llm_client = LLMClient(ctx=ctx)

        # 构建搜索关键词 - 明确针对中老年人
        if topic_keyword:
            query = f"{topic_keyword} 中老年人 养生 健康 热点"
        else:
            query = "中老年人 养生健康 热点 最新 2025"

        # 执行多渠道搜索
        all_trends = []
        channel_results = {}

        for channel_name, sites in channels.items():
            try:
                search_params = {
                    "query": query,
                    "search_type": "web",
                    "count": 8,
                    "need_summary": True,
                    "time_range": "1w"
                }
                
                # 如果指定了网站，添加 sites 参数
                if sites:
                    search_params["sites"] = sites

                response = search_client.search(**search_params)

                if response.web_items:
                    channel_trends = []
                    for item in response.web_items:
                        trend = {
                            "content": item.title,  # 真实标题
                            "author": item.site_name,  # 真实来源
                            "description": item.snippet,  # 真实摘要
                            "url": item.url,  # 真实URL
                            "publish_time": item.publish_time,  # 真实发布时间
                            "rank_score": item.rank_score,  # 真实热度评分
                            "channel": channel_name,  # 渠道分类
                            "auth_level": getattr(item, 'auth_info_level', None)
                        }
                        channel_trends.append(trend)
                        all_trends.append(trend)

                    channel_results[channel_name] = channel_trends
                    print(f"{channel_name}: 找到 {len(channel_trends)} 条热点")
            except Exception as e:
                print(f"{channel_name} 渠道搜索失败: {str(e)}")
                if channel_name == "综合搜索":
                    continue
                continue

        # 如果没有搜索到任何热点
        if not all_trends:
            return json.dumps({
                "success": False,
                "error": "未找到相关热点内容"
            }, ensure_ascii=False)

        # 按热度排序
        all_trends.sort(key=lambda x: x.get('rank_score', 0), reverse=True)

        # 取前12个热点进行分析
        top_trends = all_trends[:12]

        # 使用LLM分析每个热点的养生价值（基于真实内容分析，非伪造数据）
        trends_with_value = []
        for trend in top_trends:
            try:
                value_prompt = f"""请根据以下真实的热点信息，分析其养生价值。

热点标题：{trend['content']}
来源：{trend['author']}
发布时间：{trend.get('publish_time', '未知')}
内容摘要：{trend['description'][:200]}

请分析并输出JSON格式：
{{
    "health_value": "养生价值简述（50字以内）",
    "target_audience": "主要受众群体"
}}"""

                messages = [
                    SystemMessage(content="你是中老年养生价值分析专家。"),
                    HumanMessage(content=value_prompt)
                ]

                response = llm_client.invoke(
                    messages=messages,
                    model="doubao-seed-2-0-lite-260215",
                    temperature=0.7
                )

                content = response.content
                if isinstance(content, str):
                    content = content.strip()
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()

                value_data = json.loads(content)

                # 添加养生价值到热点数据
                trend["health_value"] = value_data.get("health_value", "")
                trend["target_audience"] = value_data.get("target_audience", "中老年人")

                trends_with_value.append(trend)

            except Exception as e:
                trend["health_value"] = ""
                trend["target_audience"] = "中老年人"
                trends_with_value.append(trend)
                print(f"热点分析失败: {str(e)}")

        # 如果启用详情抓取，获取前3个热点的真实正文内容
        detailed_count = 0
        if fetch_details and trends_with_value:
            print(f"\n开始抓取热点详情（真实正文内容）...")
            
            for i, trend in enumerate(trends_with_value[:3]):  # 只处理前3个以控制耗时
                try:
                    print(f"正在抓取第{i+1}个热点详情: {trend['content'][:30]}...")
                    
                    # 抓取真实URL内容
                    fetch_result = _fetch_url_content(trend['url'], ctx)
                    
                    # 仅存储真实数据
                    detail_info = {
                        "url": trend['url'],
                        "fetch_success": fetch_result['success'],
                        "detail_content": fetch_result.get('content', ''),  # 真实正文
                        "full_title": fetch_result.get('title', ''),  # 真实标题
                        "fetch_error": fetch_result.get('error', '')
                    }
                    
                    trend["detail_info"] = detail_info
                    detailed_count += 1
                    
                    status = "成功" if fetch_result['success'] else "失败"
                    print(f"  ✓ 第{i+1}个热点详情抓取{status}")
                    
                except Exception as e:
                    print(f"  ✗ 第{i+1}个热点详情抓取失败: {str(e)}")
                    trend["detail_info"] = {
                        "url": trend['url'],
                        "fetch_success": False,
                        "error": str(e),
                        "detail_content": "",
                        "full_title": ""
                    }

        # 基于真实热点生成选题建议
        system_prompt = """你是一位专业的中老年养生内容策划师，擅长从多渠道网络热点中挖掘适合中老年人的养生选题。

请根据提供的真实热点列表，给出选题建议。要求：
1. **目标人群**：必须是中老年人（50岁以上），内容要贴近他们的生活实际
2. **选题方向**：慢性病管理、日常保健、饮食调理、运动养生、心理养生等
3. **语言风格**：通俗易懂、接地气，避免专业术语
4. **实用性**：选择日常可操作、成本低的养生方法
5. **时效性**：优先选择近期热点
6. 给出3-5个选题建议
7. 每个选题要说明推荐理由、养生价值点和来源渠道

输出格式（必须是JSON格式）：
{
    "topic_suggestions": [
        {
            "title": "选题标题",
            "reason": "推荐理由（50-100字）",
            "key_points": ["价值点1", "价值点2", "价值点3"],
            "target_audience": "目标人群（必须是中老年人或老年人群体）",
            "source_channels": ["来源渠道1", "来源渠道2"],
            "health_benefits": ["养生价值1", "养生价值2", "养生价值3"]
        }
    ]
}"""

        # 构建热点描述文本（仅使用真实数据）
        trends_text = "\n".join([
            f"{i+1}. 标题：{t['content']}\n   来源：{t['author']}\n   渠道：{t.get('channel', '未知')}\n   热度评分：{t.get('rank_score', 0):.2f}\n   发布时间：{t.get('publish_time', '未知')}\n   描述：{t['description'][:150]}...\n   养生价值：{t.get('health_value', '')}\n"
            for i, t in enumerate(trends_with_value[:10])
        ])

        # 如果有详细信息，也加入上下文（仅真实正文内容）
        if any(t.get('detail_info', {}).get('fetch_success', False) for t in trends_with_value):
            trends_text += "\n\n📝 部分热点的详细正文内容：\n"
            for t in trends_with_value[:3]:
                if t.get('detail_info') and t['detail_info'].get('fetch_success') and t['detail_info'].get('detail_content'):
                    trends_text += f"\n【{t['content'][:20]}】\n"
                    trends_text += f"{t['detail_info']['detail_content'][:500]}...\n"

        # 添加渠道统计信息
        channel_summary = "\n".join([
            f"- {channel}: {len(results)} 条热点"
            for channel, results in channel_results.items()
        ])

        user_message = f"""以下是从多渠道抓取的真实养生健康热点：

📊 渠道统计：
{channel_summary}

🔥 热点列表：
{trends_text}

请根据以上真实热点信息，给出3-5个适合制作养生视频的选题建议。"""

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
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

        suggestions = json.loads(content)

        result_data = {
            "trends_summary": trends_with_value,  # 包含真实数据的汇总
            "suggestions": suggestions.get("topic_suggestions", []),
            "total_trends": len(trends_with_value),
            "channel_results": channel_results,
            "data_source_notes": {
                "real_data_fields": [
                    "content (文章标题)",
                    "author (来源网站)",
                    "description (文章摘要)",
                    "url (原始链接)",
                    "publish_time (发布时间)",
                    "rank_score (热度评分)",
                    "channel (渠道分类)"
                ],
                "optional_real_data": [
                    "detail_content (文章正文，需开启fetch_details参数)",
                    "full_title (完整标题)"
                ],
                "unavailable_fields": [
                    "点赞数/转发数/阅读量（属于各社交平台私有数据，需要官方API授权）",
                    "用户评论（大部分网站采用JavaScript动态加载，静态抓取不可用）"
                ],
                "analysis_fields": [
                    "health_value (养生价值分析，由AI基于真实内容分析生成，供参考)"
                ]
            },
            "has_detailed_content": detailed_count > 0,
            "detailed_count": detailed_count
        }

        message = f"成功从多渠道抓取{len(trends_with_value)}个热点（全部为真实数据），给出{suggestions.get('topic_suggestions', [])}个选题建议"
        if detailed_count > 0:
            message += f"，其中{detailed_count}个热点包含真实正文内容"

        return json.dumps({
            "success": True,
            "data": result_data,
            "message": message
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
