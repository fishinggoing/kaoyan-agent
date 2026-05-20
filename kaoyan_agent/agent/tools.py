# kaoyan_agent/agent/tools.py

TOOLS = [
    {
        "name": "search_schools",
        "description": "按条件搜索学校。可以按省份、学校层次、类型和关键词筛选。",
        "input_schema": {
            "type": "object",
            "properties": {
                "province": {
                    "type": "string",
                    "description": "省份名称，如'浙江'、'江苏'",
                },
                "tier": {
                    "type": "string",
                    "enum": ["985", "211", "双一流", "双非"],
                    "description": "学校层次",
                },
                "type": {
                    "type": "string",
                    "description": "学校类型，如'综合'、'理工'、'师范'",
                },
                "keyword": {
                    "type": "string",
                    "description": "学校名称关键词",
                },
            },
        },
    },
    {
        "name": "get_majors",
        "description": "查询学校开设的专业及学科评估等级。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "学校ID，从search_schools结果中获取",
                },
                "discipline": {
                    "type": "string",
                    "description": "专业名称关键词，如'计算机'、'软件'",
                },
            },
        },
    },
    {
        "name": "query_scores",
        "description": "查询复试分数线、报录比、招生人数等硬指标。返回最新年份数据优先。",
        "input_schema": {
            "type": "object",
            "properties": {
                "major_id": {
                    "type": "integer",
                    "description": "专业ID，从get_majors结果中获取",
                },
                "year": {
                    "type": "integer",
                    "description": "查询年份，不填则返回所有年份",
                },
            },
        },
    },
    {
        "name": "query_admitted_scores",
        "description": "查询实际录取分数（最低分/平均分/最高分）。仅在用户明确询问'实际录取分数'、'录取的人考了多少分'时才调用此工具。",
        "input_schema": {
            "type": "object",
            "properties": {
                "major_id": {
                    "type": "integer",
                    "description": "专业ID",
                },
                "year": {
                    "type": "integer",
                    "description": "查询年份",
                },
            },
        },
    },
    {
        "name": "get_employment",
        "description": "查询学校的就业质量信息（就业率、平均薪资、就业去向摘要）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_id": {
                    "type": "integer",
                    "description": "学校ID",
                },
            },
        },
    },
    {
        "name": "compare_schools",
        "description": "横向对比多所学校同一专业的硬指标。输入学校ID列表和专业名称，返回各校分数线、报录比、学科评估等数据。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "要对比的学校ID列表",
                },
                "major_name": {
                    "type": "string",
                    "description": "专业名称",
                },
            },
            "required": ["school_ids", "major_name"],
        },
    },
    {
        "name": "collect_school_info",
        "description": "当数据库中找不到用户询问的学校时，调用此工具从研招网采集学校信息。采集到的数据会自动写入数据库，之后可以重新查询。仅在确认学校不存在时调用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "school_name": {
                    "type": "string",
                    "description": "要采集的学校全称，如'同济大学'、'复旦大学'",
                },
            },
            "required": ["school_name"],
        },
    },
]
