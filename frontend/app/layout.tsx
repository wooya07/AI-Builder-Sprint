import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "설계한 학기",
  description: "목표와 생활 리듬을 반영하는 개인 맞춤 시간표 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
