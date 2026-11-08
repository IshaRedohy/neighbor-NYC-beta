import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Neighbor — Your people, a little closer",
  description:
    "An invitation-only community connecting New Yorkers through shared experiences, skills, and neighborhoods.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
