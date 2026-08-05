import type { Source } from "./intelligence-data";

export type Company = {
  slug: string;
  name: string;
  englishName?: string;
  region: string;
  sector: string;
  stage: string;
  status: "运营中" | "已上市";
  founded?: string;
  headquarters?: string;
  summary: string;
  product: string;
  source: Source;
  confidence: number;
};

const official = (name: string, url: string): Source => ({
  name,
  url,
  level: "官方披露",
});

export { companies } from "./company-registry";

export type Institution = {
  slug: string;
  name: string;
  englishName?: string;
  region: "中国" | "美国";
  type: string;
  stages: string;
  sectors: string[];
  source: Source;
};

export const institutionCatalog: Institution[] = [
  { slug:"sequoia-capital", name:"Sequoia Capital", region:"美国", type:"风险投资", stages:"全阶段", sectors:["AI","企业科技","消费"], source:official("Sequoia Capital","https://www.sequoiacap.com/") },
  { slug:"a16z", name:"Andreessen Horowitz", region:"美国", type:"风险投资", stages:"种子至成长期", sectors:["AI","企业科技","生物科技","Web3"], source:official("a16z","https://a16z.com/") },
  { slug:"benchmark", name:"Benchmark", region:"美国", type:"风险投资", stages:"早期", sectors:["软件","AI","互联网"], source:official("Benchmark","https://www.benchmark.com/") },
  { slug:"kleiner-perkins", name:"Kleiner Perkins", region:"美国", type:"风险投资", stages:"早期至成长期", sectors:["企业科技","消费","医疗"], source:official("Kleiner Perkins","https://www.kleinerperkins.com/") },
  { slug:"founders-fund", name:"Founders Fund", region:"美国", type:"风险投资", stages:"早期至成长期", sectors:["AI","国防科技","商业航天"], source:official("Founders Fund","https://foundersfund.com/") },
  { slug:"yc", name:"Y Combinator", region:"美国", type:"加速器/投资机构", stages:"种子期", sectors:["科技创业"], source:official("Y Combinator","https://www.ycombinator.com/companies") },
  { slug:"lightspeed", name:"Lightspeed Venture Partners", region:"美国", type:"风险投资", stages:"全阶段", sectors:["企业科技","消费","医疗"], source:official("Lightspeed","https://lsvp.com/") },
  { slug:"greylock", name:"Greylock Partners", region:"美国", type:"风险投资", stages:"早期", sectors:["AI","企业软件","消费"], source:official("Greylock","https://greylock.com/") },
  { slug:"general-catalyst", name:"General Catalyst", region:"美国", type:"风险投资", stages:"全阶段", sectors:["AI","医疗","工业"], source:official("General Catalyst","https://www.generalcatalyst.com/") },
  { slug:"khosla", name:"Khosla Ventures", region:"美国", type:"风险投资", stages:"早期至成长期", sectors:["AI","气候科技","医疗"], source:official("Khosla Ventures","https://www.khoslaventures.com/") },
  { slug:"hongshan", name:"红杉中国", englishName:"HongShan", region:"中国", type:"风险投资", stages:"全阶段", sectors:["科技","医疗","消费"], source:official("红杉中国","https://www.hongshan.com/") },
  { slug:"idg-capital", name:"IDG 资本", region:"中国", type:"风险投资", stages:"全阶段", sectors:["硬科技","企业服务","消费"], source:official("IDG 资本","https://www.idgcapital.com/") },
  { slug:"hillhouse", name:"高瓴", englishName:"Hillhouse", region:"中国", type:"投资机构", stages:"全阶段", sectors:["科技","医疗","先进制造"], source:official("高瓴","https://www.hillhouseinvestment.com/") },
  { slug:"qiming", name:"启明创投", englishName:"Qiming Venture Partners", region:"中国", type:"风险投资", stages:"早期至成长期", sectors:["医疗","TMT"], source:official("启明创投","https://www.qimingvc.com/") },
  { slug:"matrix-china", name:"经纬创投", region:"中国", type:"风险投资", stages:"早期", sectors:["科技","医疗","消费"], source:official("经纬创投","https://www.matrixpartners.com.cn/") },
  { slug:"zhenfund", name:"真格基金", englishName:"ZhenFund", region:"中国", type:"早期投资", stages:"天使/种子", sectors:["科技创业","消费","企业服务"], source:official("真格基金","https://www.zhenfund.com/") },
  { slug:"legend-capital", name:"君联资本", englishName:"Legend Capital", region:"中国", type:"风险投资", stages:"全阶段", sectors:["科技","医疗","消费"], source:official("君联资本","https://www.legendcapital.com.cn/") },
  { slug:"fortune-capital", name:"达晨财智", englishName:"Fortune Capital", region:"中国", type:"风险投资", stages:"成长期", sectors:["硬科技","先进制造","医疗"], source:official("达晨财智","https://www.fortunevc.com/") },
  { slug:"scgc", name:"深创投", englishName:"SCGC", region:"中国", type:"国有创投", stages:"全阶段", sectors:["硬科技","制造","医疗"], source:official("深创投","https://www.szvc.com.cn/") },
  { slug:"gaorong", name:"高榕创投", englishName:"Gaorong Ventures", region:"中国", type:"风险投资", stages:"早期至成长期", sectors:["科技","消费","企业服务"], source:official("高榕创投","https://www.gaorongcapital.com/") },
];

export type IpoCompany = {
  slug: string;
  name: string;
  market: "A股" | "港股" | "美股";
  ticker: string;
  sector: string;
  status: string;
  latest: string;
  source: Source;
};

export const ipoCompanies: IpoCompany[] = [
  { slug:"cambricon", name:"寒武纪", market:"A股", ticker:"688256", sector:"半导体", status:"已上市·科创板", latest:"持续披露定期报告", source:official("上海证券交易所","https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=688256") },
  { slug:"catl", name:"宁德时代", market:"A股", ticker:"300750", sector:"新能源", status:"已上市·创业板", latest:"持续披露定期报告", source:official("深圳证券交易所","https://www.szse.cn/") },
  { slug:"bgi-genomics", name:"华大基因", market:"A股", ticker:"300676", sector:"生物科技", status:"已上市·创业板", latest:"持续披露定期报告", source:official("深圳证券交易所","https://www.szse.cn/") },
  { slug:"horizon-robotics", name:"地平线机器人", market:"港股", ticker:"09660", sector:"半导体", status:"已上市·主板", latest:"持续披露公告与财报", source:official("香港交易所披露易","https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh") },
  { slug:"xtalpi", name:"晶泰科技", market:"港股", ticker:"02228", sector:"生物科技", status:"已上市·特专科技", latest:"持续披露公告与财报", source:official("香港交易所披露易","https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh") },
  { slug:"pony-ai", name:"小马智行", market:"美股", ticker:"PONY", sector:"机器人", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1969302",level:"监管文件"} },
  { slug:"weride", name:"文远知行", market:"美股", ticker:"WRD", sector:"机器人", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/search/",level:"监管文件"} },
  { slug:"rigetti", name:"Rigetti Computing", market:"美股", ticker:"RGTI", sector:"量子计算", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1838359",level:"监管文件"} },
  { slug:"ionq", name:"IonQ", market:"美股", ticker:"IONQ", sector:"量子计算", status:"已上市·NYSE", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1824920",level:"监管文件"} },
  { slug:"rocket-lab", name:"Rocket Lab", market:"美股", ticker:"RKLB", sector:"商业航天", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1819994",level:"监管文件"} },
  { slug:"tempus-ai", name:"Tempus AI", market:"美股", ticker:"TEM", sector:"生物科技", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/search/",level:"监管文件"} },
  { slug:"recursion", name:"Recursion Pharmaceuticals", market:"美股", ticker:"RXRX", sector:"生物科技", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1601830",level:"监管文件"} },
  { slug:"mobileye", name:"Mobileye", market:"美股", ticker:"MBLY", sector:"半导体", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1910139",level:"监管文件"} },
  { slug:"aurora", name:"Aurora Innovation", market:"美股", ticker:"AUR", sector:"机器人", status:"已上市·NASDAQ", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1828108",level:"监管文件"} },
  { slug:"joby", name:"Joby Aviation", market:"美股", ticker:"JOBY", sector:"商业航天", status:"已上市·NYSE", latest:"持续提交 SEC 文件", source:{name:"SEC EDGAR",url:"https://www.sec.gov/edgar/browse/?CIK=1819848",level:"监管文件"} },
];

export const reports = [
  { slug:"ai-capital-2026", type:"中美对照", title:"前沿 AI 资本开支与融资：公开披露口径", summary:"区分企业融资、基础设施承诺和基金投入，避免将不同口径直接相加。", date:"2026-04-03", sources:4, tags:["AI","中美","资本"] },
  { slug:"humanoid-robotics", type:"赛道研究", title:"人形机器人：从本体融资走向真实环境数据", summary:"跟踪 Figure、宇树科技与中国具身智能公司的产品和数据闭环。", date:"2025-09-20", sources:8, tags:["机器人","具身智能"] },
  { slug:"ai-chips", type:"赛道研究", title:"AI 芯片供给侧：训练、推理与国产 GPU 路线", summary:"从产品定位和公开披露拆分训练、推理与边缘计算路线。", date:"2025-08-15", sources:11, tags:["半导体","AI"] },
  { slug:"space-commercialization", type:"赛道研究", title:"商业航天的验证顺序：火箭、任务与现金流", summary:"以官方任务记录为主线，区分技术成功、订单与规模化收入。", date:"2025-06-10", sources:9, tags:["商业航天"] },
  { slug:"autonomous-driving", type:"公司与产业研究", title:"Robotaxi 商业化：车队、订单与城市复制", summary:"对照小马智行、文远知行、Aurora 与 Mobileye 的运营、前装和资本市场验证路径。", date:"2026-07-24", sources:10, tags:["机器人","自动驾驶","上市公司"] },
];

export type Person = {
  slug: string;
  name: string;
  englishName: string;
  role: string;
  concepts: string[];
  summary: string;
  materials: { title: string; date: string; type: string; url: string; source: string }[];
};

export const people: Person[] = [
  {
    slug:"warren-buffett", name:"沃伦·巴菲特", englishName:"Warren Buffett", role:"Berkshire Hathaway 董事长",
    concepts:["能力圈","护城河","安全边际","浮存金","复利"],
    summary:"长期通过股东信和股东大会解释资本配置、企业质量与投资纪律。",
    materials:[
      {title:"2024 Annual Letter",date:"2025-02-22",type:"shareholder_letter",url:"https://www.berkshirehathaway.com/letters/2024ltr.pdf",source:"Berkshire Hathaway"},
      {title:"2023 Annual Letter",date:"2024-02-24",type:"shareholder_letter",url:"https://www.berkshirehathaway.com/letters/2023ltr.pdf",source:"Berkshire Hathaway"},
      {title:"2022 Annual Letter",date:"2023-02-25",type:"shareholder_letter",url:"https://www.berkshirehathaway.com/letters/2022ltr.pdf",source:"Berkshire Hathaway"},
      {title:"2021 Annual Letter",date:"2022-02-26",type:"shareholder_letter",url:"https://www.berkshirehathaway.com/letters/2021ltr.pdf",source:"Berkshire Hathaway"},
      {title:"2020 Annual Letter",date:"2021-02-27",type:"shareholder_letter",url:"https://www.berkshirehathaway.com/letters/2020ltr.pdf",source:"Berkshire Hathaway"},
    ],
  },
  {
    slug:"charlie-munger", name:"查理·芒格", englishName:"Charlie Munger", role:"Berkshire Hathaway 前副董事长",
    concepts:["多元思维模型","逆向思维","误判心理学","激励机制"],
    summary:"强调跨学科思维模型、避免心理偏误，以及以长期理性约束投资与经营决策。",
    materials:[
      {title:"A Lesson on Elementary, Worldly Wisdom",date:"1994",type:"speech",url:"https://fs.blog/great-talks/a-lesson-on-worldly-wisdom/",source:"USC Business School / transcript archive"},
      {title:"The Psychology of Human Misjudgment",date:"1995",type:"speech",url:"https://fs.blog/great-talks/psychology-human-misjudgment/",source:"Harvard Law School / transcript archive"},
      {title:"Poor Charlie's Almanack",date:"2005",type:"compiled_work",url:"https://www.stripe.press/poor-charlies-almanack",source:"Stripe Press"},
      {title:"Berkshire 2023 Annual Letter: Charlie Munger tribute",date:"2024-02-24",type:"commentary",url:"https://www.berkshirehathaway.com/letters/2023ltr.pdf",source:"Berkshire Hathaway"},
      {title:"Daily Journal Corporation filings",date:"2023",type:"public_document",url:"https://www.sec.gov/edgar/browse/?CIK=783412",source:"SEC EDGAR"},
    ],
  },
  {
    slug:"duan-yongping", name:"段永平", englishName:"Duan Yongping", role:"企业家、投资人",
    concepts:["本分","平常心","做对的事","Stop Doing List"],
    summary:"公开讨论企业文化、消费者导向、能力圈和长期主义；转载与本人发言需严格区分。",
    materials:[
      {title:"雪球公开主页与发言",date:"持续更新",type:"public_post",url:"https://xueqiu.com/1247347556",source:"雪球·大道无形我有型"},
      {title:"浙江大学公开课相关材料",date:"2025",type:"qa",url:"https://www.zju.edu.cn/",source:"浙江大学"},
      {title:"OPPO 关于“本分”企业文化",date:"持续更新",type:"compiled_work",url:"https://www.oppo.com/cn/about/",source:"OPPO"},
      {title:"vivo 企业文化与价值观",date:"持续更新",type:"compiled_work",url:"https://www.vivo.com.cn/about-vivo/culture",source:"vivo"},
      {title:"网易公司投资公开文件",date:"2006",type:"public_document",url:"https://ir.netease.com/",source:"NetEase Investor Relations"},
    ],
  },
  {
    slug:"li-lu", name:"李录", englishName:"Li Lu", role:"Himalaya Capital 创始人",
    concepts:["文明演进","现代化","价值投资在中国","能力圈扩展"],
    summary:"从文明与现代化框架讨论长期经济发展，并将价值投资方法应用于企业研究。",
    materials:[
      {title:"The Prospects for Value Investing in China",date:"2015",type:"speech",url:"https://www.himalayacapital.com/letters/",source:"Himalaya Capital"},
      {title:"Reflections on the Next Twenty Years",date:"2020",type:"article",url:"https://www.himalayacapital.com/letters/",source:"Himalaya Capital"},
      {title:"Himalaya Capital – Our Approach",date:"持续更新",type:"public_post",url:"https://www.himalayacapital.com/",source:"Himalaya Capital"},
      {title:"Columbia Business School lecture archive",date:"2006",type:"speech",url:"https://www8.gsb.columbia.edu/valueinvesting/",source:"Columbia Business School"},
      {title:"Poor Charlie's Almanack foreword/context",date:"2005",type:"commentary",url:"https://www.stripe.press/poor-charlies-almanack",source:"Stripe Press"},
    ],
  },
  {
    slug:"kaiming-he", name:"何恺明", englishName:"Kaiming He", role:"MIT 教授、AI 研究者",
    concepts:["深度残差学习","实例分割","自监督学习","可扩展视觉表征"],
    summary:"围绕计算机视觉、深度学习与自监督表征提出多项基础方法，材料以论文和个人学术主页为主。",
    materials:[
      {title:"Kaiming He — Academic Homepage",date:"持续更新",type:"public_post",url:"https://people.csail.mit.edu/kaiming/",source:"MIT CSAIL"},
      {title:"Deep Residual Learning for Image Recognition",date:"2015-12-10",type:"authored_work",url:"https://arxiv.org/abs/1512.03385",source:"arXiv"},
      {title:"Mask R-CNN",date:"2017-03-20",type:"authored_work",url:"https://arxiv.org/abs/1703.06870",source:"arXiv"},
      {title:"Masked Autoencoders Are Scalable Vision Learners",date:"2021-11-11",type:"authored_work",url:"https://arxiv.org/abs/2111.06377",source:"arXiv"},
      {title:"Kaiming He publications",date:"持续更新",type:"public_document",url:"https://people.csail.mit.edu/kaiming/publications.html",source:"MIT CSAIL"},
      {title:"Kaiming He on X",date:"持续更新",type:"public_post",url:"https://x.com/kaiminghe",source:"X"},
    ],
  },
  {
    slug:"shunyu-yao", name:"姚顺雨", englishName:"Shunyu Yao", role:"AI 研究者",
    concepts:["ReAct","Tree of Thoughts","智能体评测","The Second Half"],
    summary:"研究语言模型推理、行动与软件智能体，持续讨论从预训练扩展到真实任务学习与评测的方法。",
    materials:[
      {title:"Shunyu Yao — Homepage",date:"持续更新",type:"public_post",url:"https://ysymyth.github.io/",source:"个人学术主页"},
      {title:"ReAct: Synergizing Reasoning and Acting in Language Models",date:"2022-10-06",type:"authored_work",url:"https://arxiv.org/abs/2210.03629",source:"arXiv"},
      {title:"Tree of Thoughts: Deliberate Problem Solving with Large Language Models",date:"2023-05-17",type:"authored_work",url:"https://arxiv.org/abs/2305.10601",source:"arXiv"},
      {title:"SWE-bench: Can Language Models Resolve Real-World GitHub Issues?",date:"2023-10-10",type:"authored_work",url:"https://arxiv.org/abs/2310.06770",source:"arXiv"},
      {title:"The Second Half",date:"2025",type:"article",url:"https://ysymyth.github.io/The-Second-Half/",source:"个人学术主页"},
      {title:"Shunyu Yao on X",date:"持续更新",type:"public_post",url:"https://x.com/ShunyuYao12",source:"X"},
    ],
  },
];
