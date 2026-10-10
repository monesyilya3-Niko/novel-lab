"""网文核心毒点与弃坑点排查引擎 — 100% 纯 Python 标准库实现。

排查 10 大核心高危毒点：
1. excessive_suffering: 过度憋屈受辱无反抗
2. enemy_mercy: 圣母资敌放虎归山
3. simp_behavior: 降智舔狗践踏尊严
4. power_inconsistency: 战力断崖崩坏与数值膨胀
5. preachy_monologue: 作者下场长篇生硬说教
6. distress_trope: 核心女配莫名被俘送人头
7. ntr_ambiguity: 绿帽擦边与情感忠诚背叛
8. nerfed_powers: 金手指莫名被夺削弱
9. broken_promise: 言而无信承诺烂尾
10. brainless_antagonist: 反派无脑复读找茬
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# 毒点规则定义
# ---------------------------------------------------------------------------
POISON_PATTERNS = [
    {
        "type": "excessive_suffering",
        "name": "过度憋屈受辱",
        "severity": "fatal",
        "weight": 25,
        "patterns": [
            r"(跪在地上|跪下磕头|自扇耳光|扇了自己两个耳光|趴在地上学狗叫|钻过胯下)",
            r"(任凭对方羞辱|低头不敢出声|默默忍受着殴打|苦苦哀求放过|咽下耻辱不敢反抗)",
            r"(向对方赔罪认错|卑躬屈膝地道歉|打不还手骂不还口)"
        ],
        "reason": "主角遭受极端人格侮辱却没有任何反击动作或暗中布局，引起读者强烈憋屈与弃书冲动。",
        "suggestion": "缩短受辱篇幅，并当场展现反击动作（暗下死手、记下死账、布下杀局）。"
    },
    {
        "type": "enemy_mercy",
        "name": "圣母资敌放虎归山",
        "severity": "fatal",
        "weight": 25,
        "patterns": [
            r"(得饶人处且饶人|不想脏了自己的手|这次就放你一马|冤冤相报何时了|放他离去吧)",
            r"(留你一条狗命走吧|任由仇人踉跄离去|废了修为放你走|化干戈为玉帛)"
        ],
        "reason": "对曾动杀心的敌人心慈手软，违背网文斩草除根爽感铁律，极度损毁主角智商与立意。",
        "suggestion": "斩草必除根，决不可轻易放走仇敌；若受制于规矩，也应暗中补刀或借刀杀人绝后患。"
    },
    {
        "type": "simp_behavior",
        "name": "降智舔狗倒贴",
        "severity": "fatal",
        "weight": 20,
        "patterns": [
            r"(哪怕你多看我一眼|甘愿做牛做马|只求你不要离开我|即使你喜欢别人我也无怨无悔)",
            r"(把全部家当拱手送给女神|跪求女神原谅|即使被当成备胎也心甘情愿|为了讨她欢心倾家荡产)"
        ],
        "reason": "主角缺乏自尊，对蔑视冷落自己的异性卑躬屈膝，触碰现代读者心理底线。",
        "suggestion": "确立男女角色平等自尊，对方傲慢则主角更绝情冷淡，以实力与独立魅力反向征服。"
    },
    {
        "type": "power_inconsistency",
        "name": "战力断崖崩坏",
        "severity": "critical",
        "weight": 15,
        "patterns": [
            r"(大宗师满街走|金丹多如狗|元婴遍地走|神魔不如狗|曾经以为无敌的.*如今守门)",
            r"(原来之前的至尊强者不过是蝼蚁|前文的神级功法现在沦为废纸)"
        ],
        "reason": "跨地图后战力数值通胀严重，前期读者积累的成就感瞬间贬值破灭。",
        "suggestion": "换地图时以法则、道意或特殊维度压制保持梯度，保持高阶战力的稀缺性与庄严感。"
    },
    {
        "type": "preachy_monologue",
        "name": "长篇生硬说教",
        "severity": "high",
        "weight": 10,
        "patterns": [
            r"(其实人生就是这样|作者认为|在这个物欲横流的社会里|我们每个人都应该明白)",
            r"(社会现实告诉我们|人性的丑恶就在于此|大道理人人都懂)"
        ],
        "reason": "作者脱离剧情亲自下场长篇大论灌输主观价值观，严重打断沉浸感与行文节奏。",
        "suggestion": "将主观议论删除或压缩为一句角色的有力对白金句，让情节事实替作者说话。"
    },
    {
        "type": "distress_trope",
        "name": "核心配角白送人头",
        "severity": "high",
        "weight": 15,
        "patterns": [
            r"(不听劝告偷偷溜出|偏要任性前往|被绑架在废弃仓库|拿你的女人来换)",
            r"(用你全家性命威胁主角自废武功|逼迫主角下跪换取人质安全)"
        ],
        "reason": "工具人式送人头导致剧情狗血生硬，主角被迫受制于人，读者对拖油瓶极度反感。",
        "suggestion": "强化配角自保逻辑，或将救援情节写为主角将计就计的围猎反杀局。"
    },
    {
        "type": "ntr_ambiguity",
        "name": "绿帽擦边情感不洁",
        "severity": "fatal",
        "weight": 30,
        "patterns": [
            r"(依偎在另一个男人怀里|衣衫不整地从房间出来|眼神迷离地拉扯|坐在了男配的腿上)",
            r"(虽然我爱的是你但我身体属于他|为了救你我不得不委身于他)"
        ],
        "reason": "情感背叛或严重暧昧擦边，直接触碰读者的第一禁区，导致毁灭性差评。",
        "suggestion": "严守情感忠诚底线；若有误会，三章内必须彻底廓清并严惩造谣者。"
    },
    {
        "type": "nerfed_powers",
        "name": "金手指莫名被夺削弱",
        "severity": "high",
        "weight": 20,
        "patterns": [
            r"(被宗门长辈强行收走|将宝物暂借给他人保管|无故被小偷盗走|金手指陷入永久休眠)",
            r"(神级外挂被莫名封印|修为被废且金手指失灵|宝物被迫上交家族)"
        ],
        "reason": "主角已获得的底牌被生硬剥夺，剥夺感极强，读者付出沉没成本受挫弃书。",
        "suggestion": "外挂可以有冷却限制或代价，但绝对控制权必须始终在主角手中；如被夺，三章内必须作为反杀诱饵。"
    },
    {
        "type": "broken_promise",
        "name": "言而无信承诺烂尾",
        "severity": "medium",
        "weight": 10,
        "patterns": [
            r"(早就把当年的誓言忘得一干二净|昔日的承诺抛诸脑后|早就忘了还要去救)",
            r"(发过的重誓如今全当耳旁风|随口答应的事从不兑现)"
        ],
        "reason": "主角立誓后抛诸脑后毫无推进，显得人设虚伪冷血，丧失主线目标牵引力。",
        "suggestion": "建立伏笔记账本，阶段性交代主线目标的推进进度，有始有终完成承诺结算。"
    },
    {
        "type": "brainless_antagonist",
        "name": "反派无脑复读找茬",
        "severity": "medium",
        "weight": 10,
        "patterns": [
            r"(你找死！你找死！|你这废物竟敢|给脸不要脸的小畜生|你可知我是谁|信不信我诛你九族)",
            r"(蝼蚁也敢放肆|不知天高地厚的狗东西|跪下磕头饶你不死)"
        ],
        "reason": "反派台词单一廉价复读，毫无动机地为了找茬而找茬，挨打之后毫无长进继续送人头，爽感单薄低俗。",
        "suggestion": "反派动机立足于真实利益争夺；反派反扑要有手段和层级升级，避免复读机式谩骂。"
    }
]

MAX_SCAN_LINES = 10000


def check_poison(text: str) -> dict[str, Any]:
    """对输入文本执行纯本地毒点全维扫描。
    
    Returns:
        {
            "score": int (0-100, 越低越健康，0为全无毒),
            "verdict": str ("安全" / "轻微注意" / "中度预警" / "致命毒点"),
            "total_issues": int,
            "findings": list[dict]
        }
    """
    if not text or not isinstance(text, str):
        return {
            "score": 0,
            "verdict": "文本为空，未发现毒点",
            "total_issues": 0,
            "findings": []
        }

    lines = text.splitlines()[:MAX_SCAN_LINES]
    findings: list[dict[str, Any]] = []
    total_penalty = 0

    for line_idx, line in enumerate(lines, 1):
        clean_line = line.strip()
        if not clean_line:
            continue

        for rule in POISON_PATTERNS:
            for pat in rule["patterns"]:
                m = re.search(pat, clean_line)
                if m:
                    # 截取前后上下文片段
                    start = max(0, m.start() - 15)
                    end = min(len(clean_line), m.end() + 15)
                    snippet = clean_line[start:end]

                    findings.append({
                        "line": line_idx,
                        "type": rule["type"],
                        "type_name": rule["name"],
                        "severity": rule["severity"],
                        "snippet": snippet,
                        "matched": m.group(0),
                        "reason": rule["reason"],
                        "suggestion": rule["suggestion"]
                    })
                    total_penalty += rule["weight"]
                    break  # 避免同一行同一条规则重复计分

    score = min(100, total_penalty)
    if score == 0:
        verdict = "安全：未发现明显弃坑毒点，行文节奏舒畅"
    elif score < 20:
        verdict = "轻微：发现个别潜在敏感词句，建议留意爽点代偿"
    elif score < 50:
        verdict = "警告：存在部分憋屈或送人头情节，容易引起读者弃书"
    else:
        verdict = "危险：检测到高危致命毒点，强烈建议在发布前立即修改！"

    return {
        "score": score,
        "verdict": verdict,
        "total_issues": len(findings),
        "findings": findings
    }
