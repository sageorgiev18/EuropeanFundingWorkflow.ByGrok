import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EU Funding Workflow",
  description: "Matching EU funding opportunities",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
