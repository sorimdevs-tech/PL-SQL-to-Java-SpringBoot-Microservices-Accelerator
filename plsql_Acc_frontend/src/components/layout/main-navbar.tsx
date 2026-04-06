import { Bell, ChevronDown, CircleDollarSign, Menu, Settings2 } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { NavItem } from "@/types/dashboard"

interface MainNavbarProps {
  items: NavItem[]
}

export function MainNavbar({ items }: MainNavbarProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 md:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 md:hidden"
            aria-label="Toggle navigation menu"
          >
            <Menu className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white shadow-md shadow-slate-900/30">
              <CircleDollarSign className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-900">AccFlow Studio</p>
              <p className="text-xs text-slate-500">Enterprise Console</p>
            </div>
          </div>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          {items.map((item) => (
            <a
              key={item.label}
              href="#"
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                item.active
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {item.label}
              {item.badge ? <Badge variant="warning">{item.badge}</Badge> : null}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" aria-label="Notifications">
            <Bell className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Settings">
            <Settings2 className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" className="hidden md:inline-flex">
            Finance Admin
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  )
}
