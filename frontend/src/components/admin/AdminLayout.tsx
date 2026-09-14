import {
  LayoutDashboard,
  Users,
  Shield,
  BarChart3,
  Cpu,
  Server,
  ScrollText,
} from "lucide-react";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "users", label: "Users", icon: Users },
  { id: "permissions", label: "Permissions", icon: Shield },
  { id: "usage", label: "Usage", icon: BarChart3 },
  { id: "models", label: "Models", icon: Cpu },
  { id: "system", label: "System", icon: Server },
  { id: "logs", label: "Logs", icon: ScrollText },
];

interface AdminLayoutProps {
  currentSection: string;
  onSectionChange: (section: string) => void;
  children: React.ReactNode;
}

export default function AdminLayout({
  currentSection,
  onSectionChange,
  children,
}: AdminLayoutProps) {
  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Admin sidebar nav */}
      <div className="hidden w-48 shrink-0 border-r border-nexus-border bg-nexus-surface lg:block">
        <div className="p-3">
          <h2 className="mb-2 px-3 text-xs font-medium uppercase tracking-wider text-gray-500">
            Admin
          </h2>
          <nav className="space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = currentSection === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSectionChange(item.id)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    active
                      ? "bg-nexus-elevated text-gray-100"
                      : "text-gray-400 hover:bg-nexus-elevated hover:text-gray-200"
                  }`}
                >
                  <Icon size={15} />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Mobile tabs */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex overflow-x-auto border-b border-nexus-border bg-nexus-surface px-2 lg:hidden">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = currentSection === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSectionChange(item.id)}
                className={`flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${
                  active
                    ? "border-blue-500 text-blue-500"
                    : "border-transparent text-gray-400 hover:text-gray-200"
                }`}
              >
                <Icon size={13} />
                {item.label}
              </button>
            );
          })}
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>
      </div>
    </div>
  );
}
