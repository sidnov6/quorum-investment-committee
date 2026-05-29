import "./globals.css";
import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import Assistant from "@/components/Assistant";

export const metadata: Metadata = {
  title: "QUORUM — AI Investment Committee",
  description: "A multi-agent investment committee that debates from real data and converges on a documented allocation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 min-w-0 lg:ml-64">
            <div className="mx-auto max-w-6xl px-6 py-8">{children}</div>
          </main>
        </div>
        <Assistant />
      </body>
    </html>
  );
}
