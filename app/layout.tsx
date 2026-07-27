import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";
import "./ipo/[slug]/market-detail.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://no1lize.github.io"),
  title: {
    default: "丽泽路1号｜科技与创投情报",
    template: "%s｜丽泽路1号",
  },
  description: "聚合中美新兴科技、创业公司、投资机构与 IPO 的可追溯公开信息。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "丽泽路1号",
    description: "公开、克制、可追溯的中美科技与创投情报。",
    type: "website",
    locale: "zh_CN",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" data-theme="dark" suppressHydrationWarning>
      <body>
        <Providers>
          <SiteHeader />
          {children}
          <footer className="site-footer">
            <div>
              <strong>丽泽路1号</strong>
              <span>事实、计算与判断分层呈现</span>
            </div>
            <p>信息仅供研究，不构成投资建议。关键事实均应回溯原始信源。</p>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
