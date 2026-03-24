#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
医学文献自动化助手 - 多领域版本
Medical Literature Automation Assistant - Multi-Domain Version
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('literature_assistant.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== 配置区域 ====================

# API密钥配置
DEEPSEEK_API_KEY =  # DeepSeek API密钥
SERPER_API_KEY =      # Serper API密钥

# DeepSeek API配置
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# Serper API配置
SERPER_API_URL = "https://google.serper.dev/search"

# PubMed API配置
PUBMED_API_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# 检索模式配置
SEARCH_MODE = "pubmed"  # 可选: "serper" 或 "pubmed"

# 顶级期刊列表
TOP_JOURNALS = [
    "Journal of Clinical Oncology",
    "JCO",
    "Lancet Oncology",
    "Journal of Heart and Lung Transplantation",
    "JHLT",
    "New England Journal of Medicine",
    "NEJM",
    "Lancet",
    "JAMA",
    "BMJ"
]

# ==================== 三大研究领域配置 ====================

# 肺癌领域关键词
LUNG_CANCER_KEYWORDS = [
    "lung cancer robotic surgery",
    "lung cancer ablation",
    "lung cancer targeted therapy",
    "lung cancer immunotherapy",
    "lung cancer bispecific antibody",
    "lung cancer ADC",
    "lung cancer minimally invasive surgery",
    "lung cancer SBRT",
    "肺癌机器人手术",
    "肺癌消融",
    "肺癌靶向治疗",
    "肺癌免疫治疗",
    "肺癌双抗",
    "肺癌ADC药物"
]

# 肺移植领域关键词
LUNG_TRANSPLANT_KEYWORDS = [
    "lung transplantation minimally invasive surgery",
    "lung transplantation perioperative management",
    "lung transplant ECMO",
    "lung transplant rejection",
    "lung transplant infection",
    "肺移植微创手术",
    "肺移植围术期管理",
    "肺移植ECMO",
    "肺移植排异"
]

# 胸交感神经切除领域关键词
THORACIC_SYMPATHECTOMY_KEYWORDS = [
    "thoracic sympathectomy hyperhidrosis",
    "thoracic sympathectomy arrhythmia",
    "endoscopic thoracic sympathectomy",
    "ETS palmar hyperhidrosis",
    "thoracic sympathetic denervation",
    "胸交感神经切除",
    "手汗症ETS",
    "胸交感神经切断"
]

# 研究领域定义
RESEARCH_DOMAINS = {
    "lung_cancer": {
        "name": "肺癌领域",
        "keywords": LUNG_CANCER_KEYWORDS,
        "top_n_per_keyword": 3
    },
    "lung_transplant": {
        "name": "肺移植领域",
        "keywords": LUNG_TRANSPLANT_KEYWORDS,
        "top_n_per_keyword": 3
    },
    "thoracic_sympathectomy": {
        "name": "胸交感神经切除领域",
        "keywords": THORACIC_SYMPATHECTOMY_KEYWORDS,
        "top_n_per_keyword": 3
    }
}

# 历史对话存储文件
HISTORY_FILE = "conversation_history.json"


# ==================== 工具函数 ====================

def load_history() -> List[Dict]:
    """加载历史对话"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载历史对话失败: {e}")
    return []

def save_history(history: List[Dict]) -> None:
    """保存历史对话"""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存历史对话失败: {e}")

def format_date(days_ago: int = 30) -> str:
    """格式化日期，返回前N个月的日期"""
    date = datetime.now() - timedelta(days=days_ago)
    return date.strftime("%Y-%m-%d")


# ==================== 模块1: PubMed API文献检索 ====================

def search_literature_pubmed(
    keyword: str,
    days_ago: int = 90,
    top_n: int = 10,
    filter_top_journals: bool = False
) -> List[Dict]:
    """
    使用PubMed API检索医学文献
    
    Args:
        keyword: 检索关键词
        days_ago: 检索最近多少天的文献
        top_n: 返回前N条结果
        filter_top_journals: 是否过滤顶级期刊（默认False，以获取更多结果）
    
    Returns:
        文献列表
    """
    
    # 构建PubMed查询
    query = keyword
    
    # 添加时间过滤
    if days_ago > 0:
        from_date = format_date(days_ago)
        to_date = format_date(0)
        query += f' AND ("{from_date}"[Date - Publication] : "{to_date}"[Date - Publication])'
    
    # 添加期刊过滤（可选）
    if filter_top_journals:
        journal_query = " OR ".join([f'"{j}"[Journal]' for j in TOP_JOURNALS])
        query += f' AND ({journal_query})'
    
    logger.info(f"正在使用PubMed检索文献: {keyword}")
    logger.info(f"PubMed查询语句: {query}")
    
    try:
        # 步骤1: ESearch - 搜索获取PMID列表
        esearch_url = f"{PUBMED_API_BASE}esearch.fcgi"
        esearch_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": top_n,
            "sort": "date"
        }
        
        response = requests.get(esearch_url, params=esearch_params, timeout=30)
        response.raise_for_status()
        esearch_data = response.json()
        
        # 获取PMID列表
        id_list = esearch_data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            logger.warning(f"PubMed未找到文献: {keyword}")
            return []
        
        logger.info(f"PubMed找到 {len(id_list)} 篇文献")
        
        # 步骤2: EFetch - 获取详细信息
        efetch_url = f"{PUBMED_API_BASE}efetch.fcgi"
        efetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        
        time.sleep(0.34)  # PubMed API限制：每秒最多3次请求
        
        response = requests.get(efetch_url, params=efetch_params, timeout=30)
        response.raise_for_status()
        xml_content = response.text
        
        # 解析XML - 不使用命名空间
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_content)
        
        results = []
        
        for article in root.findall(".//PubmedArticle"):
            try:
                # 提取基本信息
                pmid = article.find(".//PMID").text
                title = article.find(".//ArticleTitle").text or "No title"
                
                # 提取摘要
                abstract_elem = article.find(".//AbstractText")
                abstract = abstract_elem.text if abstract_elem is not None else "No abstract"
                
                # 提取作者
                authors = []
                affiliations = []
                for author_elem in article.findall(".//Author"):
                    last_name = author_elem.find("LastName")
                    fore_name = author_elem.find("ForeName")
                    if last_name is not None and fore_name is not None:
                        authors.append(f"{fore_name.text} {last_name.text}")
                        # 提取单位
                        for aff_elem in author_elem.findall(".//Affiliation"):
                            if aff_elem.text:
                                affiliations.append(aff_elem.text)
                
                # 提取期刊
                journal = article.find(".//Journal/Title")
                journal_name = journal.text if journal is not None else "Unknown"
                journal_abbr = article.find(".//Journal/ISOAbbreviation")
                journal_abbr_name = journal_abbr.text if journal_abbr is not None else ""
                
                # 提取发表日期
                pub_date_elem = article.find(".//PubDate")
                pub_date = "Unknown"
                if pub_date_elem is not None:
                    year = pub_date_elem.find("Year")
                    month = pub_date_elem.find("Month")
                    day = pub_date_elem.find("Day")
                    if year is not None:
                        pub_date = year.text
                        if month is not None:
                            pub_date += f"-{month.text}"
                            if day is not None:
                                pub_date += f"-{day.text}"
                
                # 构建URL
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": abstract[:800] if len(abstract) > 800 else abstract,
                    "journal": journal_name,
                    "journal_abbr": journal_abbr_name,
                    "authors": ", ".join(authors[:5]),  # 只取前5个作者
                    "affiliations": affiliations[:3],  # 只取前3个单位
                    "pmid": pmid,
                    "date": pub_date,
                    "keyword": keyword
                })
                
            except Exception as e:
                logger.warning(f"解析文章时出错: {e}")
                continue
        
        logger.info(f"PubMed检索完成，成功解析 {len(results)} 篇文献")
        return results
        
    except Exception as e:
        logger.error(f"PubMed检索失败: {e}")
        logger.error(f"错误详情: {str(e)}")
        return []


# ==================== 模块2: 按研究领域检索文献 ====================

def search_literature_by_domain(
    domain_key: str,
    days_ago: int = 90
) -> Dict:
    """
    按研究领域检索文献
    
    Args:
        domain_key: 研究领域键值（lung_cancer, lung_transplant, thoracic_sympathectomy）
        days_ago: 检索最近多少天
    
    Returns:
        包含领域信息和文献列表的字典
    """
    domain_info = RESEARCH_DOMAINS.get(domain_key)
    if not domain_info:
        logger.error(f"未知的研究领域: {domain_key}")
        return None
    
    logger.info(f"开始检索 {domain_info['name']} 的文献...")
    
    all_results = []
    seen_urls = set()
    
    # 遍历该领域的所有关键词
    for keyword in domain_info["keywords"]:
        results = search_literature_pubmed(
            keyword=keyword,
            days_ago=days_ago,
            top_n=domain_info["top_n_per_keyword"],
            filter_top_journals=False
        )
        
        # 去重
        for result in results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(result)
        
        # 避免请求过快
        time.sleep(0.5)
    
    logger.info(f"{domain_info['name']} 检索完成，共找到 {len(all_results)} 篇不重复文献")
    
    return {
        "domain_key": domain_key,
        "domain_name": domain_info["name"],
        "literature": all_results,
        "count": len(all_results)
    }


def search_all_domains(days_ago: int = 90) -> List[Dict]:
    """
    检索所有研究领域的文献
    
    Args:
        days_ago: 检索最近多少天
    
    Returns:
        所有领域的检索结果列表
    """
    all_domains_results = []
    
    for domain_key in RESEARCH_DOMAINS.keys():
        try:
            domain_result = search_literature_by_domain(domain_key, days_ago)
            if domain_result and domain_result["count"] > 0:
                all_domains_results.append(domain_result)
        except Exception as e:
            logger.error(f"检索 {domain_key} 时出错: {e}")
            continue
    
    return all_domains_results


# ==================== 模块3: DeepSeek API调用 ====================

def call_deepseek_api(
    messages: List[Dict],
    temperature: float = 0.7,
    max_tokens: int = 6000
) -> str:
    """
    调用DeepSeek API
    
    Args:
        messages: 对话消息列表
        temperature: 温度参数
        max_tokens: 最大token数
    
    Returns:
        API响应内容
    """
    if DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY_HERE":
        logger.error("请先配置DEEPSEEK_API_KEY")
        return "错误：请先配置DEEPSEEK_API_KEY"
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        logger.info(f"正在调用DeepSeek API...")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
            logger.error("API响应格式异常")
            return "错误：API响应格式异常"
            
    except Exception as e:
        logger.error(f"DeepSeek API调用失败: {e}")
        return f"错误：{str(e)}"


# ==================== 模块4: 科研简报生成（增强版）====================

def generate_research_briefing(domain_result: Dict) -> str:
    """
    生成科研简报（>=2500字）
    
    包含：题目、作者、单位、中英文摘要、研究目的/方法/结果/结论
    以及四大分析模块：统计学显微镜、亚组分析的宝藏、指南冲击波、乔医生冷思考
    
    Args:
        domain_result: 包含领域信息和文献列表的字典
    
    Returns:
        生成的科研简报文本
    """
    domain_name = domain_result["domain_name"]
    literature = domain_result["literature"]
    
    if not literature:
        return f"【{domain_name}简报】\n\n未找到相关文献，无法生成简报。"
    
    # 构建文献详细信息
    lit_details = []
    for i, item in enumerate(literature):
        detail = f"""
文献 {i+1}:
【标题】{item['title']}
【作者】{item.get('authors', 'Unknown')}
【单位】{', '.join(item.get('affiliations', ['Unknown']))}
【期刊】{item['journal']} ({item.get('journal_abbr', '')})
【发表日期】{item['date']}
【链接】{item['url']}
【摘要】{item['snippet']}
"""
        lit_details.append(detail)
    
    lit_summary = "\n".join(lit_details)
    
    system_prompt = """你是一位资深医学期刊编辑和临床研究者，在肺癌、肺移植、胸外科领域具有深厚造诣。请基于提供的医学文献，撰写一篇高质量的科研简报。

要求：
1. 总字数>=2500字
2. 必须包含以下完整结构：

【文献基本信息】
- 列出所有文献的标题、作者、单位、期刊、发表日期

【中文摘要】
- 综合所有文献，撰写300-500字的中文摘要

【English Abstract】
- 综合所有文献，撰写300-500字的英文摘要

【研究目的】
- 总结这些文献的研究目的和临床意义（200-300字）

【研究方法】
- 总结各研究的方法学特点（200-300字）

【研究结果】
- 使用Markdown表格展示关键研究结果
- 表格应包含：研究名称、样本量、主要终点、次要终点、疗效数据
- 表格示例：
| 研究名称 | 样本量 | 主要终点 | 次要终点 | 疗效数据 |
|---------|--------|---------|---------|---------|
| Study A | 500 | OS | PFS | HR=0.75 (95%CI: 0.65-0.86) |

【研究结论】
- 总结主要发现和临床启示（200-300字）

【四大分析模块】（每个模块400-600字）：

1. 统计学显微镜
- 深入分析各项研究的统计学方法
- 解读HR（风险比）、95%CI（置信区间）、P值的临床意义
- 分析样本量是否充足，统计学效能如何
- 讨论多重比较校正问题

2. 亚组分析的宝藏
- 挖掘各研究中亚组分析的临床意义
- 分析Forest Plot中不同亚组的疗效差异
- 讨论年龄、性别、病理类型、分期等亚组的特点
- 识别可能从治疗中获益的特殊人群

3. 指南冲击波
- 判定这些研究对NCCN/CSCO指南的潜在影响
- 分析证据等级（I级、II级、III级）
- 讨论是否可能改变现有治疗标准
- 预测指南更新的可能内容

4. 乔医生冷思考
- 结合临床经验，分析这些研究的局限性
- 讨论研究结果在真实世界中的适用性
- 分析在中国人群中的推广难点
- 提出未来研究的方向和改进建议

3. 语言风格：专业、严谨、学术化
4. 使用医学术语准确
5. 适当引用文献编号（如：[文献1]、[文献2]）
6. 表格必须使用Markdown格式"""

    user_prompt = f"""请基于以下文献撰写【{domain_name}简报】：

文献详细信息：
{lit_summary}

请严格按照上述结构要求撰写，确保每个部分都充分展开，特别是四大分析模块要深入分析。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    logger.info(f"正在生成【{domain_name}简报】...")
    response = call_deepseek_api(messages, temperature=0.5, max_tokens=6000)
    
    return f"【{domain_name}简报】\n\n{response}"


# ==================== 模块5: 公众号科普文生成 ====================

def generate_wechat_article(domain_result: Dict) -> str:
    """
    生成公众号科普文（>=3000字）
    风格：病例引出+深度综述+专家总结
    """
    domain_name = domain_result["domain_name"]
    literature = domain_result["literature"]
    
    if not literature:
        return f"【{domain_name}科普文】\n\n未找到相关文献。"
    
    lit_summary = "\n".join([
        f"{i+1}. {item['title']}\n   期刊: {item['journal']}\n   摘要: {item['snippet'][:150]}..."
        for i, item in enumerate(literature[:5])
    ])
    
    system_prompt = """你是一位擅长医学科普的医生博主，拥有丰富的临床经验。请基于提供的医学文献，撰写一篇面向大众的科普文章。

要求：
1. 总字数>=3000字
2. 文章结构：
   【真实病例】（300-500字）- 用一个真实的临床病例引出主题
   【深度科普】（2000-2500字）- 深入浅出地讲解疾病、治疗方法、最新进展
   【专家总结】（300-500字）- 总结关键要点，给出实用建议
   
3. 语言风格：
   - 3分叙事+7分科普及
   - 通俗口语化，避免过多专业术语
   - 必要时用生活化的比喻解释复杂概念
   - 适当加入"患者可能会问"的Q&A环节
   
4. 标题要求：吸引人但不夸张，能准确传达文章主旨
   
5. 使用表情符号和分段，增强可读性"""

    user_prompt = f"""请基于以下文献撰写【{domain_name}科普文】：

文献列表：
{lit_summary}

请严格按照上述结构撰写。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    logger.info(f"正在生成【{domain_name}科普文】...")
    response = call_deepseek_api(messages, temperature=0.8, max_tokens=5000)
    
    return f"【{domain_name}科普文】\n\n{response}"


# ==================== 模块6: 小红书科普文生成 ====================

def generate_xiaohongshu_article(domain_result: Dict) -> str:
    """
    生成小红书科普文（800-1000字）
    2026年临床医生口吻，通俗、真诚、接地气
    """
    domain_name = domain_result["domain_name"]
    literature = domain_result["literature"]
    
    if not literature:
        return f"【{domain_name}小红书科普文】\n\n未找到相关文献。"
    
    # 提取病种名称（去掉"领域"二字）
    if "肺癌" in domain_name:
        disease_name = "肺癌"
    elif "肺移植" in domain_name:
        disease_name = "肺移植"
    elif "胸交感神经切除" in domain_name:
        disease_name = "胸交感神经切除"
    else:
        disease_name = domain_name
    
    # 选择前3篇文献
    top_lit = literature[:3]
    lit_summary = "\n".join([
        f"• {item['title']}\n  {item['snippet'][:150]}..."
        for i, item in enumerate(top_lit)
    ])
    
    system_prompt = """你是一位2026年的临床医生，在肺癌、肺移植、胸外科领域有丰富经验。请基于提供的医学文献，撰写一篇小红书风格的科普笔记。

核心要求：
1. 字数严格控制在800-1000字
2. 语言风格：
   - 26年临床医生口吻，通俗、真诚、接地气
   - 禁止使用"综上所述、如图所示、由此可见"等官方套话
   - 使用"大白话讲、这意味着、核心定位、医生真心话、关键提醒"等口语化表达
   - 短句为主，节奏快，读起来像医生在面对面聊天

3. 标题要求：
   - 必须包含爆款标题
   - emoji表情+吸引点击+情绪价值
   - 例如："🚨查出这个千万别拖！医生深夜紧急提醒" "💥肺结节3个信号！90%的人错过了"

4. 必须包含的元素：

   【典型临床案例】（150-200字）
   - 简短真实、贴近患者
   - 用"上周门诊来了个50岁的大叔"这样的开场
   - 案例要能引出后续的干货内容
   
   【配图建议】（至少3条，明确画面内容）
   - 用"配图1："、"配图2："、"配图3："标记
   - 每条配图建议明确描述画面内容
   - 例如："配图1：医生拿着X光片指给患者看，旁边标注'这是早期肺癌'"
   
   【中英文对照】（专业术语统一对照）
   - 重要医学术语先中文解释，后括号加英文
   - 例如："靶向治疗（Targeted Therapy）、免疫治疗（Immunotherapy）"
   - 至少包含5-8个关键术语对照

5. 结构要求：
   【痛点引入】（80-120字）- 用情绪化语言引起共鸣
   【典型临床案例】（150-200字）- 真实案例开场
   【核心干货】（450-550字）- 用大白话讲清楚核心内容
   【医生真心话提醒】（100-150字）- 给出实用建议
   【总结】（50-80字）- 用1-2句话收尾
   
6. 其他要求：
   - 大量使用emoji表情（🚨💥⚠️✅等）
   - 用数字列表和分隔线（---）
   - 结尾添加5-8个相关话题标签
   - 整体要真诚、有温度、像朋友聊天"""

    user_prompt = f"""请基于以下文献撰写【{disease_name}小红书科普文】：

文献列表：
{lit_summary}

请严格按照上述要求撰写，确保包含：
1. 爆款标题
2. 典型临床案例
3. 至少3条配图建议
4. 5-8个中英文术语对照
5. 使用大白话，不用官方套话
6. 800-1000字"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    logger.info(f"正在生成【{disease_name}小红书科普文】...")
    response = call_deepseek_api(messages, temperature=0.9, max_tokens=2500)
    
    return f"【{disease_name}小红书科普文】\n\n{response}"


# ==================== 主程序 ====================

def main():
    """主程序入口"""
    print("=" * 60)
    print("医学文献自动化助手 - 多领域版本")
    print("Medical Literature Automation Assistant - Multi-Domain")
    print("=" * 60)
    print()
    
    # 检查API配置
    if DEEPSEEK_API_KEY == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("警告：请先在代码中配置DEEPSEEK_API_KEY")
        return
    
    print(f"当前检索模式: {SEARCH_MODE}")
    print()
    print("开始执行文献自动化流程...\n")
    
    # 加载历史对话
    history = load_history()
    print(f"已加载 {len(history)} 条历史对话记录\n")
    
    # 步骤1: 按领域检索文献
    print("步骤 1/4: 按三大研究领域检索文献...")
    all_domains_results = search_all_domains(days_ago=90)
    
    if not all_domains_results:
        print("未检索到任何领域的文献，请检查网络连接或API配置")
        return
    
    print(f"\n成功检索到 {len(all_domains_results)} 个领域的文献：")
    for domain_result in all_domains_results:
        print(f"  - {domain_result['domain_name']}: {domain_result['count']} 篇")
    print()
    
    # 步骤2: 为每个领域生成科研简报
    print("步骤 2/4: 为每个领域生成科研简报...")
    briefing_results = []
    for domain_result in all_domains_results:
        try:
            briefing = generate_research_briefing(domain_result)
            briefing_results.append(briefing)
            print(f"  ✅ {domain_result['domain_name']}简报生成完成")
        except Exception as e:
            logger.error(f"生成{domain_result['domain_name']}简报时出错: {e}")
            briefing_results.append(f"【{domain_result['domain_name']}简报】\n\n生成失败: {str(e)}")
    print()
    
    # 步骤3: 为每个领域生成公众号科普文
    print("步骤 3/4: 为每个领域生成公众号科普文...")
    wechat_results = []
    for domain_result in all_domains_results:
        try:
            article = generate_wechat_article(domain_result)
            wechat_results.append(article)
            print(f"  ✅ {domain_result['domain_name']}科普文生成完成")
        except Exception as e:
            logger.error(f"生成{domain_result['domain_name']}科普文时出错: {e}")
            wechat_results.append(f"【{domain_result['domain_name']}科普文】\n\n生成失败: {str(e)}")
    print()
    
    # 步骤4: 为每个领域生成小红书科普文
    print("步骤 4/4: 为每个领域生成小红书科普文...")
    xiaohongshu_results = []
    for domain_result in all_domains_results:
        try:
            article = generate_xiaohongshu_article(domain_result)
            xiaohongshu_results.append(article)
            print(f"  ✅ {domain_result['domain_name']}小红书笔记生成完成")
        except Exception as e:
            logger.error(f"生成{domain_result['domain_name']}小红书笔记时出错: {e}")
            xiaohongshu_results.append(f"【{domain_result['domain_name']}小红书笔记】\n\n生成失败: {str(e)}")
    print()
    
    # 保存结果到文件（每个领域独立文件）
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 为每个领域保存独立的科研简报
    print("\n保存科研简报...")
    for i, (domain_result, briefing) in enumerate(zip(all_domains_results, briefing_results)):
        domain_name = domain_result["domain_name"]
        filename = f"{date_str}_{domain_name}_科研简报.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(briefing)
        print(f"  ✅ 已保存: {filename}")
    
    # 为每个领域保存独立的公众号科普文
    print("\n保存公众号科普文...")
    for i, (domain_result, article) in enumerate(zip(all_domains_results, wechat_results)):
        domain_name = domain_result["domain_name"]
        filename = f"{date_str}_{domain_name}_科普文章.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(article)
        print(f"  ✅ 已保存: {filename}")
    
    # 为每个领域保存独立的小红书科普文
    print("\n保存小红书科普文...")
    for i, (domain_result, article) in enumerate(zip(all_domains_results, xiaohongshu_results)):
        # 提取病种名称（去掉"领域"二字）
        domain_name = domain_result["domain_name"]
        if "肺癌" in domain_name:
            disease_name = "肺癌"
        elif "肺移植" in domain_name:
            disease_name = "肺移植"
        elif "胸交感神经切除" in domain_name:
            disease_name = "胸交感神经切除"
        else:
            disease_name = domain_name
        
        filename = f"{date_str}_{disease_name}_小红书科普文.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(article)
        print(f"  ✅ 已保存: {filename}")
    
    # 保存各领域文献列表
    for domain_result in all_domains_results:
        domain_key = domain_result["domain_key"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"literature_{domain_key}_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(domain_result["literature"], f, ensure_ascii=False, indent=2)
        print(f"  ✅ {domain_result['domain_name']}文献列表已保存至: literature_{domain_key}_{timestamp}.json")
    
    # 更新历史对话
    files_generated = []
    for domain_result in all_domains_results:
        # 提取病种名称（去掉"领域"二字）
        domain_name = domain_result["domain_name"]
        if "肺癌" in domain_name:
            disease_name = "肺癌"
        elif "肺移植" in domain_name:
            disease_name = "肺移植"
        elif "胸交感神经切除" in domain_name:
            disease_name = "胸交感神经切除"
        else:
            disease_name = domain_name
        
        files_generated.extend([
            f"{date_str}_{domain_name}_科研简报.md",
            f"{date_str}_{domain_name}_科普文章.md",
            f"{date_str}_{disease_name}_小红书科普文.md"
        ])
    
    history.append({
        "timestamp": timestamp,
        "domains": [domain["domain_name"] for domain in all_domains_results],
        "total_literature": sum(domain["count"] for domain in all_domains_results),
        "files_generated": files_generated
    })
    save_history(history)
    print(f"历史对话已更新\n")
    
    print("=" * 60)
    print("全部完成！")
    print(f"共生成 {len(briefing_results)} 份科研简报")
    print(f"共生成 {len(wechat_results)} 篇公众号文章")
    print(f"共生成 {len(xiaohongshu_results)} 篇小红书笔记")
    print("=" * 60)


if __name__ == "__main__":
    main()
