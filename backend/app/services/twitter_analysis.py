"""指定 Twitter 用户分析服务：拉取文章 → LLM 分析 → 返回分析报告。

只使用该用户发布的文章（articles）类型内容进行分析，不使用媒体推文（media）。
"""
import logging

from app.config import get_settings
from app.services.llm.client import create_llm_client
from app.services.providers.twitter import twitter_provider

logger = logging.getLogger(__name__)

_ANALYSIS_PROMPT = """你是一个专业的财经分析师。请基于以下指定用户发布的最新文章内容，撰写一份中文分析报告。

分析要求：
1. 总结该用户近期的核心观点和主题
2. 提取涉及的具体投资方向、板块或个股
3. 评估其观点的逻辑链条和依据
4. 指出观点的倾向性（看多/看空/中性）及置信度
5. 给出你对这些观点的独立评价

请用 Markdown 格式输出，结构清晰。"""


def analyze_twitter_user(username: str, max_articles: int = 20) -> dict:
    """拉取指定 Twitter 用户发布的文章并调用 LLM 分析。

    仅拉取用户发布的文章（articles），不包含媒体推文（media），
    文章通常包含更完整的观点和逻辑。不使用 iwencai 相关服务。

    Param:
        username: Twitter 用户名（不含 @）
        max_articles: 最多分析的文章数
    Return:
        包含 username、article_count、articles 和 analysis 字段的字典
    """
    logger.info(f"开始分析 Twitter 用户文章: @{username}")

    # 1. 仅拉取该用户的文章（articles），不使用 media
    articles = twitter_provider.fetch_user_articles_raw(username)
    if not articles:
        logger.warning(f"Twitter 用户无可用文章: @{username}")
        return {
            "username": username,
            "article_count": 0,
            "articles": [],
            "analysis": f"用户 @{username} 暂无已发布的文章数据，请检查用户名是否正确。",
        }

    # 2. 准备 LLM 输入
    article_texts = []
    for a in articles[:max_articles]:
        text = f"- [{a.get('publish_time', '')}] {a.get('title', '')}\n  内容摘要：{a.get('content', '')[:500]}"
        article_texts.append(text)

    articles_data = "\n\n".join(article_texts)
    user_message = f"Twitter 用户 @{username} 的最新 {len(articles)} 篇文章：\n\n{articles_data}"

    # 3. 调用 LLM 分析
    try:
        client = create_llm_client()
        analysis = client.chat(
            messages=[
                {"role": "system", "content": _ANALYSIS_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
        )
        logger.info(f"Twitter 用户文章分析完成: @{username}, 分析长度={len(analysis)}")
    except Exception as e:
        logger.error(f"Twitter 用户文章分析 LLM 调用失败: {e}", exc_info=True)
        analysis = f"AI 分析生成失败: {e}"

    return {
        "username": username,
        "article_count": len(articles),
        "articles": [
            {
                "title": a.get("title", ""),
                "content": a.get("content", "")[:500],
                "publish_time": str(a.get("publish_time", "")),
                "url": a.get("url", ""),
            }
            for a in articles[:max_articles]
        ],
        "analysis": analysis,
    }
