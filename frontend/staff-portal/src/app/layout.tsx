import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { PortalChrome } from "@/components/PortalChrome";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "PrelimMD - Staff Portal",
  description: "Nurse and doctor portal for patient intake management",
};

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${inter.variable}`}>
        <div className="font-vars">
          <PortalChrome>{children}</PortalChrome>
        </div>
      </body>
    </html>
  );
}
