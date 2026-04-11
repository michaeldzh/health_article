"""
网络热点抓取工具（增强版）
抓取网络上的养生健康相关热点，支持：
1. 多渠道并行搜索（综合搜索、权威官方、主流媒体、专业健康、社交平台、生活方式）
2. 热点详情深度抓取
3. AI模拟用户评价和讨论
4. 养生价值分析
5. 选题建议生成

技术说明：
- 点赞数/转发数：由于使用搜索引擎API，无法获取各平台的真实互动数据。
  这些数据属于平台私有数据，需要调用各平台官方API（如微博开放平台、小红书开放平台），
  且大多数平台有严格的反爬机制和API限制。
- 用户评论：大多数现代网站采用JavaScript动态加载评论技术，静态页面抓取难以获取完整评论数据。
  本工具通过两种方式弥补：(1)尝试抓取页面正文内容 (2)基于文章内容AI模拟可能的用户讨论和评价
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import SearchClient, LLMClient, FetchClient
from langchain_core.messages import HumanMessage, SystemMessage
import json


def _fetch_url_content(url: str, ctx) -> dict:
    """
    尝试抓取URL的详细内容
    返回：{success: bool, content: str, title: str, error: str}
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

        # 提取文本内容
        text_content = []
        for item in response.content:
            if item.type == "text":
                text_content.append(item.text)

        full_content = "\n".join(text_content)

        return {
            "success": True,
            "content": full_content[:3000],  # 限制长度避免过长
            "title": response.title or "",
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": "",
            "title": ""
        }


def _generate_simulated_feedback(content: str, title: str, llm_client, ctx) -> list:
    """
    基于文章内容，AI模拟中老年用户的可能反馈和讨论
    """
    try:
        prompt = f"""你是一位资深的中老年养生内容运营专家。请根据以下文章内容，

模拟3-5条中老年人可能会发表的评论或反馈。

要求：
1. 评论者身份：50岁以上的中老年人（退休人员、慢性病患者、养生爱好者等）
2. 评论风格：口语化、接地气、真实感强，像朋友圈或公众号评论区
3. 评论角度：
   - 表示赞同并分享自己经验
   - 提出疑问或困惑
   - 补充其他方法
   - 表达感谢
   - 担忧可行性或安全性
4. 每条评论20-80字
5. 包含情感倾向（正面/中性/担忧）

文章标题：{title}
文章摘要（前500字）：{content[:500]}

输出格式（必须是JSON数组）：
[
    {{
        "user_type": "评论者类型（如：退休阿姨/慢病患者/养生达人等）",
        "comment": "具体评论文本",
        "sentiment": "正面/中性/担忧",
        "theme": "评论主题（如：分享经验/提出疑问/表示感谢等）"
    }}
]"""

        messages = [
            SystemMessage(content="你是中老年用户行为分析专家，擅长模拟真实的中老年用户评论。"),
            HumanMessage(content=prompt)
        ]

        response = llm_client.invoke(
            messages=messages,
            model="doubao-seed-2-0-lite-260215",
            temperature=0.8
        )

        content_str = response.content
        if isinstance(content_str, str):
            content_str = content_str.strip()
            if "```json" in content_str:
                content_str = content_str.split("```json")[1].split("```")[0].strip()
            elif "```" in content_str:
                content_str = content_str.split("```")[1].split("```")[0].strip()

        feedback_list = json.loads(content_str)
        return feedback_list if isinstance(feedback_list, list) else []

    except Exception as e:
        print(f"生成模拟用户反馈失败: {str(e)}")
        return []


@tool
def fetch_health_trends(topic_keyword: str = "", fetch_details: bool = False) -> str:
    """
    抓取网络上的养生健康相关热点，并给出选题建议

    Args:
        topic_keyword: 可选的关键词（如"睡眠"、"减肥"、"秋季养生"等），为空则搜索综合热点
        fetch_details: 是否抓取热点详情和生成模拟用户评价（默认False，开启后会增加耗时）

    Returns:
        返回热点列表和选题建议的JSON字符串，包含：
        - 热点汇总（话题标题、来源渠道、热度评分、发布时间、养生价值、受众群体）
        - 热点详情（可选，包含正文内容和模拟用户评价）
        - 选题建议（推荐理由、核心内容、健康益处、来源渠道）

    关于点赞数/转发数的说明：
        由于技术限制（搜索引擎API无法获取社交平台的私有互动数据），当前无法提供真实的点赞数和转发数。
        但提供以下替代指标：
        1. 热度评分（rank_score，0-1范围）：基于搜索引擎的综合热度算法
        2. 养生价值评分（health_value）：AI分析的养生实用价值
        3. 可操作性评估（actionable）：是否适合制作成视频内容
        4. 模拟用户评价（可选）：AI基于内容生成的可能讨论方向
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
                            "content": item.title,
                            "author": item.site_name,
                            "description": item.snippet,
                            "url": item.url,
                            "publish_time": item.publish_time,
                            "rank_score": item.rank_score,
                            "channel": channel_name,
                            "auth_level": getattr(item, 'auth_info_level', None)
                        }
                        channel_trends.append(trend)
                        all_trends.append(trend)

                    channel_results[channel_name] = channel_trends
                    print(f"{channel_name}: 找到 {len(channel_trends)} 条热点")
            except Exception as e:
                print(f"{channel_name} 渠道搜索失败: {str(e)}")
                # 如果是综合搜索失败，则直接跳过
                if channel_name == "综合搜索":
                    continue
                # 其他渠道失败，继续尝试其他渠道
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

        # 步骤1：使用LLM分析每个热点的养生价值
        trends_with_value = []
        for trend in top_trends:
            try:
                # 分析单个热点的养生价值
                value_prompt = f"""请分析以下健康热点对中老年人的养生价值。

热点标题：{trend['content']}
来源：{trend['author']}
发布时间：{trend.get('publish_time', '未知')}
内容摘要：{trend['description'][:200]}

请分析并输出（必须是JSON格式）：
{{
    "health_value": "这个热点对中老年人的养生价值分析（50字以内）",
    "target_audience": "主要受众群体",
    "actionable": "是否可操作（是/否）",
    "engagement_prediction": "预测该话题在中老年群体的讨论热度（高/中/低）及原因（30字以内）"
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
                trend["actionable"] = value_data.get("actionable", "是")
                trend["engagement_prediction"] = value_data.get("engagement_prediction", "")

                trends_with_value.append(trend)

            except Exception as e:
                # 如果分析失败，添加默认值
                trend["health_value"] = "养生待分析"
                trend["target_audience"] = "中老年人"
                trend["actionable"] = "是"
                trend["engagement_prediction"] = ""
                trends_with_value.append(trend)
                print(f"热点分析失败: {str(e)}")

        # 步骤2（可选）：如果启用详情抓取，获取前3个热点的详细内容和模拟用户评价
        detailed_trends = []
        if fetch_details and trends_with_value:
            print(f"\n开始抓取热点详情和生成模拟用户评价...")
            
            for i, trend in enumerate(trends_with_value[:3]):  # 只处理前3个以控制耗时
                try:
                    print(f"正在处理第{i+1}个热点: {trend['content'][:30]}...")
                    
                    # 2a. 抓取URL详细内容
                    fetch_result = _fetch_url_content(trend['url'], ctx)
                    
                    detail_info = {
                        "url": trend['url'],
                        "fetch_success": fetch_result['success'],
                        "detail_content": fetch_result.get('content', '')[:1000],  # 截取前1000字作为预览
                        "full_title": fetch_result.get('title', ''),
                        "fetch_error": fetch_result.get('error', '')
                    }
                    
                    # 2b. 基于内容生成模拟用户评价
                    simulated_feedback = []
                    if fetch_result['success'] and fetch_result['content']:
                        simulated_feedback = _generate_simulated_feedback(
                            content=fetch_result['content'],
                            title=trend['content'],
                            llm_client=llm_client,
                            ctx=ctx
                        )
                    
                    detail_info["simulated_user_feedback"] = simulated_feedback
                    
                    # 将详情信息合并到热点数据中
                    trend["detail_info"] = detail_info
                    detailed_trends.append(trend)
                    
                    print(f"  ✓ 详情获取完成，生成{len(simulated_feedback)}条模拟用户评价")
                    
                except Exception as e:
                    print(f"  ✗ 详情获取失败: {str(e)}")
                    trend["detail_info"] = {
                        "url": trend['url'],
                        "fetch_success": False,
                        "error": str(e),
                        "simulated_user_feedback": []
                    }
                    detailed_trends.append(trend)

        # 步骤3：基于热点养生价值生成选题建议
        system_prompt = """你是一位专业的中老年养生内容策划师，擅长从多渠道网络热点中挖掘适合中老年人的养生选题。

请根据提供的热点列表，分析并给出选题建议。要求：
1. **目标人群**：必须是中老年人（50岁以上），内容要贴近他们的生活实际
2. **选题方向**：慢性病管理、日常保健、饮食调理、运动养生、心理养生等
3. **语言风格**：通俗易懂、接地气，避免专业术语，要有亲切感
4. **实用性**：选择日常可操作、成本低的养生方法，避免过度养生
5. **时效性**：优先选择近期热点和热议话题
6. 给出3-5个选题建议
7. 每个选题要说明推荐理由、养生价值点和热点来源渠道
8. 考虑用户的讨论热情度，选择容易引发共鸣的话题

输出格式（必须是JSON格式）：
{
    "topic_suggestions": [
        {
            "title": "选题标题",
            "reason": "推荐理由（50-100字）",
            "key_points": ["价值点1", "value点2", "value点3"],
            "target_audience": "目标人群（必须是中老年人或老年人群体）",
            "source_channels": ["来源渠道1", "来源渠道2"],
            "health_benefits": ["养生价值1", "养生价值2", "养生价值3"],
            "expected_engagement": "预期的用户参与度和讨论方向"
        }
    ]
}"""

        # 构建热点描述文本
        trends_text = "\n".join([
            f"{i+1}. 标题：{t['content']}\n   来源：{t['author']}\n   渠道：{t.get('channel', '未知')}\n   热度评分：{t.get('rank_score', 0):.2f}\n   养生价值：{t.get('health_value', '')}\n   受众：{t.get('target_audience', '')}\n   可操作性：{t.get('actionable', '')}\n   预期讨论热度：{t.get('engagement_prediction', '未知')}\n   描述：{t['description'][:100]}...\n"
            for i, t in enumerate(trends_with_value[:10])
        ])

        # 如果有详细信息，也加入上下文
        if detailed_trends:
            trends_text += "\n\n📝 部分热点的详细信息和用户反馈：\n"
            for t in detailed_trends:
                if t.get('detail_info') and t['detail_info'].get('simulated_user_feedback'):
                    trends_text += f"\n【{t['content'][:20]}】模拟用户评论：\n"
                    for feedback in t['detail_info']['simulated_user_feedback'][:3]:
                        trends_text += f"  - [{feedback.get('user_type', '')}] ({feedback.get('sentiment', '')}) {feedback.get('comment', '')}\n"

        # 添加渠道统计信息
        channel_summary = "\n".join([
            f"- {channel}: {len(results)} 条热点"
            for channel, results in channel_results.items()
        ])

        user_message = f"""以下是从多渠道抓取的养生健康热点：

📊 渠道统计：
{channel_summary}

🔥 热点列表：
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

        result_data = {
            "trends_summary": trends_with_value,  # 包含养生价值的热点汇总
            "suggestions": suggestions.get("topic_suggestions", []),
            "total_trends": len(trends_with_value),
            "channel_results": channel_results,
            "technical_notes": {
                "likes_shares_unavailable": "由于使用搜索引擎API，无法获取真实的点赞数/转发数。这些数据属于各社交平台的私有数据，需要平台授权的API才能访问。",
                "alternative_metrics": {
                    "rank_score": "搜索引擎热度评分（0-1），综合考虑了内容质量、时效性、权威性等因素",
                    "engagement_prediction": "AI预测的话题讨论热度（高/中/低），基于内容特征和历史规律",
                    "simulated_feedback": "如果启用详情抓取，会基于文章内容模拟中老年用户的可能评论和反馈"
                },
                "user_comments_status": "大部分网站采用JavaScript动态加载评论，静态抓取难以获取。通过AI模拟用户评价作为替代方案。",
                "how_to_get_real_metrics": "如需真实数据，可考虑：1.申请各平台开放平台API权限 2.使用第三方数据服务商（如新榜、清博指数） 3.手动查看并记录"
            },
            "has_detailed_info": len(detailed_trends) > 0,
            "detailed_count": len(detailed_trends)
        }

        message = f"成功从多渠道抓取{len(trends_with_value)}个热点，并给出{suggestions.get('topic_suggestions', [])}个选题建议"
        if detailed_trends:
            message += f"，其中{len(detailed_trends)}个热点包含详细内容和模拟用户评价"

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
