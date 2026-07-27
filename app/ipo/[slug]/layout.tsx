import styles from "./market-detail.module.css";

export default function IpoDetailLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <div className={styles.scope}>{children}</div>;
}
