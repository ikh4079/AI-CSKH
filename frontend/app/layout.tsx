import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono } from "next/font/google";

import "./globals.css";

const sans = Bricolage_Grotesque({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "AI CSKH",
  description: "FastAPI + LangGraph + RAG customer service",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className={`${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}

