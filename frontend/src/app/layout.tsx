import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "ConvoxAI",
  description:
    "Your AI clone answers inquiries, shares expertise, and builds audience.",
  icons: {
    icon: [
      { url: "/Brand.png", sizes: "any" },
      { url: "/Brand.png", sizes: "32x32", type: "image/png" },
      { url: "/Brand.png", sizes: "16x16", type: "image/png" },
    ],
    apple: "/Brand.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
