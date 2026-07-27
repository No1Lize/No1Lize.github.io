import type { Source } from "./intelligence-data";

export type Company = {
  slug: string;
  name: string;
  englishName?: string;
  region: "中国" | "美国";
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

export const companies: Company[] = [
  { slug:"google", name:"Google", region:"美国", sector:"AI / AGI", stage:"已上市", status:"已上市", founded:"1998", headquarters:"Mountain View", summary:"开发搜索、云计算、人工智能与面向消费者和企业的软件服务。", product:"Google Search、Google Cloud、Gemini 与相关 AI 产品。", source:official("Google","https://about.google/"), confidence:0.99 },
  { slug:"openai", name:"OpenAI", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2015", headquarters:"San Francisco", summary:"开发通用人工智能模型、开发者平台与面向个人和企业的 AI 产品。", product:"基础模型、ChatGPT、API 与智能体开发工具。", source:official("OpenAI","https://openai.com/about/"), confidence:0.98 },
  { slug:"anthropic", name:"Anthropic", region:"美国", sector:"AI / AGI", stage:"Series F", status:"运营中", founded:"2021", headquarters:"San Francisco", summary:"以可靠性、可解释性与安全研究为重点的前沿 AI 公司。", product:"Claude 模型、企业 API 与安全研究。", source:official("Anthropic","https://www.anthropic.com/company"), confidence:0.98 },
  { slug:"figure-ai", name:"Figure AI", region:"美国", sector:"机器人", stage:"Series C", status:"运营中", founded:"2022", headquarters:"California", summary:"研发面向真实工作和生活环境的通用人形机器人。", product:"Figure 人形机器人与 Helix 视觉—语言—行动模型。", source:official("Figure AI","https://www.figure.ai/"), confidence:0.97 },
  { slug:"spacex", name:"SpaceX", region:"美国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2002", headquarters:"Texas", summary:"研发可复用运载系统、载人航天器与卫星互联网。", product:"Falcon、Dragon、Starship 与 Starlink。", source:official("SpaceX","https://www.spacex.com/"), confidence:0.99 },
  { slug:"rocket-lab", name:"Rocket Lab", region:"美国", sector:"商业航天", stage:"已上市", status:"已上市", founded:"2006", headquarters:"California", summary:"提供小型运载发射、卫星平台、航天器部件和任务服务。", product:"Electron、HASTE、Photon 航天器与 Neutron 运载系统。", source:official("Rocket Lab","https://www.rocketlabusa.com/about/about-us/"), confidence:0.99 },
  { slug:"xai", name:"xAI", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2023", headquarters:"United States", summary:"开发基础模型、算力基础设施与面向消费者的 AI 产品。", product:"Grok 模型及相关开发者服务。", source:official("xAI","https://x.ai/company"), confidence:0.96 },
  { slug:"scale-ai", name:"Scale AI", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2016", headquarters:"San Francisco", summary:"为 AI 模型开发提供数据、评测与企业应用基础设施。", product:"数据标注、模型评测和企业生成式 AI 平台。", source:official("Scale AI","https://scale.com/about"), confidence:0.96 },
  { slug:"databricks", name:"Databricks", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2013", headquarters:"San Francisco", summary:"提供统一数据、分析与 AI 平台。", product:"Lakehouse、数据治理与机器学习工具。", source:official("Databricks","https://www.databricks.com/company/about-us"), confidence:0.97 },
  { slug:"perplexity", name:"Perplexity", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2022", headquarters:"San Francisco", summary:"提供带来源引用的 AI 搜索与研究产品。", product:"AI 搜索、研究与企业知识检索。", source:official("Perplexity","https://www.perplexity.ai/about"), confidence:0.95 },
  { slug:"anduril", name:"Anduril Industries", region:"美国", sector:"智能制造", stage:"成长期", status:"运营中", founded:"2017", headquarters:"California", summary:"开发自主系统、传感器和国防软件平台。", product:"Lattice 平台与多类自主飞行器。", source:official("Anduril","https://www.anduril.com/"), confidence:0.96 },
  { slug:"shield-ai", name:"Shield AI", region:"美国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2015", headquarters:"San Diego", summary:"开发面向航空器的自主驾驶软件和无人系统。", product:"Hivemind 自主系统与 V-BAT 飞行器。", source:official("Shield AI","https://shield.ai/"), confidence:0.96 },
  { slug:"sierra", name:"Sierra", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2023", headquarters:"San Francisco", summary:"为企业客户服务场景构建 AI 智能体平台。", product:"企业级客户体验智能体。", source:official("Sierra","https://sierra.ai/"), confidence:0.93 },
  { slug:"harvey", name:"Harvey", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2022", headquarters:"San Francisco", summary:"面向律师事务所和企业法务提供生成式 AI 工作平台。", product:"法律研究、文档分析与工作流自动化。", source:official("Harvey","https://www.harvey.ai/"), confidence:0.95 },
  { slug:"glean", name:"Glean", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2019", headquarters:"California", summary:"构建企业搜索、知识发现与 AI 助手平台。", product:"企业搜索与工作场景智能体。", source:official("Glean","https://www.glean.com/about"), confidence:0.95 },
  { slug:"cerebras", name:"Cerebras Systems", region:"美国", sector:"半导体", stage:"Pre-IPO", status:"运营中", founded:"2016", headquarters:"California", summary:"研发面向 AI 训练和推理的晶圆级计算系统。", product:"Wafer Scale Engine 与 AI 超算系统。", source:official("Cerebras","https://www.cerebras.ai/company"), confidence:0.97 },
  { slug:"groq", name:"Groq", region:"美国", sector:"半导体", stage:"成长期", status:"运营中", founded:"2016", headquarters:"California", summary:"研发面向低延迟 AI 推理的 LPU 架构和云服务。", product:"LPU 推理芯片与 GroqCloud。", source:official("Groq","https://groq.com/about-us"), confidence:0.96 },
  { slug:"sambanova", name:"SambaNova Systems", englishName:"SambaNova", region:"美国", sector:"半导体", stage:"成长期", status:"运营中", founded:"2017", headquarters:"California", summary:"提供企业级 AI 芯片、系统和模型服务。", product:"DataScale 系统与企业 AI 云。", source:official("SambaNova","https://sambanova.ai/about"), confidence:0.94 },
  { slug:"psiquantum", name:"PsiQuantum", region:"美国", sector:"量子计算", stage:"成长期", status:"运营中", founded:"2016", headquarters:"California", summary:"以光子路线开发容错量子计算系统。", product:"硅光子量子计算架构。", source:official("PsiQuantum","https://www.psiquantum.com/"), confidence:0.95 },
  { slug:"rigetti", name:"Rigetti Computing", region:"美国", sector:"量子计算", stage:"已上市", status:"已上市", founded:"2013", headquarters:"California", summary:"研发超导量子处理器并提供云端量子计算服务。", product:"超导量子芯片与 Quantum Cloud Services。", source:official("Rigetti","https://www.rigetti.com/"), confidence:0.97 },
  { slug:"ionq", name:"IonQ", region:"美国", sector:"量子计算", stage:"已上市", status:"已上市", founded:"2015", headquarters:"Maryland", summary:"开发离子阱量子计算系统，并通过云平台和直接系统访问提供服务。", product:"离子阱量子计算机、云访问与量子网络技术。", source:official("IonQ","https://ionq.com/company"), confidence:0.99 },
  { slug:"helion", name:"Helion Energy", region:"美国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2013", headquarters:"Washington", summary:"研发基于脉冲磁约束路线的聚变发电系统。", product:"聚变原型机与发电系统。", source:official("Helion","https://www.helionenergy.com/"), confidence:0.94 },
  { slug:"commonwealth-fusion", name:"Commonwealth Fusion Systems", region:"美国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2018", headquarters:"Massachusetts", summary:"开发高温超导磁体和紧凑型托卡马克聚变装置。", product:"SPARC 与 ARC 聚变系统。", source:official("CFS","https://cfs.energy/"), confidence:0.96 },
  { slug:"redwood-materials", name:"Redwood Materials", region:"美国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2017", headquarters:"Nevada", summary:"建设电池材料回收与闭环供应链。", product:"电池回收、正极材料与铜箔。", source:official("Redwood Materials","https://www.redwoodmaterials.com/"), confidence:0.96 },
  { slug:"form-energy", name:"Form Energy", region:"美国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2017", headquarters:"Massachusetts", summary:"开发面向电网长时储能的铁空气电池。", product:"多日储能系统。", source:official("Form Energy","https://formenergy.com/"), confidence:0.96 },
  { slug:"relativity-space", name:"Relativity Space", region:"美国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2015", headquarters:"California", summary:"开发面向商业发射的可重复使用运载火箭。", product:"Terran R 运载系统。", source:official("Relativity Space","https://www.relativityspace.com/"), confidence:0.95 },
  { slug:"axiom-space", name:"Axiom Space", region:"美国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2016", headquarters:"Texas", summary:"开展商业载人航天任务并建设商业空间站模块。", product:"Axiom Station 与私人宇航任务。", source:official("Axiom Space","https://www.axiomspace.com/"), confidence:0.96 },
  { slug:"varda", name:"Varda Space Industries", region:"美国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2020", headquarters:"California", summary:"利用在轨环境开展材料与药物制造并回收产品。", product:"在轨制造卫星与返回舱。", source:official("Varda","https://www.varda.com/"), confidence:0.94 },
  { slug:"joby", name:"Joby Aviation", region:"美国", sector:"商业航天", stage:"已上市", status:"已上市", founded:"2009", headquarters:"California", summary:"研发电动垂直起降飞行器并筹备商业空中出行服务。", product:"eVTOL 飞行器、认证与空中出行运营体系。", source:official("Joby Aviation","https://www.jobyaviation.com/about/"), confidence:0.99 },
  { slug:"aurora", name:"Aurora Innovation", region:"美国", sector:"机器人", stage:"已上市", status:"已上市", founded:"2017", headquarters:"Pennsylvania", summary:"开发面向卡车运输和出行服务的自动驾驶系统。", product:"Aurora Driver 自动驾驶软硬件系统。", source:official("Aurora","https://aurora.tech/company"), confidence:0.99 },
  { slug:"mobileye", name:"Mobileye", region:"美国", sector:"半导体", stage:"已上市", status:"已上市", founded:"1999", headquarters:"Jerusalem", summary:"提供高级辅助驾驶芯片、感知软件、地图和自动驾驶方案。", product:"EyeQ 芯片、SuperVision、REM 地图与 Chauffeur。", source:official("Mobileye","https://www.mobileye.com/about/"), confidence:0.99 },
  { slug:"tempus-ai", name:"Tempus AI", region:"美国", sector:"生物科技", stage:"已上市", status:"已上市", founded:"2015", headquarters:"Chicago", summary:"将临床与分子数据用于精准医疗、诊断和 AI 辅助决策。", product:"基因检测、临床数据平台与医疗 AI 应用。", source:official("Tempus","https://www.tempus.com/about-us/"), confidence:0.99 },
  { slug:"recursion", name:"Recursion Pharmaceuticals", region:"美国", sector:"生物科技", stage:"已上市", status:"已上市", founded:"2013", headquarters:"Salt Lake City", summary:"结合自动化实验、计算生物学和机器学习推进药物发现。", product:"Recursion OS 研发平台与自有药物管线。", source:official("Recursion","https://www.recursion.com/about"), confidence:0.99 },
  { slug:"deepseek", name:"DeepSeek", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2023", headquarters:"杭州", summary:"研发通用基础模型、代码模型和推理模型，并开放多项模型权重。", product:"DeepSeek 系列大语言模型与 API。", source:official("DeepSeek","https://www.deepseek.com/"), confidence:0.98 },
  { slug:"unitree", name:"宇树科技", englishName:"Unitree Robotics", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2016", headquarters:"杭州", summary:"研发四足机器人、人形机器人及其运动控制系统。", product:"Go、B2、H1 与 G1 系列机器人。", source:official("宇树科技","https://www.unitree.com/"), confidence:0.98 },
  { slug:"zhipu-ai", name:"智谱AI", englishName:"Zhipu AI", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2019", headquarters:"北京", summary:"研发 GLM 系列基础模型与企业级大模型平台。", product:"GLM 模型、智谱清言与开放平台。", source:official("智谱AI","https://www.zhipuai.cn/"), confidence:0.97 },
  { slug:"moonshot-ai", name:"月之暗面", englishName:"Moonshot AI", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2023", headquarters:"北京", summary:"研发长上下文基础模型和面向个人的 AI 助手。", product:"Kimi 智能助手与开放平台。", source:official("Moonshot AI","https://www.moonshot.cn/"), confidence:0.96 },
  { slug:"minimax", name:"MiniMax", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2021", headquarters:"上海", summary:"研发文本、语音和视频等多模态基础模型。", product:"多模态模型、开放平台与 AI 原生应用。", source:official("MiniMax","https://www.minimaxi.com/"), confidence:0.96 },
  { slug:"baichuan-ai", name:"百川智能", englishName:"Baichuan AI", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2023", headquarters:"北京", summary:"研发通用基础模型并探索医疗等垂直应用。", product:"Baichuan 系列模型与行业解决方案。", source:official("百川智能","https://www.baichuan-ai.com/"), confidence:0.95 },
  { slug:"stepfun", name:"阶跃星辰", englishName:"StepFun", region:"中国", sector:"AI / AGI", stage:"成长期", status:"运营中", founded:"2023", headquarters:"上海", summary:"研发语言、语音、图像和视频多模态模型。", product:"Step 系列基础模型与开放平台。", source:official("阶跃星辰","https://www.stepfun.com/"), confidence:0.94 },
  { slug:"biren", name:"壁仞科技", englishName:"Biren Technology", region:"中国", sector:"半导体", stage:"成长期", status:"运营中", founded:"2019", headquarters:"上海", summary:"研发面向通用计算和 AI 的高性能 GPU。", product:"BR 系列通用 GPU 与软件平台。", source:official("壁仞科技","https://www.birentech.com/"), confidence:0.96 },
  { slug:"moore-threads", name:"摩尔线程", englishName:"Moore Threads", region:"中国", sector:"半导体", stage:"成长期", status:"运营中", founded:"2020", headquarters:"北京", summary:"研发全功能 GPU 芯片及软硬件平台。", product:"MTT GPU、驱动与计算平台。", source:official("摩尔线程","https://www.mthreads.com/"), confidence:0.96 },
  { slug:"cambricon", name:"寒武纪", englishName:"Cambricon", region:"中国", sector:"半导体", stage:"已上市", status:"已上市", founded:"2016", headquarters:"北京", summary:"研发云端、边缘端 AI 芯片和基础系统软件。", product:"思元系列智能芯片与软件栈。", source:official("寒武纪","https://www.cambricon.com/"), confidence:0.99 },
  { slug:"horizon-robotics", name:"地平线机器人", englishName:"Horizon Robotics", region:"中国", sector:"半导体", stage:"已上市", status:"已上市", founded:"2015", headquarters:"北京", summary:"提供乘用车高级辅助驾驶计算方案。", product:"征程系列芯片与驾驶软件。", source:official("地平线","https://www.horizon.auto/"), confidence:0.98 },
  { slug:"pony-ai", name:"小马智行", englishName:"Pony.ai", region:"中国", sector:"机器人", stage:"已上市", status:"已上市", founded:"2016", headquarters:"广州", summary:"研发自动驾驶系统并运营 Robotaxi 与 Robotruck 业务。", product:"自动驾驶软硬件系统与运营平台。", source:official("Pony.ai","https://www.pony.ai/"), confidence:0.98 },
  { slug:"weride", name:"文远知行", englishName:"WeRide", region:"中国", sector:"机器人", stage:"已上市", status:"已上市", founded:"2017", headquarters:"广州", summary:"开发多场景 L4 自动驾驶产品和运营服务。", product:"Robotaxi、Robobus、Robosweeper 与 Robovan。", source:official("WeRide","https://www.weride.ai/"), confidence:0.98 },
  { slug:"xpeng-aeroht", name:"小鹏汇天", englishName:"XPENG AEROHT", region:"中国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2013", headquarters:"广州", summary:"研发面向低空出行的飞行汽车产品。", product:"分体式飞行汽车与电动垂直起降飞行器。", source:official("小鹏汇天","https://www.aeroht.com/"), confidence:0.95 },
  { slug:"landspace", name:"蓝箭航天", englishName:"LandSpace", region:"中国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2015", headquarters:"北京", summary:"研发液体燃料商业运载火箭及发动机。", product:"朱雀系列运载火箭。", source:official("蓝箭航天","https://www.landspace.com/"), confidence:0.97 },
  { slug:"galactic-energy", name:"星河动力", englishName:"Galactic Energy", region:"中国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2018", headquarters:"北京", summary:"研发固体与液体商业运载火箭。", product:"谷神星与智神星系列运载火箭。", source:official("星河动力","http://www.galactic-energy.cn/"), confidence:0.95 },
  { slug:"origin-space", name:"起源太空", englishName:"Origin Space", region:"中国", sector:"商业航天", stage:"成长期", status:"运营中", founded:"2017", headquarters:"深圳", summary:"研发空间资源探测与在轨服务相关技术。", product:"空间望远镜、机器人和任务服务。", source:official("起源太空","https://www.origin.space/"), confidence:0.91 },
  { slug:"catl", name:"宁德时代", englishName:"CATL", region:"中国", sector:"新能源", stage:"已上市", status:"已上市", founded:"2011", headquarters:"宁德", summary:"研发动力电池、储能电池和相关电池材料体系。", product:"动力电池、储能系统与电池服务。", source:official("CATL","https://www.catl.com/"), confidence:0.99 },
  { slug:"envision-energy", name:"远景能源", englishName:"Envision Energy", region:"中国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2007", headquarters:"上海", summary:"提供风电、储能和零碳能源解决方案。", product:"智能风机、储能系统与能源管理。", source:official("远景能源","https://www.envision-group.com/"), confidence:0.97 },
  { slug:"svlot", name:"蜂巢能源", englishName:"SVOLT", region:"中国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2018", headquarters:"常州", summary:"研发动力电池和储能电池产品。", product:"电芯、模组、电池包与储能系统。", source:official("蜂巢能源","https://www.svolt.cn/"), confidence:0.95 },
  { slug:"xtalpi", name:"晶泰科技", englishName:"XtalPi", region:"中国", sector:"生物科技", stage:"已上市", status:"已上市", founded:"2015", headquarters:"深圳", summary:"使用 AI、量子物理与自动化实验推动药物和材料研发。", product:"智能药物研发平台与自动化实验室。", source:official("晶泰科技","https://www.xtalpi.com/"), confidence:0.97 },
  { slug:"bgi-genomics", name:"华大基因", englishName:"BGI Genomics", region:"中国", sector:"生物科技", stage:"已上市", status:"已上市", founded:"1999", headquarters:"深圳", summary:"提供基因检测、科研服务与多组学解决方案。", product:"生育健康、肿瘤防控和感染防控检测。", source:official("华大基因","https://www.bgi.com/"), confidence:0.99 },
  { slug:"insilico-medicine", name:"英矽智能", englishName:"Insilico Medicine", region:"中国", sector:"生物科技", stage:"成长期", status:"运营中", founded:"2014", headquarters:"香港", summary:"利用生成式 AI 进行靶点发现与小分子药物设计。", product:"Pharma.AI 平台与自研药物管线。", source:official("Insilico Medicine","https://insilico.com/"), confidence:0.97 },
  { slug:"fourier-intelligence", name:"傅利叶智能", englishName:"Fourier Intelligence", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2015", headquarters:"上海", summary:"研发康复机器人和通用人形机器人平台。", product:"康复机器人、GR 系列人形机器人。", source:official("傅利叶智能","https://www.fftai.com/"), confidence:0.96 },
  { slug:"agibot", name:"智元机器人", englishName:"AgiBot", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2023", headquarters:"上海", summary:"研发具身智能机器人本体、数据和模型体系。", product:"远征、灵犀等机器人系列。", source:official("智元机器人","https://www.zhiyuan-robot.com/"), confidence:0.94 },
  { slug:"galbot", name:"银河通用", englishName:"Galbot", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2023", headquarters:"北京", summary:"研发面向零售、工业和服务场景的具身智能机器人。", product:"通用机器人本体与具身模型。", source:official("银河通用","https://www.galbot.com/"), confidence:0.92 },
];

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
