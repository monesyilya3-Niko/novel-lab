"""网文智能起名工坊引擎 — 100% 纯 Python 标准库实现。

支持：
1. 角色名（按题材风格、性别过滤，规避烂大街流水线重名）；
2. 宗门势力 / 财阀集团 / 科技联邦 / 异能公会；
3. 功法绝学 / 战技秘典 / 异能神通；
4. 神兵法宝 / 科技装备 / 上古神器。
"""
from __future__ import annotations

import random
from typing import Any

# ---------------------------------------------------------------------------
# 姓氏库
# ---------------------------------------------------------------------------
COMMON_SURNAMES = [
    "林", "陆", "顾", "沈", "谢", "裴", "霍", "楚", "苏", "周", "叶", "萧",
    "陈", "李", "张", "秦", "韩", "徐", "程", "宋", "唐", "白", "傅", "江"
]

RARE_COMPOUND_SURNAMES = [
    "诸葛", "司马", "欧阳", "夏侯", "皇甫", "上官", "公孙", "令狐", "东方", "独孤",
    "慕容", "司徒", "百里", "拓跋", "长孙", "宇文", "司空", "南宫", "太史", "呼延"
]

WESTERN_FIRST_NAMES = [
    "亚瑟", "雷恩", "克里斯", "维克托", "罗恩", "艾伦", "卡尔", "诺亚", "伊恩", "休斯",
    "奥利弗", "塞巴斯蒂安", "卢卡斯", "加百列", "亚德里安", "赛弗", "莱斯特", "达利安"
]

# ---------------------------------------------------------------------------
# 角色名素库（按风格与性别细分）
# ---------------------------------------------------------------------------
CHARACTER_VOCAB = {
    # 仙侠飘逸 / 古典修真
    "xianxia": {
        "male": [
            "长生", "青玄", "知衍", "云深", "清绝", "守拙", "明澈", "望尘", "怀舟", "临渊",
            "弈秋", "九思", "玄霄", "归真", "无咎", "修远", "抱朴", "砚冰", "逸白", "岁桉",
            "景行", "栖竹", "重霄", "墨寻", "问川", "折风", "浮生", "枕流", "宴平", "云谏"
        ],
        "female": [
            "清婉", "微澜", "知夏", "素商", "浅予", "如岁", "若雪", "晚照", "云舒", "初霁",
            "折霜", "月白", "南絮", "秋水", "朝颜", "寄瑶", "寻欢", "弄晴", "望舒", "映澈",
            "青梧", "锦瑟", "竹清", "扶微", "梦渔", "汀兰", "若华", "静姝", "采薇", "舒窈"
        ],
        "neutral": [
            "无尘", "若虚", "行简", "玄策", "微澜", "知非", "观棋", "照影", "听雨", "归途"
        ]
    },
    # 都市商战 / 现代精英
    "dushi": {
        "male": [
            "廷彦", "承越", "景曜", "泽恒", "铭远", "振东", "致远", "修哲", "睿辰", "峻熙",
            "凯旋", "嘉树", "宏图", "宇森", "承泽", "晋恒", "崇文", "瀚海", "廷钧", "耀廷",
            "慎言", "言深", "谨之", "行舟", "斯年", "泊远", "卓然", "牧言", "驰野", "见深"
        ],
        "female": [
            "清栀", "温言", "书禾", "语嫣", "知许", "念慈", "以宁", "星漫", "思渺", "芷若",
            "安然", "允诺", "若宁", "晚青", "微吟", "欣然", "锦宁", "予安", "景宜", "知意",
            "嘉怡", "佩芸", "怀瑾", "秋宁", "言蹊", "清雅", "舒曼", "沛凝", "映真", "初晴"
        ],
        "neutral": [
            "言川", "林深", "向远", "朝夕", "一诺", "知秋", "江澜", "清野", "北辰", "青木"
        ]
    },
    # 科幻末世 / 废土硬核
    "kehuan": {
        "male": [
            "重渊", "破虏", "雷动", "铁甲", "锋锐", "裂空", "极光", "苍穹", "震川", "逆锋",
            "拓荒", "斩月", "曜星", "猎鹰", "黑曜", "磁悬", "磐石", "赤霄", "暴风", "断浪",
            "凯文", "雷恩", "罗夏", "柯林", "赛博", "泰坦", "罗杰", "沃克", "肖恩", "布雷克"
        ],
        "female": [
            "夜莺", "星岚", "紫电", "幽兰", "凌霜", "幻羽", "青鸾", "月芒", "红雀", "寒光",
            "艾达", "米娅", "莉莉丝", "塞拉", "艾薇", "蕾娜", "诺娃", "希尔", "维多利亚", "克洛伊"
        ],
        "neutral": [
            "零号", "孤星", "暗潮", "天穹", "极昼", "极夜", "裂隙", "幻影", "先驱", "方舟"
        ]
    },
    # 玄幻霸气 / 诸天异界
    "xuanhuan": {
        "male": [
            "啸天", "战天", "君临", "傲天", "破军", "苍生", "无极", "断天", "重光", "霸先",
            "吞海", "绝顶", "踏仙", "遮天", "九幽", "镇狱", "乱古", "无始", "恒宇", "青帝",
            "荒天", "太初", "诛天", "冥夜", "焚天", "御龙", "撼山", "碎星", "弑神", "通天"
        ],
        "female": [
            "凰月", "倾城", "天骄", "傲霜", "璇玑", "琉璃", "踏雪", "碧落", "幽凰", "明月",
            "帝女", "洛神", "灵曦", "梦华", "霓裳", "紫薇", "玉衡", "摇光", "神曦", "云汐"
        ],
        "neutral": [
            "天权", "混沌", "太初", "永夜", "造化", "天道", "太虚", "无量", "归元", "真武"
        ]
    },
    # 悬疑诡异 / 惊悚怪谈
    "xuanyi": {
        "male": [
            "慎独", "守心", "明鉴", "无恙", "安平", "秉烛", "照幽", "夜巡", "藏锋", "守真",
            "默言", "慎思", "见微", "潜龙", "解意", "辨色", "存真", "未明", "断妄", "破障"
        ],
        "female": [
            "幽微", "静夜", "素心", "若兰", "微光", "清音", "晚霜", "初见", "凝安", "如水",
            "沉香", "白芷", "半夏", "佩兰", "紫苏", "青黛", "木香", "知母", "辛夷", "细辛"
        ],
        "neutral": [
            "无名", "归人", "守夜", "寻道", "秉烛", "过客", "行者", "破晓", "惊蛰", "霜降"
        ]
    }
}

# ---------------------------------------------------------------------------
# 宗门势力素库
# ---------------------------------------------------------------------------
SECT_PREFIXES = ["青云", "紫霄", "太虚", "九幽", "天道", "玄天", "万象", "无极", "昆仑", "蜀山", "乾坤", "星宿", "大荒", "天衍", "神霄"]
SECT_MODIFIERS = ["真武", "剑极", "灵台", "造化", "丹鼎", "神武", "阴阳", "四象", "八荒", "诛仙", "问道", "长生", "万劫", "混沌"]
SECT_SUFFIXES = ["宗", "门", "阁", "派", "宫", "谷", "殿", "山庄", "圣地", "皇朝", "世家", "道盟", "神教", "法会"]

CORP_PREFIXES = ["启明", "华泰", "恒瑞", "远洋", "天成", "博雅", "宏图", "盛世", "鼎盛", "嘉禾", "深蓝", "创纪", "星海", "天工"]
CORP_FIELDS = ["重工", "科技", "生物", "资本", "矿业", "能源", "航天", "医药", "金融", "智造", "微电", "建设"]
CORP_SUFFIXES = ["集团", "财阀", "实业", "控股", "联合体", "投资有限公司", "全球发展总署", "理事会"]

# ---------------------------------------------------------------------------
# 功法战技素库
# ---------------------------------------------------------------------------
SKILL_RANKS = ["天阶", "地阶", "荒古", "上古", "太古", "九幽", "混沌", "纯阳", "先天", "神级", "无上帝品"]
SKILL_ELEMENTS = ["真龙", "神象", "九天", "青莲", "大荒", "紫电", "焚天", "玄冥", "破空", "太阴", "斩仙", "截天", "星罗"]
SKILL_FORMS = ["宝鉴", "真经", "神诀", "九式", "神体", "古卷", "造化诀", "碎空指", "拔剑术", "游身步", "惊雷枪", "镇魔印"]

# ---------------------------------------------------------------------------
# 神兵法宝素库
# ---------------------------------------------------------------------------
ARTIFACT_ELEMENTS = ["太素", "玄黄", "九龙", "诛仙", "斩月", "断浪", "山河", "混沌", "两仪", "四象", "虚空", "弑神", "量天"]
ARTIFACT_TYPES = ["神剑", "龙枪", "战戟", "古鼎", "宝钟", "玄塔", "明镜", "道玺", "天印", "拂尘", "玉佩", "折扇", "机甲核心"]


def generate_character_names(style: str = "xianxia", gender: str = "all", count: int = 10) -> list[str]:
    """生成角色名列表。"""
    style_key = style if style in CHARACTER_VOCAB else "xianxia"
    pool: list[str] = []
    
    if gender in ("male", "all"):
        pool.extend(CHARACTER_VOCAB[style_key]["male"])
    if gender in ("female", "all"):
        pool.extend(CHARACTER_VOCAB[style_key]["female"])
    if gender in ("neutral", "all"):
        pool.extend(CHARACTER_VOCAB[style_key]["neutral"])
        
    results: list[str] = []
    used = set()
    
    for _ in range(max(1, min(count, 50))):
        for _retry in range(30):
            # 80% 单姓，20% 复姓
            if random.random() < 0.2 and RARE_COMPOUND_SURNAMES:
                surname = random.choice(RARE_COMPOUND_SURNAMES)
            else:
                surname = random.choice(COMMON_SURNAMES)
                
            first_name = random.choice(pool)
            full_name = f"{surname}{first_name}"
            if full_name not in used:
                used.add(full_name)
                results.append(full_name)
                break
                
    return results


def generate_sect_names(kind: str = "sect", count: int = 10) -> list[str]:
    """生成宗门势力或财阀集团名称。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    
    for _ in range(count):
        for _retry in range(30):
            if kind == "corp":
                name = f"{random.choice(CORP_PREFIXES)}{random.choice(CORP_FIELDS)}{random.choice(CORP_SUFFIXES)}"
            else:
                # 宗门门派
                if random.random() < 0.5:
                    name = f"{random.choice(SECT_PREFIXES)}{random.choice(SECT_MODIFIERS)}{random.choice(SECT_SUFFIXES)}"
                else:
                    name = f"{random.choice(SECT_PREFIXES)}{random.choice(SECT_SUFFIXES)}"
            if name not in used:
                used.add(name)
                results.append(name)
                break
                
    return results


def generate_skill_names(count: int = 10) -> list[str]:
    """生成功法战技秘典名称。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    
    for _ in range(count):
        for _retry in range(30):
            if random.random() < 0.4:
                name = f"【{random.choice(SKILL_RANKS)}】{random.choice(SKILL_ELEMENTS)}{random.choice(SKILL_FORMS)}"
            else:
                name = f"{random.choice(SKILL_ELEMENTS)}{random.choice(SKILL_FORMS)}"
            if name not in used:
                used.add(name)
                results.append(name)
                break
                
    return results


def generate_artifact_names(count: int = 10) -> list[str]:
    """生成神兵法宝器物名称。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    
    for _ in range(count):
        for _retry in range(30):
            name = f"{random.choice(ARTIFACT_ELEMENTS)}{random.choice(ARTIFACT_TYPES)}"
            if name not in used:
                used.add(name)
                results.append(name)
                break
                
    return results


TEAM_PREFIXES = ["极光", "破晓", "星芒", "暗影", "无畏", "天擎", "银翼", "赤焰", "幻影", "雷霆", "神谕", "巅峰", "狂澜", "苍穹"]
TEAM_SUFFIXES = ["战队", "电子竞技俱乐部", "Gaming", "Esports", "先锋队", "俱乐部", "Team"]

SHELTER_PREFIXES = ["晨曦", "希望", "钢铁壁垒", "诺亚", "曙光", "方舟", "永夜", "黑石", "磐石", "地下城", "守望", "避难所", "新绿洲"]
SHELTER_SUFFIXES = ["基地", "避难所", "聚集地", "要塞", "安全区", "前哨站", "地下城", "特别行政特区"]

ORG_PREFIXES = ["第七", "第九", "第十三", "守秘人", "深空", "天理", "真理", "异象", "黑水", "天启", "秩序", "极密", "异常收容"]
ORG_SUFFIXES = ["调查局", "基金会", "协议会", "研究所", "防务联盟", "仲裁庭", "理事会", "监督部", "学会"]


def generate_team_names(count: int = 10) -> list[str]:
    """生成电竞战队或竞技俱乐部名称。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    for _ in range(count):
        for _retry in range(30):
            name = f"{random.choice(TEAM_PREFIXES)}{random.choice(TEAM_SUFFIXES)}"
            if name not in used:
                used.add(name)
                results.append(name)
                break
    return results


def generate_shelter_names(count: int = 10) -> list[str]:
    """生成末日避难所、聚集地或生存要塞名称。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    for _ in range(count):
        for _retry in range(30):
            name = f"{random.choice(SHELTER_PREFIXES)}{random.choice(SHELTER_SUFFIXES)}"
            if name not in used:
                used.add(name)
                results.append(name)
                break
    return results


def generate_org_names(count: int = 10) -> list[str]:
    """生成怪谈收容机构、神秘调查局或科研联盟名称。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    for _ in range(count):
        for _retry in range(30):
            name = f"{random.choice(ORG_PREFIXES)}{random.choice(ORG_SUFFIXES)}"
            if name not in used:
                used.add(name)
                results.append(name)
                break
    return results


# ---------------------------------------------------------------------------
# 爆款网文书名词库与三段式公式（身份/开局 + 核心转折/外挂 + 终极爽感/钩子）
# ---------------------------------------------------------------------------
TITLE_VOCAB: dict[str, dict[str, list[str]]] = {
    "xianxia": {
        "identities": [
            "开局被废本命飞剑", "斩天剑宗小师叔", "人在仙门刚成杂役", "开局被夺至尊骨",
            "退婚当日我顿悟大道", "绑定签到系统三百年", "修仙万年方知是反派", "满级大能重修",
            "炼丹童子觉醒神级天赋", "被逐出师门当天", "我本仙尊转世", "无敌剑仙重生"
        ],
        "twists": [
            "觉醒万倍返还系统", "我能看到万物词条", "反手契约上古神凰", "顿悟满级他化自在法",
            "每天签到一本神级帝经", "一剑斩碎三十三重天", "绑定诸天功法模拟器", "识海深处藏着混沌天宫",
            "把废丹炼成九转金丹", "开局继承诛仙剑阵", "反手镇压反派老祖"
        ],
        "hooks": [
            "，全宗门老祖跪求原谅", "，直接打爆诸天神魔", "，震惊九天十地",
            "，这一剑你拿什么挡", "，举世皆敌又如何", "，圣女连夜送上本命灵宝",
            "，诸天仙帝皆来朝拜", "，弹指间苍穹倾覆"
        ]
    },
    "dushi": {
        "identities": [
            "开局被拜金女甩在民政局", "隐世财阀唯一继承人", "送外卖被万亿总裁倒追",
            "离婚当天激活万亿黑卡", "穿越成假千金真团宠", "摊牌了我是全球首富",
            "神豪科技系统的宿主", "被全公司孤立之后", "开局继承八千栋楼",
            "退役兵王重返都市", "千亿财阀大少隐姓埋名"
        ],
        "twists": [
            "开局奖励百亿现金与汤臣一品", "我能听见顶级大佬心声", "绑定情绪打脸暴击系统",
            "反手收购前女友家族企业", "一眼看穿古玩原石底细", "觉醒神级神医传承",
            "直接买下整座金融中心", "投资回报率高达一万倍", "开启万界黑科技商城"
        ],
        "hooks": [
            "，前妻一家跪在雨中痛哭", "，全城权贵争相上门巴结", "，打脸全场悔恨不及",
            "，千亿财阀当场叫爸爸", "，震惊整个华尔街", "，商界巨鳄躬身迎接",
            "，这一刻他们高攀不起", "，直接买下全球首富榜"
        ]
    },
    "kehuan": {
        "identities": [
            "极寒天灾降临前一个月", "全球丧尸爆发第一天", "重生在智械危机爆发前夕",
            "开局继承地下安全堡垒", "人在废土刚开出神级基地车", "觉醒机械亲和超维异能",
            "辐射末世求生第一百天", "开局契约星际母舰核心", "纳米寄生体全面暴乱"
        ],
        "twists": [
            "我疯狂囤积万亿物资", "给避难所加装反物质歼星炮", "打造无限能源超级地下城",
            "一键无限升级基地设施", "契约深渊异种成为虫群主宰", "基因锁直接冲破第七阶",
            "把机械装甲爆改成神级泰坦", "解析外星高维科技蓝图"
        ],
        "hooks": [
            "，恶毒邻居还在挨冻我吃战斧牛排", "，各大庇护所跪求借粮", "，单手硬撼十级尸王狂潮",
            "，直接横推整个末日", "，星际舰队奉我为神明", "，人类最后的救世方舟"
        ]
    },
    "xuanyi": {
        "identities": [
            "欢迎来到无限规则怪谈", "深夜接到死者打来的求救电话", "人在精神病院刚觉醒死神之眼",
            "凶宅试睡员的第一夜", "成为异常收容所唯一人类所长", "开局被拉入诡异直播间",
            "调查连环命案第十三天", "我能听见死者生前遗言", "午夜十二点的神秘列车"
        ],
        "twists": [
            "我能洞察所有规则漏洞", "反手把红衣厉鬼当房客收租", "开局给不可名状邪神做心理咨询",
            "用物理法则超度一切诡异", "诡异全成了我的兼职打工人", "随手撕碎了邪神降临法阵",
            "在惊悚副本里直接建立新秩序"
        ],
        "hooks": [
            "，吓得S级邪神连夜退群", "，全网数亿观众直接看呆了", "，不可名状的存在直呼祖宗",
            "，这主播把诡异当狗溜", "，通关后整个诡异副本全崩了", "，连夜改写通关评级"
        ]
    },
    "duanpian": {
        "identities": [
            "妻子以为她做的事天衣无缝", "资助贫困生十年后我被送上法庭", "假千金死遁后全家发疯了",
            "发现老公手机里的小号后", "被全家吸血三十年我直接断绝关系", "闺蜜抢了我的未婚夫之后",
            "重生回被真千金赶出家门那晚", "为救小舅子掏空积蓄后"
        ],
        "twists": [
            "我默默拿出了第三套录音笔", "当庭播放那段长达八小时的监控", "反手将私匿账本公之于众",
            "我微笑着签字转身走向新生活", "他们不知道我早已立好公证遗嘱", "我毫不犹豫拉黑了所有亲属"
        ],
        "hooks": [
            "，如今跪在火葬场哭给谁看", "，这一局你拿什么赢我", "，法庭宣判那天全网泪崩",
            "，这一次我绝不回头", "，恶毒亲戚最终身败名裂", "，你们的报应才刚刚开始"
        ]
    }
}


def generate_title_names(style: str = "xianxia", count: int = 10) -> list[str]:
    """生成爆款网文书名（三段式公式：开局/身份 + 核心外挂 + 终极爽感）。"""
    results: list[str] = []
    used = set()
    count = max(1, min(count, 50))
    s_key = style.lower().strip()
    if s_key not in TITLE_VOCAB:
        if s_key in ("xuanhuan", "wuxia"):
            s_key = "xianxia"
        elif s_key in ("moshi", "kehuan_moshi"):
            s_key = "kehuan"
        elif s_key in ("zhihu", "yanxuan", "short_story"):
            s_key = "duanpian"
        else:
            s_key = "xianxia"

    pool = TITLE_VOCAB[s_key]
    connectors = ["：", "，", "：开局", "：我"]

    for _ in range(count):
        for _retry in range(50):
            identity = random.choice(pool["identities"])
            twist = random.choice(pool["twists"])
            hook = random.choice(pool["hooks"])

            # 灵活组合连接符
            conn = random.choice(connectors)
            if conn == "：开局" and identity.startswith("开局"):
                conn = "："
            if conn == "：我" and twist.startswith("我"):
                conn = "："

            # 两种经典格式：冒号卖点型 or 逗号直接型
            if random.random() < 0.65:
                raw_title = f"{identity}{conn}{twist}{hook}"
            else:
                raw_title = f"{identity}，{twist}{hook}"

            # 清理可能出现的标点重复
            clean_title = raw_title.replace("，，", "，").replace("：：", "：").replace("，：", "：")
            name = f"《{clean_title}》"
            if name not in used:
                used.add(name)
                results.append(name)
                break

    return results


def generate(kind: str = "character", style: str = "xianxia", gender: str = "all", count: int = 10) -> dict[str, Any]:
    """起名工坊对外统一接口。"""
    kind = kind.lower().strip()
    if kind == "character":
        names = generate_character_names(style=style, gender=gender, count=count)
    elif kind in ("title", "book_title", "novel_title"):
        names = generate_title_names(style=style, count=count)
    elif kind in ("sect", "faction"):
        names = generate_sect_names(kind="sect", count=count)
    elif kind in ("corp", "company"):
        names = generate_sect_names(kind="corp", count=count)
    elif kind in ("skill", "kungfu"):
        names = generate_skill_names(count=count)
    elif kind in ("artifact", "weapon"):
        names = generate_artifact_names(count=count)
    elif kind in ("team", "esports"):
        names = generate_team_names(count=count)
    elif kind in ("shelter", "base"):
        names = generate_shelter_names(count=count)
    elif kind in ("org", "agency", "institution"):
        names = generate_org_names(count=count)
    else:
        names = generate_character_names(style=style, gender=gender, count=count)
        
    return {
        "kind": kind,
        "style": style,
        "gender": gender,
        "count": len(names),
        "names": names
    }
