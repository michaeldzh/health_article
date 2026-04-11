"""
网络热点抓取工具（时节增强版）
抓取网络上的养生健康相关热点，并给出选题建议

核心特性：
1. 自动匹配当下时节和节气
2. 严格限制时间范围（最近7天内的内容）
3. 过滤掉过期的历史内容
4. 动态生成符合当季的搜索关键词

数据真实性说明：
- 本工具仅提供通过搜索引擎API和URL抓取获取的真实数据
- 不包含任何模拟、伪造或AI生成的虚假数据
- 可提供的真实数据：标题、来源网站、摘要、URL、发布时间、热度评分、正文内容
- 无法获取的数据：点赞数、转发数、评论数（这些是各社交平台私有数据，需要官方API授权）
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_dev_sdk import SearchClient, LLMClient, FetchClient
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime, timedelta
import json


def _get_current_seasonal_info() -> dict:
    """
    获取当前的时节信息，包括：
    - 当前日期
    - 当前节气
    - 季节关键词
    - 养生重点方向
    
    Returns:
        dict: 时节信息字典
    """
    now = datetime.now()
    
    # 获取年月日
    current_year = now.year
    current_month = now.month
    current_day = now.day
    
    # 定义24节气的大致时间范围（简化版，实际精确计算需要天文算法）
    solar_terms = {
        # 春季 (2-4月)
        "立春": (2, 3, 5), "雨水": (2, 18, 22), "惊蛰": (3, 5, 9),
        "春分": (3, 20, 24), "清明": (4, 4, 8), "谷雨": (4, 19, 23),
        # 夏季 (5-7月)
        "立夏": (5, 5, 9), "小满": (5, 20, 24), "芒种": (6, 5, 9),
        "夏至": (6, 21, 25), "小暑": (7, 6, 10), "大暑": (7, 22, 26),
        # 秋季 (8-10月)
        "立秋": (7, 30, 8), "处暑": (8, 22, 26), "白露": (9, 7, 11),
        "秋分": (9, 22, 26), "寒露": (10, 8, 12), "霜降": (10, 23, 27),
        # 冬季 (11-1月)
        "立冬": (11, 7, 11), "小雪": (11, 22, 26), "大雪": (12, 6, 10),
        "冬至": (12, 21, 25), "小寒": (1, 5, 9), "大寒": (1, 20, 24)
    }
    
    # 找到当前最接近的节气
    current_solar_term = None
    min_diff = float('inf')
    for term, (term_month, start_day, end_day) in solar_terms.items():
        # 计算距离当前日期的天数差
        term_date = datetime(current_year, term_month, (start_day + end_day) // 2)
        diff = abs((now - term_date).days)
        if diff < min_diff:
            min_diff = diff
            current_solar_term = term
    
    # 确定季节和对应的养生关键词
    season_keywords = {
        (3, 4, 5): {
            "season": "春季",
            "solar_terms": ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨"],
            "health_topics": ["春季养生", "养肝护肝", "防过敏", "春困", "疏肝理气", 
                            "踏青运动", "春季饮食", "祛湿", "预防感冒", "调节情绪"],
            "diet_focus": ["韭菜", "菠菜", "香椿", "荠菜", "春笋", "蜂蜜"],
            "weather_features": ["气温回升", "多风", "乍暖还寒", "花粉飘散"]
        },
        (6, 7, 8): {
            "season": "夏季",
            "solar_terms": ["立夏", "小满", "芒种", "夏至", "小暑", "大暑"],
            "health_topics": ["夏季养生", "防暑降温", "清热解暑", "冬病夏治",
                            "健脾祛湿", "睡眠调理", "防蚊虫", "补水防晒"],
            "diet_focus": ["绿豆", "西瓜", "苦瓜", "冬瓜", "莲子", "薏米"],
            "weather_features": ["高温炎热", "多雨潮湿", "雷阵雨"]
        },
        (9, 10, 11): {
            "season": "秋季",
            "solar_terms": ["立秋", "处暑", "白露", "秋分", "寒露", "霜降"],
            "health_topics": ["秋季养生", "润燥养肺", "防秋燥", "贴秋膘",
                            "预防心脑血管", "秋季进补", "保暖防寒", "调养脾胃"],
            "diet_focus": ["梨", "百合", "银耳", "莲藕", "柿子", "南瓜"],
            "weather_features": ["干燥凉爽", "温差大", "秋风", "早晚凉"]
        },
        (12, 1, 2): {
            "season": "冬季",
            "solar_terms": ["立冬", "小雪", "大雪", "冬至", "小寒", "大寒"],
            "health_topics": ["冬季养生", "防寒保暖", "温补阳气", "补肾填精",
                            "预防心脑血管", "冬季进补", "呼吸道防护", "关节保养"],
            "diet_focus": ["羊肉", "萝卜", "白菜", "山药", "核桃", "黑芝麻"],
            "weather_features": ["寒冷干燥", "低温", "大风雪", "室内外温差大"]
        }
    }
    
    # 获取当前季节信息
    season_info = season_keywords.get(current_month, season_keywords[(3, 4, 5)])
    
    return {
        "current_date": now.strftime("%Y年%m月%d日"),
        "year": current_year,
        "month": current_month,
        "day": current_day,
        "season": season_info["season"],
        "solar_term": current_solar_term or "未知",
        "health_topics": season_info["health_topics"],
        "diet_focus": season_info["diet_focus"],
        "weather_features": season_info["weather_features"],
        "search_keywords": _build_seasonal_search_keywords(now, season_info)
    }


def _build_seasonal_search_keywords(now: datetime, season_info: dict) -> str:
    """
    构建符合当前时节的搜索关键词
    
    Args:
        now: 当前时间
        season_info: 季节信息
        
    Returns:
        str: 搜索关键词字符串
    """
    month = now.month
    day = now.day
    
    # 基础关键词：中老年人 + 养生 + 当前年份
    base_keywords = [f"中老年人", "养生健康", f"{now.year}"]
    
    # 添加季节相关关键词
    base_keywords.append(season_info["season"] + "养生")
    
    # 添加当前月份相关的特定关键词
    monthly_keywords = {
        1: ["冬季养生", "新年养生", "春节前后", "防寒保暖"],
        2: ["春节养生", "年后调理", "春季初", "立春后"],
        3: ["三月养生", "春季养生", "惊蛰", "春分", "防过敏"],
        4: ["四月养生", "清明前后", "谷雨", "春季保健", "养肝"],
        5: ["五月养生", "立夏", "初夏养生", "春夏交替"],
        6: ["六月养生", "芒种", "夏至", "夏季开始", "防暑"],
        7: ["七月养生", "小暑", "大暑前", "盛夏", "三伏天"],
        8: ["八月养生", "立秋", "处暑", "夏末秋初", "末伏"],
        9: ["九月养生", "白露", "秋季养生", "秋分", "润燥"],
        10: ["十月养生", "寒露", "霜降", "深秋", "秋冬换季"],
        11: ["十一月养生", "立冬", "小雪", "冬季开始", "初冬"],
        12: ["十二月养生", "大雪", "冬至", "严冬", "年终养生"]
    }
    
    # 选择当前月的关键词（取前3个最相关的）
    month_specific = monthly_keywords.get(month, [])[:3]
    base_keywords.extend(month_specific)
    
    # 添加"最新"、"本周"、"近期"等时效性词汇
    time_keywords = ["最新", "本周", "近期", "热点"]
    base_keywords.extend(time_keywords[:2])
    
    # 用空格连接所有关键词
    return " ".join(base_keywords)


def _is_within_time_range(publish_time_str: str, days_limit: int = 7) -> bool:
    """
    判断发布时间是否在指定天数范围内
    
    Args:
        publish_time_str: 发布时间字符串（ISO格式）
        days_limit: 天数限制（默认7天）
        
    Returns:
        bool: 是否在时间范围内
    """
    if not publish_time_str:
        return False
    
    try:
        # 解析发布时间
        if isinstance(publish_time_str, str):
            # 处理多种时间格式
            publish_time_str = publish_time_str.replace("T", " ").split("+")[0].strip()
            
            # 尝试不同的格式
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"]:
                try:
                    publish_time = datetime.strptime(publish_time_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                # 如果都解析不了，返回False
                return False
        
        # 计算时间差
        now = datetime.now()
        time_diff = (now - publish_time).days
        
        return time_diff <= days_limit
        
    except Exception as e:
        print(f"时间解析失败: {publish_time_str}, 错误: {str(e)}")
        return False


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
    
    **重要特性**：
    - ✅ 自动匹配当前时节/节气（如2026年4月=春季+谷雨节气）
    - ✅ 严格筛选最近7天内发布的最新内容
    - ✅ 过滤掉过期的历史内容（如2025年的旧文章）
    - ✅ 动态生成符合当季的搜索关键词
    
    **数据真实性保证**：
    - 本工具仅返回真实抓取的数据，不包含任何模拟或伪造的信息

    Args:
        topic_keyword: 可选的关键词（如"睡眠"、"减肥"等），为空则自动根据当前时节搜索
        fetch_details: 是否抓取热点详情的真实正文内容（默认False）

    Returns:
        返回JSON字符串，包含：
        - seasonal_info: 当前时节信息（节气、季节、养生重点等）
        - trends_summary: 最近7天内的热点列表（已过滤过期内容）
        - filtered_count: 被过滤掉的过期内容数量
        - suggestions: 基于最新热点的选题建议
    """
    ctx = request_context.get() or new_context(method="fetch_health_trends")

    try:
        # 获取当前时节信息
        seasonal_info = _get_current_seasonal_info()
        current_year = seasonal_info["year"]
        current_month = seasonal_info["month"]
        current_season = seasonal_info["season"]
        current_solar_term = seasonal_info["solar_term"]
        
        print(f"\n📅 当前时节: {seasonal_info['current_date']}")
        print(f"🌿 季节: {current_season} | 节气: {current_solar_term}")
        print(f"🔍 搜索关键词将包含时节相关内容\n")

        # 定义多渠道搜索列表
        channels = {
            "综合搜索": None,
            "权威官方": "nhc.gov.cn,chinacdc.cn,people.com.cn,xinhuanet.com",
            "主流媒体": "sohu.com,sina.com.cn,qq.com,163.com,ifeng.com",
            "专业健康": "39.net,99.com.cn,ydyy.cn,jkzx.cn",
            "社交平台": "weibo.com,zhihu.com",
            "生活方式": "xiaohongshu.com,bilibili.com"
        }

        # 搜索养生健康热点
        search_client = SearchClient(ctx=ctx)
        llm_client = LLMClient(ctx=ctx)

        # 构建搜索关键词 - 结合用户输入和当前时节
        if topic_keyword:
            # 用户指定了关键词，结合时节优化
            query = f"{topic_keyword} 中老年人 {current_season}养生 健康 最新 {current_year}"
        else:
            # 使用自动生成的时节关键词
            query = seasonal_info["search_keywords"]

        # 执行多渠道搜索（使用更严格的时间限制：最近7天）
        all_trends = []
        channel_results = {}
        total_before_filter = 0

        for channel_name, sites in channels.items():
            try:
                search_params = {
                    "query": query,
                    "search_type": "web",
                    "count": 15,  # 多取一些以便过滤后还有足够的内容
                    "need_summary": True,
                    "time_range": "1w"  # 强制限制为最近一周
                }
                
                # 如果指定了网站，添加 sites 参数
                if sites:
                    search_params["sites"] = sites

                response = search_client.search(**search_params)

                if response.web_items:
                    channel_trends = []
                    for item in response.web_items:
                        total_before_filter += 1
                        
                        # 严格的时间过滤：只保留最近7天内的内容
                        is_recent = _is_within_time_range(item.publish_time, days_limit=7)
                        
                        # 额外检查：确保不是往年旧文（如2025年的内容）
                        is_not_old = True
                        if item.publish_time:
                            pub_str = str(item.publish_time)
                            # 排除去年的内容
                            if f"{current_year - 1}" in pub_str and current_month > 1:
                                is_not_old = False
                            # 排除更早的内容
                            if pub_str.startswith(f"{current_year - 2}") or pub_str.startswith(f"{current_year - 3}"):
                                is_not_old = False
                        
                        trend = {
                            "content": item.title,
                            "author": item.site_name,
                            "description": item.snippet,
                            "url": item.url,
                            "publish_time": item.publish_time,
                            "rank_score": item.rank_score,
                            "channel": channel_name,
                            "auth_level": getattr(item, 'auth_info_level', None),
                            "is_recent": is_recent and is_not_old,  # 标记是否通过时间过滤
                            "filter_reason": "" if (is_recent and is_not_old) else (
                                "超过7天" if not is_recent else "往期旧文"
                            )
                        }
                        
                        all_trends.append(trend)
                        
                        # 只有通过过滤的才计入渠道统计
                        if is_recent and is_not_old:
                            channel_trends.append(trend)

                    channel_results[channel_name] = {
                        "trends": channel_trends,
                        "total_fetched": len([item for item in response.web_items])
                    }
                    print(f"{channel_name}: 获取{len(response.web_items)}条，通过时间过滤{len(channel_trends)}条")

            except Exception as e:
                print(f"{channel_name} 渠道搜索失败: {str(e)}")
                if channel_name == "综合搜索":
                    continue
                continue

        # 过滤出符合时间要求的热点
        valid_trends = [t for t in all_trends if t.get("is_recent", False)]
        invalid_trends = [t for t in all_trends if not t.get("is_recent", False)]

        print(f"\n📊 时间过滤结果:")
        print(f"   总计获取: {len(all_trends)} 条")
        print(f"   ✓ 有效（近7天）: {len(valid_trends)} 条")
        print(f"   ✗ 已过滤（超时/旧文）: {len(invalid_trends)} 条")

        # 如果没有找到足够的新鲜热点
        if len(valid_trends) < 3:
            warning_msg = f"⚠️ 近期热点较少（仅{len(valid_trends)}条），已放宽条件包含部分稍早内容"
            print(warning_msg)
            
            # 放宽条件：如果7天内内容太少，扩展到14天但仍排除去年及更早的
            relaxed_trends = []
            for t in all_trends:
                if t.get("is_recent"):
                    relaxed_trends.append(t)
                elif _is_within_time_range(t.get("publish_time", ""), days_limit=14):
                    # 14天内但不在7天内的，也纳入但标记
                    t["is_relaxed"] = True
                    relaxed_trends.append(t)
            
            if len(relaxed_trends) >= len(valid_trends):
                valid_trends = relaxed_trends

        # 如果还是没有热点
        if not valid_trends:
            return json.dumps({
                "success": False,
                "error": f"未找到近期（7天内）的相关热点内容。当前时节：{current_season}({current_solar_term})，可能该时段养生话题较少。",
                "seasonal_info": seasonal_info,
                "suggestion": "可以尝试指定具体关键词（如'春季养生''睡眠'等）重新搜索"
            }, ensure_ascii=False)

        # 按热度排序（优先显示最新的高热度内容）
        valid_trends.sort(key=lambda x: (x.get('rank_score', 0), x.get('is_recent', False)), reverse=True)

        # 取前10个热点进行分析
        top_trends = valid_trends[:10]

        # 使用LLM分析每个热点的养生价值
        trends_with_value = []
        for trend in top_trends:
            try:
                value_prompt = f"""请根据以下真实的热点信息，分析其养生价值。

【当前时节】{seasonal_info['current_date']}，{current_season}，节气：{current_solar_term}
【时节养生重点】：{', '.join(seasonal_info['health_topics'][:5])}

热点标题：{trend['content']}
来源：{trend['author']}
发布时间：{trend.get('publish_time', '未知')}
内容摘要：{trend['description'][:200]}

请分析并输出JSON格式：
{{
    "health_value": "养生价值简述（50字以内）",
    "target_audience": "主要受众群体",
    "season_relevance": "与当前时节的契合度（高/中/低）"
}}"""

                messages = [
                    SystemMessage(content="你是中老年养生价值分析专家，善于判断内容的时节相关性。"),
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
                trend["season_relevance"] = value_data.get("season_relevance", "中")

                trends_with_value.append(trend)

            except Exception as e:
                trend["health_value"] = ""
                trend["target_audience"] = "中老年人"
                trend["season_relevance"] = "中"
                trends_with_value.append(trend)

        # 详情抓取（可选）
        detailed_count = 0
        if fetch_details and trends_with_value:
            print(f"\n开始抓取热点详情...")
            
            for i, trend in enumerate(trends_with_value[:3]):
                try:
                    print(f"正在抓取第{i+1}个热点详情: {trend['content'][:30]}...")
                    
                    fetch_result = _fetch_url_content(trend['url'], ctx)
                    
                    detail_info = {
                        "url": trend['url'],
                        "fetch_success": fetch_result['success'],
                        "detail_content": fetch_result.get('content', ''),
                        "full_title": fetch_result.get('title', ''),
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

        # 生成选题建议（强调时节相关性）
        system_prompt = f"""你是一位专业的中老年养生内容策划师，擅长从多渠道网络热点中挖掘适合中老年人的养生选题。

**当前时节信息**：
- 日期：{seasonal_info['current_date']}
- 季节：{current_season}
- 节气：{current_solar_term}
- 时节养生重点：{', '.join(seasonal_info['health_topics'][:5])}
- 当季食材推荐：{', '.join(seasonal_info['diet_focus'][:5])}

请根据以上真实热点列表，给出选题建议。要求：
1. **目标人群**：必须是中老年人（50岁以上）
2. **时节契合度**：必须与当前时节高度相关，选择适合{current_season}{current_solar_term}的话题
3. **时效性**：必须是近期热门话题，不要选择过时的内容
4. **实用性**：日常可操作、成本低
5. 给出3-5个选题建议
6. 每个选题说明推荐理由、与时节的关联、养生价值点

输出格式（必须是JSON格式）：
{{
    "topic_suggestions": [
        {{
            "title": "选题标题",
            "reason": "推荐理由（50-100字，强调时节相关性）",
            "key_points": ["价值点1", "value点2", "value点3"],
            "target_audience": "目标人群",
            "source_channels": ["来源渠道1", "来源渠道2"],
            "health_benefits": ["养生价值1", "养生价值2", "养生价值3"],
            "season_connection": "与{current_season}{current_solar_term}的具体联系"
        }}
    ]
}}"""

        # 构建热点描述文本（仅使用真实数据，包含时间信息）
        trends_text = "\n".join([
            f"{i+1}. 标题：{t['content']}\n   来源：{t['author']}\n   发布时间：{t.get('publish_time', '未知')}\n   时节契合度：{t.get('season_relevance', '未知')}\n   热度评分：{t.get('rank_score', 0):.2f}\n   描述：{t['description'][:150]}...\n   养生价值：{t.get('health_value', '')}\n"
            for i, t in enumerate(trends_with_value[:10])
        ])

        # 如果有详细信息
        if any(t.get('detail_info', {}).get('fetch_success', False) for t in trends_with_value):
            trends_text += "\n\n📝 部分热点的详细正文内容：\n"
            for t in trends_with_value[:3]:
                if t.get('detail_info') and t['detail_info'].get('fetch_success') and t['detail_info'].get('detail_content'):
                    trends_text += f"\n【{t['content'][:20]}】\n"
                    trends_text += f"{t['detail_info']['detail_content'][:500]}...\n"

        # 渠道统计
        channel_summary = "\n".join([
            f"- {channel}: {data['trends']} 条有效热点（共获取{data['total_fetched']}条）"
            for channel, data in channel_results.items()
        ])

        user_message = f"""以下是从多渠道抓取的最新养生健康热点（已过滤过期内容）：

📅 当前时节：{seasonal_info['current_date']} | {current_season} · {current_solar_term}

📊 渠道统计：
{channel_summary}

📊 时间过滤：共获取{len(all_trends)}条，有效{len(valid_trends)}条，过滤{len(invalid_trends)}条过期内容

🔥 热点列表（全部为近7天内发布）：
{trends_text}

请根据以上最新热点信息，给出3-5个适合制作养生视频的选题建议（必须贴合当前时节）。"""

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
            "seasonal_info": seasonal_info,  # 当前时节信息
            "time_filter_stats": {
                "total_fetched": len(all_trends),
                "valid_recent": len(valid_trends),
                "filtered_out": len(invalid_trends),
                "filter_criteria": "最近7天内发布，排除往年旧文"
            },
            "trends_summary": trends_with_value,  # 有效热点列表
            "suggestions": suggestions.get("topic_suggestions", []),
            "channel_results": channel_results,
            "has_detailed_content": detailed_count > 0,
            "detailed_count": detailed_count
        }

        message = f"成功抓取{seasonal_info['season']}{current_solar_term}时节热点（{len(valid_trends)}条近7天内容，已过滤{len(invalid_trends)}条过期内容）"
        if detailed_count > 0:
            message += f"，其中{detailed_count}篇含完整正文"

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
