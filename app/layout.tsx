import type { Metadata, Viewport } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { Navbar } from "@/components/navbar"

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" })

export const metadata: Metadata = {
  title: "Parking Audit Builder",
  description: "Generate ZPL labels and PDF reports for parking audits from Visual Matrix exports",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#3b82f6",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} bg-background`}>
      <body className="min-h-screen flex flex-col font-sans">
        <Navbar />
        <main className="flex-1 container mx-auto px-4 py-6 max-w-5xl">
          {children}
        </main>
        <footer className="border-t border-border py-4 text-center text-sm text-muted-foreground">
          Parking Audit Builder
        </footer>
      </body>
    </html>
  )
}
