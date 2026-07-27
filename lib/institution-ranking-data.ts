import { institutionCatalog } from "./catalog-data";

export type InstitutionRankingRecord = {
  publisher: "清科";
  year: 2025;
  category: InstitutionRankingCategory;
  title: string;
  rank?: number;
  ordered: boolean;
  sourceUrl: string;
};

export type InstitutionRankingCategory =
  | "早期投资"
  | "创业投资"
  | "私募股权"
  | "国资投资"
  | "战略投资者/CVC"
  | "并购投资"
  | "海外代表";

export type InstitutionDirectoryEntry = {
  name: string;
  fullName?: string;
  region: "中国" | "美国";
  type: string;
  stages: string;
  sectors: string[];
  profileSlug?: string;
  officialUrl?: string;
  rankings: InstitutionRankingRecord[];
};

export const institutionRankingSources = [
  {
    publisher: "清科研究中心 / 投资界",
    year: 2025,
    title: "清科2025中国股权投资年度排名总榜单",
    url: "https://news.pedaily.cn/202512/559270.shtml",
    categories: ["早期投资30强", "创业投资50强", "私募股权50强", "国资投资50强", "战略投资者/CVC30强", "并购投资10强"],
  },
  {
    publisher: "投中研究院 / 投中网",
    year: 2025,
    title: "投中2025年度榜单",
    url: "https://www.chinaventure.com.cn/rank/210/list.html",
    categories: ["创业投资TOP100", "私募股权TOP100", "早期投资TOP50", "中资/外资VC", "中资/外资PE", "企业直投", "人工智能与大数据", "半导体与集成电路", "先进制造与高科技", "商业航天与军民融合", "碳中和"],
  },
] as const;

const QINGKE_URL = institutionRankingSources[0].url;
const qingkeEarly = [
  "中科创星", "北京联想之星投资管理有限公司|联想之星", "启赋私募基金管理有限公司|啓赋资本", "真格基金", "英诺基金",
  "创新工场", "北京腾业创业投资管理有限公司|腾业创投", "蓝驰创投", "上海线性投资管理有限公司|线性资本", "鼎峰科创",
  "启迪之星（北京）投资管理有限公司|启迪之星创投", "宁波梅花天使投资管理有限公司|梅花创投", "九合创投", "深圳市高捷金台创业投资管理有限公司|高捷资本", "浙江银杏谷投资有限公司|银杏谷资本",
  "险峰", "云启资本", "杭州道生投资管理有限公司|道生资本", "奇绩创坛", "明势创投",
  "深圳市力合创业投资有限公司|力合创投", "峰瑞资本", "荷塘创业投资管理（北京）有限公司|荷塘创投", "上海小苗朗程投资管理有限公司|小苗朗程", "北京水木华鼎创业投资管理有限公司|水木创投",
  "北京元航投资管理有限公司|元航资本", "道彤投资", "北京星连肇基私募基金管理有限责任公司|星连资本", "上海曜途投资管理有限公司|耀途资本", "北京勿忘初心投资管理有限公司|初心资本",
] as const;

const qingkeVc = [
  "IDG资本", "深圳市创新投资集团有限公司|深创投集团", "启明创投", "苏州元禾控股股份有限公司|元禾控股", "君联资本管理股份有限公司|君联资本",
  "江苏毅达股权投资基金管理有限公司|毅达资本", "深圳市达晨财智创业投资管理有限公司|达晨财智", "高榕创投", "五源资本", "经纬创投（北京）投资管理顾问有限公司|经纬创投",
  "深圳同创伟业资产管理股份有限公司|同创伟业", "深圳市松禾资本管理有限公司|松禾资本", "美团龙珠", "礼来亚洲基金", "浙江普华天勤股权投资管理有限公司|普华资本",
  "朗玛峰创投", "北京源码资本投资有限公司|源码资本", "深圳市东方富海投资管理股份有限公司|东方富海", "长江创业投资基金管理有限公司|长江创投", "钟鼎资本",
  "弘晖基金", "纪源资本", "金雨茂物投资管理股份有限公司|金雨茂物", "深圳华业天成投资有限公司|华业天成资本", "国投创业投资管理有限公司|国投创业",
  "祥峰投资", "顺为资本", "鲁信创业投资集团股份有限公司|鲁信创投", "浙商创投股份有限公司|浙商创投", "北京洪泰同创投资管理有限公司|洪泰基金",
  "深圳市高新投集团有限公司|深高新投", "广东省粤科金融集团有限公司|粤科金融集团", "北极光创投", "华盖资本有限责任公司|华盖资本", "光合创业投资基金|光合创投",
  "清控银杏创业投资管理（北京）有限公司|清控银杏创投", "联想创投", "国中资本", "XVC", "深圳市天图投资管理股份有限公司|天图投资",
  "赛富投资基金", "武岳峰科创|武岳峰", "蔚来资本", "宁波保税区凯风创业投资管理有限公司|凯风创投", "元生创投",
  "深圳市创东方投资有限公司|创东方投资", "天堂硅谷创业投资集团有限公司|天堂硅谷", "丰年永泰（北京）投资管理有限公司|丰年资本", "深圳市高特佳投资集团有限公司|高特佳投资", "华睿投资",
] as const;

const qingkePe = [
  "红杉中国", "高瓴投资", "中金资本运营有限公司|中金资本", "CPE源峰", "招银国际资本管理（深圳）有限公司|招银国际资本",
  "招商局资本投资有限责任公司|招商资本", "中国国新基金管理有限公司|国新基金", "基石资产管理股份有限公司|基石资本", "金浦产业投资基金管理有限公司|金浦投资", "国投创新投资管理有限公司|国投创新",
  "珠海科技产业集团有限公司|珠海科技集团", "海松资本", "中信金石投资有限公司|中信金石", "鼎晖股权投资管理（天津）有限公司|鼎晖投资", "前海方舟资产管理有限公司|前海方舟",
  "国投创益产业基金管理有限公司|国投创益", "中芯聚源私募基金管理（上海）有限公司|中芯聚源", "中信资本控股有限公司|中信资本", "博裕投资", "凯辉基金",
  "腾讯投资", "海通开元投资有限公司|海通开元", "平安资本有限责任公司|平安资本", "德弘资本", "太盟投资集团|太盟投资",
  "华平投资", "广发信德投资管理有限公司|广发信德", "复星投资", "北京汽车集团产业投资有限公司|北汽产投", "云锋基金",
  "上海恒旭创领私募基金管理有限公司|恒旭资本", "中信建投资本管理有限公司|中信建投资本", "上海尚颀投资管理合伙企业（有限合伙）|尚颀资本", "建信（北京）投资基金管理有限责任公司|建信（北京）投资", "上海上实资本管理有限公司|上实资本",
  "北京云晖私募基金管理有限公司|云晖资本", "力鼎资本", "长江成长资本投资有限公司|长江成长资本", "北京博华资本有限公司|博华资本", "招商致远资本投资有限公司|招商致远资本",
  "上海正心谷投资管理有限公司|正心谷资本", "北京华控投资管理集团有限公司|华控基金", "方源资本", "华泰紫金投资有限责任公司|华泰紫金投资", "上海东方证券资本投资有限公司|东证资本",
  "中国科技产业投资管理有限公司|国科投资", "沄柏资本", "建信金投私募基金管理（北京）有限公司|建投基金", "嘉御资本", "上海联新资本管理有限公司|联新资本",
] as const;

const qingkeState = [
  "北京国有资本运营管理有限公司|北京国管", "北京亦庄国际投资发展有限公司|亦庄国投", "无锡市创新投资集团有限公司|锡创投", "宁波通商基金管理有限公司|通商基金", "广州产业投资资本管理有限公司|广州产投资本",
  "成都产业投资集团有限公司|成都产投集团", "上海国盛资本管理有限公司|上海国盛资本", "广东恒健投资控股有限公司|广东恒健控股", "南京市创新投资集团有限责任公司|南创投", "四川产业振兴基金投资集团有限公司|四川产业基金",
  "苏州创新投资集团有限公司|苏创投", "北京中关村资本基金管理有限公司|中关村资本", "上海浦东科创集团有限公司|浦东科创集团", "深圳市投控资本有限公司|深投控资本", "绿色发展基金私募股权投资管理（上海）有限公司|绿金投资",
  "中车资本", "苏州市吴江创业投资有限公司|吴江创投", "湖南省财信产业基金管理有限公司|财信产业基金", "四川省科技创新投资集团有限责任公司|四川省科创投资集团", "国泰君安创新投资有限公司|国泰君安创新投资",
  "国投创合基金管理有限公司|国投创合", "上海浦东创新投资发展（集团）有限公司|浦东创投", "厦门建发新兴产业股权投资有限责任公司|建发新兴投资", "上海临港科创投资管理有限公司|临港科创投", "合肥建投资本管理有限公司|合肥建投资本",
  "杭州和达投资管理有限公司|和达投资", "安徽中安资本管理有限公司|中安资本", "杭州国舜股权投资有限公司|国舜投资", "重庆渝富高质产业母基金私募股权投资基金管理有限公司|重庆渝富高质基金公司", "湖南兴湘资本管理有限公司|兴湘资本",
  "深圳市投控东海投资有限公司|投控东海", "上海科技创业投资（集团）有限公司|上海科创集团", "湖南能源集团湘投私募基金管理有限公司|湘投基金", "重庆两江股权投资基金管理有限公司|两江资本", "广州产业投资基金管理有限公司|广州基金",
  "浙江省产投集团有限公司|浙江产投", "山东省财金资本管理有限公司|山东财金资本公司", "中建材（安徽）新材料产业投资基金合伙企业（有限合伙）|中建材新材料基金", "合肥产投资本创业投资管理有限公司|合肥产投资本", "中国石油集团昆仑资本有限公司|中国石油昆仑资本",
  "浙江富浙私募基金管理有限公司|富浙基金", "武汉光谷产业投资有限公司|光谷产投", "上海孚腾私募基金管理有限公司|孚腾资本", "北京工业发展投资管理有限公司|北工投资", "广东粤财基金管理有限公司|广东粤财基金",
  "广汽资本有限公司|广汽资本", "广州金控基金管理有限公司|广州金控基金", "浙江省创新产业私募基金管理有限公司", "策源资本", "深圳市南山战略新兴产业投资有限公司|南山战新投",
] as const;

const qingkeCvc = [
  "中建材新材料基金", "中国石油昆仑资本", "联想创投", "腾讯投资", "中国移动链长基金", "蚂蚁集团",
  "中车资本", "阿里巴巴", "TCL创投", "泰格医药", "中国石化资本", "宁德时代",
  "上汽集团", "博世集团", "小米", "科大讯飞", "美团", "复健资本",
  "国家电投创新投资", "吉利控股集团", "创维投资", "海尔集团", "比亚迪投资", "芯联集成",
  "普洛斯", "商汤科技", "百洋医药集团", "盈峰投资", "京东集团", "百度",
] as const;

const qingkeMna = [
  "太盟投资集团|太盟投资", "鼎晖股权投资管理（天津）有限公司|鼎晖投资", "高瓴投资", "方源资本", "德弘资本",
  "博裕投资", "中信资本控股有限公司|中信资本", "红杉中国", "KKR", "CPE源峰",
] as const;

const profileAliases: Record<string, string> = {
  真格基金: "zhenfund",
  IDG资本: "idg-capital",
  深创投集团: "scgc",
  启明创投: "qiming",
  君联资本: "legend-capital",
  达晨财智: "fortune-capital",
  高榕创投: "gaorong",
  经纬创投: "matrix-china",
  红杉中国: "hongshan",
  高瓴投资: "hillhouse",
};

const categoryMeta: Record<
  Exclude<InstitutionRankingCategory, "海外代表">,
  { stages: string; sectors: string[]; title: string; ordered: boolean }
> = {
  早期投资: { stages: "天使/种子", sectors: ["科技创业", "硬科技", "企业服务"], title: "2025年中国早期投资机构30强", ordered: true },
  创业投资: { stages: "早期至成长期", sectors: ["科技", "医疗", "先进制造"], title: "2025年中国创业投资机构50强", ordered: true },
  私募股权: { stages: "成长期/Pre-IPO", sectors: ["科技", "医疗", "消费"], title: "2025年中国私募股权投资机构50强", ordered: true },
  国资投资: { stages: "全阶段", sectors: ["硬科技", "先进制造", "区域产业"], title: "2025年中国国资投资机构50强", ordered: false },
  "战略投资者/CVC": { stages: "战略投资", sectors: ["产业协同", "硬科技", "数字化"], title: "2025年中国战略投资者/CVC30强", ordered: false },
  并购投资: { stages: "并购/控股投资", sectors: ["并购整合", "科技", "消费"], title: "2025年中国并购投资机构10强", ordered: false },
};

const splitName = (value: string) => {
  const [fullName, name = fullName] = value.split("|");
  return { fullName, name };
};

const directory = new Map<string, InstitutionDirectoryEntry>();

function addQingkeList(
  category: Exclude<InstitutionRankingCategory, "海外代表">,
  values: readonly string[],
) {
  const meta = categoryMeta[category];
  values.forEach((value, index) => {
    const { fullName, name } = splitName(value);
    const current = directory.get(name);
    const ranking: InstitutionRankingRecord = {
      publisher: "清科",
      year: 2025,
      category,
      title: meta.title,
      rank: meta.ordered ? index + 1 : undefined,
      ordered: meta.ordered,
      sourceUrl: QINGKE_URL,
    };
    if (current) {
      current.rankings.push(ranking);
      current.sectors = [...new Set([...current.sectors, ...meta.sectors])];
      if (!current.fullName && fullName !== name) current.fullName = fullName;
      return;
    }
    directory.set(name, {
      name,
      fullName: fullName === name ? undefined : fullName,
      region: "中国",
      type: category === "战略投资者/CVC" ? "产业资本/CVC" : category === "国资投资" ? "国资投资机构" : category === "并购投资" ? "并购投资机构" : category,
      stages: meta.stages,
      sectors: [...meta.sectors],
      profileSlug: profileAliases[name],
      rankings: [ranking],
    });
  });
}

addQingkeList("早期投资", qingkeEarly);
addQingkeList("创业投资", qingkeVc);
addQingkeList("私募股权", qingkePe);
addQingkeList("国资投资", qingkeState);
addQingkeList("战略投资者/CVC", qingkeCvc);
addQingkeList("并购投资", qingkeMna);

for (const institution of institutionCatalog) {
  const matchedName =
    institution.name === "IDG 资本" ? "IDG资本" :
    institution.name === "深创投" ? "深创投集团" :
    institution.name === "高瓴" ? "高瓴投资" :
    institution.name;
  const existing = directory.get(matchedName);
  if (existing) {
    existing.profileSlug = institution.slug;
    existing.officialUrl = institution.source.url;
    existing.type = institution.type;
    existing.stages = institution.stages;
    existing.sectors = institution.sectors;
    continue;
  }
  directory.set(institution.name, {
    name: institution.name,
    fullName: institution.englishName,
    region: institution.region,
    type: institution.type,
    stages: institution.stages,
    sectors: institution.sectors,
    profileSlug: institution.slug,
    officialUrl: institution.source.url,
    rankings: [],
  });
}

export const institutionDirectory = [...directory.values()].sort((left, right) => {
  const leftRank = Math.min(...left.rankings.map((item) => item.rank ?? 999), 999);
  const rightRank = Math.min(...right.rankings.map((item) => item.rank ?? 999), 999);
  return (
    Number(Boolean(right.rankings.length)) - Number(Boolean(left.rankings.length)) ||
    leftRank - rightRank ||
    left.name.localeCompare(right.name, "zh-CN")
  );
});

export const institutionDirectoryStats = {
  total: institutionDirectory.length,
  china: institutionDirectory.filter((item) => item.region === "中国").length,
  us: institutionDirectory.filter((item) => item.region === "美国").length,
  detailedProfiles: institutionDirectory.filter((item) => item.profileSlug).length,
  rankedRecords: institutionDirectory.reduce((total, item) => total + item.rankings.length, 0),
};

export const institutionRankingCategories: InstitutionRankingCategory[] = [
  "早期投资",
  "创业投资",
  "私募股权",
  "国资投资",
  "战略投资者/CVC",
  "并购投资",
  "海外代表",
];

export function getInstitutionRankingEntry(name: string) {
  const normalized =
    name === "深创投" ? "深创投集团" :
    name === "高瓴" ? "高瓴投资" :
    name;
  return institutionDirectory.find((item) => item.name === normalized);
}
