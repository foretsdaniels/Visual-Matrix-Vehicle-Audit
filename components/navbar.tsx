"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Car, LayoutDashboard, Upload, List } from "lucide-react"

const navLinks = [
  { href: "/", label: "Upload", icon: Upload },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/sessions", label: "Sessions", icon: List },
]

export function Navbar() {
  const pathname = usePathname()

  return (
    <nav className="border-b border-border bg-card">
      <div className="container mx-auto px-4 max-w-5xl">
        <div className="flex items-center justify-between h-14">
          <Link href="/" className="flex items-center gap-2 text-foreground">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Car className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="font-semibold hidden sm:inline">Parking Audit Builder</span>
          </Link>
          
          <div className="flex items-center gap-1">
            {navLinks.map((link) => {
              const Icon = link.icon
              const isActive = pathname === link.href || 
                (link.href !== "/" && pathname.startsWith(link.href))
              
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{link.label}</span>
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}
