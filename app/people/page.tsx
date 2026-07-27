import type { Metadata } from "next";
import { Users } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { peopleGeneratedAt, researchPeople } from "@/lib/people-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "人物研究",
  description: "汇总所有赛道关注人物，并以统一资料管线整理其背景、公司、产品、作品、著作、演讲与公开材料。",
};

const statusLabels = {
  complete: "资料较完整",
  partial: "持续补充",
  pending: "等待抓取",
} as const;

export default function PeoplePage() {
  const trackedCount = researchPeople.filter((person) => person.tracked).length;
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">07 / PEOPLE</p>
        <h1>人物研究</h1>
        <p>
          汇总所有赛道配置中的真实人物，统一抓取 Wikipedia、Wikidata、个人主页、公司官网、论文、著作、演讲与站内情报；组织账号不会被误建成人物档案。
        </p>
        <div className="hero-chips">
          <span>{trackedCount} 位赛道人物</span>
          <span>{researchPeople.length} 位人物总计</span>
          <span>资料更新 {peopleGeneratedAt.slice(0, 10)}</span>
        </div>
      </header>

      <ChannelSplitLayout
        channel="people"
        eyebrow="LATEST PEOPLE DIRECTORY"
        title="关键人物档案"
        description="按人物进入其背景、所属机构、核心观点、公开账号、演讲资料和可追溯原始来源。"
        count={researchPeople.length}
        countLabel="公开人物快照"
        statusText={`更新 ${peopleGeneratedAt.slice(0, 10)}`}
        icon={<Users size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <div className="people-grid">
          {researchPeople.map((person) => (
            <Link href={`/people/${person.slug}`} key={person.slug}>
              <div className="person-monogram">{person.name.slice(0, 1)}</div>
              <p>{person.englishName}</p>
              <h2>{person.name}</h2>
              <span>{person.role}</span>
              <strong>{person.summary}</strong>
              <div>
                {person.sectors.map((sector) => <i key={sector}>{sector}</i>)}
                {person.concepts
                  .slice(0, Math.max(0, 4 - person.sectors.length))
                  .map((concept) => <i key={concept}>{concept}</i>)}
              </div>
              <small>{statusLabels[person.status]} · {person.materials.length} 条可追溯材料</small>
            </Link>
          ))}
        </div>
      </ChannelSplitLayout>
    </main>
  );
}
