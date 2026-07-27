import { ExternalLink } from "lucide-react";
import type { ExternalDatabaseLink } from "@/lib/external-database-links";

export function ExternalDatabaseLinks({
  links,
  lead = "以下入口跳转到外部商业数据库检索本页主体；数据在对方平台查看，本站不抓取、不缓存其内容。",
}: {
  links: ExternalDatabaseLink[];
  lead?: string;
}) {
  if (!links.length) return null;
  return (
    <div className="external-db-links">
      <p className="external-db-lead">{lead}</p>
      {links.map((link) => (
        <a
          className="source-card"
          href={link.url}
          target="_blank"
          rel="noreferrer"
          key={link.url}
        >
          <span>{link.note}</span>
          <strong>
            {link.label} <ExternalLink size={12} aria-hidden="true" />
          </strong>
          <small>{link.via}</small>
        </a>
      ))}
    </div>
  );
}
