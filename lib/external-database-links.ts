export type ExternalDatabaseLink = {
  platform: "企查查" | "鲸准" | "行行查";
  label: string;
  url: string;
  note: string;
  via: string;
};

// 鲸准、企查查与行行查都是商业数据库：详情页需要登录、会员或授权，
// 站点也不允许自动抓取。本站遵循自身合规边界（不绕过登录、验证码与
// 访问控制），因此只提供确定性的检索入口链接，数据由访问者在对方平台
// 自行查看，本站不抓取、不缓存其任何内容。
const CJK_PATTERN = /[㐀-鿿]/u;

function normalizeTerm(value: string): string {
  return value.replace(/\s+/gu, " ").trim();
}

function qccSearchUrl(term: string): string {
  return `https://www.qcc.com/web/search?key=${encodeURIComponent(term)}`;
}

// 鲸准与行行查没有公开的按名称检索地址（数据查询入口需要账号），因此
// 与本站爬虫的公开索引策略一致，改用 Bing 的 site: 限定检索直达其
// 公开页面。
function bingSiteIndexUrl(host: string, term: string): string {
  return `https://www.bing.com/search?q=${encodeURIComponent(`site:${host} "${term}"`)}`;
}

export function companyDatabaseLinks(
  name: string,
  region?: string,
): ExternalDatabaseLink[] {
  const term = normalizeTerm(name);
  // 两个平台均以中国注册主体为主，海外公司给出入口只会产生空结果。
  if (!term || (region && region !== "中国")) return [];
  return [
    {
      platform: "企查查",
      label: `企查查 · ${term}`,
      url: qccSearchUrl(term),
      note: "工商注册、股东与经营风险检索",
      via: "www.qcc.com",
    },
    {
      platform: "鲸准",
      label: `鲸准 · ${term}`,
      url: bingSiteIndexUrl("jingdata.com", term),
      note: "创投项目与融资数据公开索引检索",
      via: "经 Bing 公开索引直达 jingdata.com",
    },
  ];
}

export function personDatabaseLinks(name: string): ExternalDatabaseLink[] {
  const term = normalizeTerm(name);
  if (!term || !CJK_PATTERN.test(term)) return [];
  return [
    {
      platform: "企查查",
      label: `企查查 · ${term}`,
      url: qccSearchUrl(term),
      note: "任职、持股与关联企业检索",
      via: "www.qcc.com",
    },
    {
      platform: "鲸准",
      label: `鲸准 · ${term}`,
      url: bingSiteIndexUrl("jingdata.com", term),
      note: "创投人物与项目公开索引检索",
      via: "经 Bing 公开索引直达 jingdata.com",
    },
  ];
}

export function hanghangchaResearchLink(
  name: string,
  note = "行业研报与数据图表公开索引检索",
): ExternalDatabaseLink | null {
  const term = normalizeTerm(name);
  if (!term) return null;
  return {
    platform: "行行查",
    label: `行行查 · ${term}`,
    url: bingSiteIndexUrl("hanghangcha.com", term),
    note,
    via: "经 Bing 公开索引直达 hanghangcha.com",
  };
}

export function hanghangchaEntryLink(): ExternalDatabaseLink {
  return {
    platform: "行行查",
    label: "行行查 · 行业研究数据库",
    url: "https://www.hanghangcha.com/",
    note: "行业研报、产业链图谱与数据图表平台入口",
    via: "www.hanghangcha.com（完整内容需登录对方平台查看）",
  };
}
