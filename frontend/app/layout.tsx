import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "틈 | 공강을 나답게",
  description: "시간표의 빈틈에 꼭 맞는 활동을 추천하는 대학생 일정 도우미",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
