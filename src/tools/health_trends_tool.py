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
        llm_client = LLMClient(ctx=ctx)

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
    "actionable": "是否可操作（是/否）"
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

                trends_with_value.append(trend)

            except Exception as e:
                # 如果分析失败，添加默认值
                trend["health_value"] = "养生待分析"
                trend["target_audience"] = "中老年人"
                trend["actionable"] = "是"
                trends_with_value.append(trend)
                print(f"热点分析失败: {str(e)}")

        # 步骤2：基于热点养生价值生成选题建议
        system_prompt = """你是一位专业的中老年养生内容策划师，擅长从多渠道网络热点中挖掘适合中老年人的养生选题。

请根据提供的热点列表，分析并给出选题建议。要求：
1. **目标人群**：必须是中老年人（50岁以上），内容要贴近他们的生活实际
2. **选题方向**：慢性病管理、日常保健、饮食调理、运动养生、心理养生等
3. **语言风格**：通俗易懂、接地气，避免专业术语，要有亲切感
4. **实用性**：选择日常可操作、成本低的养生方法，避免过度养生
5. **时效性**：优先选择近期热点和热议话题
6. 给出3-5个选题建议
7. 每个选题要说明推荐理由、养生价值点和热点来源渠道

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

        # 构建热点描述文本
        trends_text = "\n".join([
            f"{i+1}. 标题：{t['content']}\n   来源：{t['author']}\n   渠道：{t.get('channel', '未知')}\n   养生价值：{t.get('health_value', '')}\n   受众：{t.get('target_audience', '')}\n   描述：{t['description'][:100]}...\n"
            for i, t in enumerate(trends_with_value[:10])
        ])

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

        return json.dumps({
            "success": True,
            "data": {
                "trends_summary": trends_with_value,  # 包含养生价值的热点汇总
                "suggestions": suggestions.get("topic_suggestions", []),
                "total_trends": len(trends_with_value),
                "channel_results": channel_results
            },
            "message": f"成功从多渠道抓取{len(trends_with_value)}个热点，并给出{suggestions.get('topic_suggestions', len([]))}个选题建议"
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
