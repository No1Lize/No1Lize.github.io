export type SearchRecordType = "技术" | "赛道" | "人物" | "公司" | "资料" | "事件";

export type SearchRecord = {
  type: SearchRecordType;
  title: string;
  text: string;
  href: string;
  region: string;
};

export type ArticleSearchIndexPayload = {
  schemaVersion: 1;
  generatedAt: string;
  recordCount: number;
  records: SearchRecord[];
};
