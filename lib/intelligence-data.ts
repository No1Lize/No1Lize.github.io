import publicArticleData from "../public/data/articles.json";

export type Region = "中国" | "美国" | "全球";
export type EventType =
  | "融资"
  | "产业投资"
  | "产品发布"
  | "技术突破"
  | "政策"
  | "监管文件"
  | "IPO";

export type Source = {
  name: string;
  url: string;
  level: "官方披露" | "原始材料" | "监管文件";
};

export type IntelligenceEvent = {
  id: string;
  title: string;
  summary: string;
  type: EventType;
  region: Region;
  sector: string;
  company: string;
  companySlug?: string;
  publishedAt: string;
  importance: number;
  source: Source;
};

const fallbackIntelligenceEvents: IntelligenceEvent[] = [
  {
    id: "openai-2026-financing",
    title: "OpenAI 完成新一轮融资",
    summary:
      "OpenAI 官方披露完成 1,220 亿美元融资，投后估值为 8,520 亿美元；金额与估值均按公司原始公告记录。",
    type: "融资",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    companySlug: "openai",
    publishedAt: "2026-03-31",
    importance: 100,
    source: {
      name: "OpenAI",
      url: "https://openai.com/index/accelerating-the-next-phase-ai/",
      level: "官方披露",
    },
  },
  {
    id: "figure-series-c",
    title: "Figure Series C 承诺资本超过 10 亿美元",
    summary:
      "Figure 官方披露 Series C 承诺资本超过 10 亿美元，投后估值 390 亿美元，资金将用于通用人形机器人规模化落地。",
    type: "融资",
    region: "美国",
    sector: "机器人",
    company: "Figure AI",
    companySlug: "figure-ai",
    publishedAt: "2025-09-16",
    importance: 93,
    source: {
      name: "Figure AI",
      url: "https://www.figure.ai/news/series-c",
      level: "官方披露",
    },
  },
  {
    id: "figure-brookfield",
    title: "Figure 与 Brookfield 建立机器人数据合作",
    summary:
      "双方将利用 Brookfield 管理的真实空间构建人形机器人预训练数据，Brookfield 同时参与 Figure Series C。",
    type: "产业投资",
    region: "美国",
    sector: "机器人",
    company: "Figure AI",
    companySlug: "figure-ai",
    publishedAt: "2025-09-17",
    importance: 86,
    source: {
      name: "Figure AI",
      url: "https://www.figure.ai/news/figure-announces-strategic-partnership-with-brookfield",
      level: "官方披露",
    },
  },
  {
    id: "openai-stargate",
    title: "Stargate 启动美国 AI 基础设施建设",
    summary:
      "OpenAI、SoftBank、Oracle 与 MGX 宣布成立 Stargate，计划四年投资 5,000 亿美元建设美国 AI 基础设施。",
    type: "产业投资",
    region: "美国",
    sector: "AI / AGI",
    company: "OpenAI",
    companySlug: "openai",
    publishedAt: "2025-01-21",
    importance: 96,
    source: {
      name: "OpenAI",
      url: "https://openai.com/index/announcing-the-stargate-project/",
      level: "官方披露",
    },
  },
  {
    id: "deepseek-r1",
    title: "DeepSeek-R1 以 MIT 许可开源",
    summary:
      "DeepSeek 发布并开源推理模型 DeepSeek-R1，模型权重与技术说明由项目官方仓库公开。",
    type: "技术突破",
    region: "中国",
    sector: "AI / AGI",
    company: "DeepSeek",
    companySlug: "deepseek",
    publishedAt: "2025-01-20",
    importance: 97,
    source: {
      name: "DeepSeek 官方仓库",
      url: "https://github.com/deepseek-ai/DeepSeek-R1",
      level: "原始材料",
    },
  },
  {
    id: "unitree-g1",
    title: "宇树科技发布 Unitree G1 人形智能体",
    summary:
      "Unitree G1 面向人形机器人研发与量产探索，产品参数和演示以公司官方页面为准。",
    type: "产品发布",
    region: "中国",
    sector: "机器人",
    company: "宇树科技",
    companySlug: "unitree",
    publishedAt: "2024-05-13",
    importance: 82,
    source: {
      name: "Unitree Robotics",
      url: "https://www.unitree.com/g1",
      level: "官方披露",
    },
  },
  {
    id: "anthropic-series-f",
    title: "Anthropic 完成 130 亿美元 Series F",
    summary:
      "Anthropic 官方披露 Series F 融资 130 亿美元，投后估值 1,830 亿美元，ICONIQ 领投。",
    type: "融资",
    region: "美国",
    sector: "AI / AGI",
    company: "Anthropic",
    companySlug: "anthropic",
    publishedAt: "2025-09-02",
    importance: 94,
    source: {
      name: "Anthropic",
      url: "https://www.anthropic.com/news/anthropic-raises-series-f-at-usd183b-post-money-valuation",
      level: "官方披露",
    },
  },
  {
    id: "spacex-starship-flight-7",
    title: "SpaceX 更新 Starship 第七次飞行测试结果",
    summary:
      "官方任务页面记录了助推器回收和飞船测试结果，用于持续跟踪商业航天工程进展。",
    type: "技术突破",
    region: "美国",
    sector: "商业航天",
    company: "SpaceX",
    companySlug: "spacex",
    publishedAt: "2025-01-16",
    importance: 84,
    source: {
      name: "SpaceX",
      url: "https://www.spacex.com/launches/mission/?missionId=starship-flight-7",
      level: "原始材料",
    },
  },
];

const generatedDate =
  typeof publicArticleData.generatedAt === "string"
    ? publicArticleData.generatedAt.slice(0, 10)
    : "2026-07-24";

export const snapshotDate = generatedDate;
export const intelligenceEvents: IntelligenceEvent[] =
  (publicArticleData.articles as IntelligenceEvent[]).length > 0
    ? (publicArticleData.articles as IntelligenceEvent[])
    : fallbackIntelligenceEvents;

export type Sector = {
  slug: string;
  name: string;
  heat: number;
  completeness: number;
  trend: "up" | "flat" | "down";
  events: number;
  institutions: number;
  fundingLabel: string;
};

export const sectors: Sector[] = [
  { slug: "ai", name: "AI / AGI", heat: 96, completeness: 92, trend: "up", events: 18, institutions: 14, fundingLabel: "$135B+" },
  { slug: "robotics", name: "机器人", heat: 88, completeness: 84, trend: "up", events: 9, institutions: 11, fundingLabel: "$1B+" },
  { slug: "semiconductor", name: "半导体", heat: 82, completeness: 76, trend: "up", events: 7, institutions: 9, fundingLabel: "部分披露" },
  { slug: "space", name: "商业航天", heat: 76, completeness: 72, trend: "up", events: 6, institutions: 7, fundingLabel: "部分披露" },
  { slug: "biotech", name: "生物科技", heat: 72, completeness: 69, trend: "flat", events: 5, institutions: 8, fundingLabel: "部分披露" },
  { slug: "energy", name: "新能源", heat: 69, completeness: 74, trend: "flat", events: 5, institutions: 8, fundingLabel: "部分披露" },
  { slug: "quantum", name: "量子计算", heat: 66, completeness: 61, trend: "up", events: 4, institutions: 5, fundingLabel: "未完整披露" },
  { slug: "manufacturing", name: "智能制造", heat: 63, completeness: 64, trend: "flat", events: 4, institutions: 6, fundingLabel: "未完整披露" },
  { slug: "materials", name: "新材料", heat: 58, completeness: 55, trend: "flat", events: 3, institutions: 5, fundingLabel: "未完整披露" },
  { slug: "web3", name: "Web3", heat: 51, completeness: 57, trend: "down", events: 3, institutions: 5, fundingLabel: "未完整披露" },
];

export const focusCompanies = [
  { slug: "openai", name: "OpenAI", region: "美国", sector: "AI / AGI", stage: "成长期", focus: "基础模型、开发者平台与 AI 基础设施", verified: "2026-03-31" },
  { slug: "deepseek", name: "DeepSeek", region: "中国", sector: "AI / AGI", stage: "成长期", focus: "开源推理模型与训练效率", verified: "2025-01-20" },
  { slug: "figure-ai", name: "Figure AI", region: "美国", sector: "机器人", stage: "Series C", focus: "通用人形机器人与真实环境数据", verified: "2025-09-17" },
  { slug: "unitree", name: "宇树科技", region: "中国", sector: "机器人", stage: "成长期", focus: "四足与人形机器人产品化", verified: "2024-05-13" },
  { slug: "anthropic", name: "Anthropic", region: "美国", sector: "AI / AGI", stage: "Series F", focus: "可靠、可解释的前沿基础模型", verified: "2025-09-02" },
  { slug: "spacex", name: "SpaceX", region: "美国", sector: "商业航天", stage: "成长期", focus: "可复用运载系统与卫星网络", verified: "2025-01-16" },
];

export const institutions = [
  { name: "Sequoia Capital", region: "美国", focus: "AI / 企业软件", activity: 91 },
  { name: "Andreessen Horowitz", region: "美国", focus: "AI / Web3 / 生物", activity: 89 },
  { name: "Founders Fund", region: "美国", focus: "AI / 国防 / 航天", activity: 84 },
  { name: "Lightspeed", region: "美国", focus: "AI / 企业科技", activity: 82 },
  { name: "红杉中国", region: "中国", focus: "科技 / 医疗 / 消费", activity: 87 },
  { name: "IDG 资本", region: "中国", focus: "硬科技 / 企业服务", activity: 81 },
  { name: "高瓴", region: "中国", focus: "科技 / 医疗 / 制造", activity: 79 },
  { name: "启明创投", region: "中国", focus: "医疗 / TMT", activity: 77 },
];

export const heatMethodology =
  "HeatScore = 30% 融资活跃度 + 20% 头部机构参与度 + 20% 重要事件活跃度 + 15% IPO 活跃度 + 15% 研究与政策活跃度。各子项按当前快照样本做 0–100 归一化；完整度低于 70% 的赛道不显示推算融资总额。";
