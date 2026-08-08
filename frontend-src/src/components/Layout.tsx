import { NavLink } from 'react-router-dom'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-4 py-2 rounded-md text-sm font-mono-ui transition-colors ${
    isActive ? 'bg-accent-blue/20 text-accent-blue' : 'text-muted hover:text-text'
  }`

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen text-text">
      <header className="border-b border-border">
        <div className="mx-auto max-w-6xl flex items-center justify-between px-6 py-4">
          <div className="font-pixel-brand text-sm">
            LLM Comparison <span className="text-accent-blue">Arena</span>
          </div>
          <nav className="flex gap-2">
            <NavLink to="/" end className={linkClass}>
              Compare
            </NavLink>
            <NavLink to="/results" className={linkClass}>
              Results
            </NavLink>
            <NavLink to="/history" className={linkClass}>
              History
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
