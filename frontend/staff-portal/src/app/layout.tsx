import type { Metadata } from "next";
import { PortalChrome } from "@/components/PortalChrome";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "PrelimMD - Staff Portal",
  description: "Nurse and doctor portal for patient intake management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PortalChrome>{children}</PortalChrome>
      </body>
    </html>
  );
}
