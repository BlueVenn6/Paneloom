import { BookOpen, CalendarDays, LayoutDashboard, Settings, Table2 } from "lucide-react";

import { useI18n } from "../i18n.jsx";

const items = [
  { id: "dashboard", labelKey: "dashboard", icon: LayoutDashboard },
  { id: "projects", labelKey: "projects", icon: BookOpen },
  { id: "storyboard", labelKey: "storyboard", icon: Table2 },
  { id: "schedule", labelKey: "schedule", icon: CalendarDays },
  { id: "settings", labelKey: "settings", icon: Settings },
];

export default function Sidebar({ activePage, onNavigate }) {
  const { t } = useI18n();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">PL</div>
        <div>
          <h1>Paneloom</h1>
          <p>{t("appSubtitle")}</p>
        </div>
      </div>

      <nav className="nav-list">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={`nav-item ${activePage === item.id ? "active" : ""}`}
              data-page={item.id}
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              <Icon size={18} />
              <span>{t(item.labelKey)}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
