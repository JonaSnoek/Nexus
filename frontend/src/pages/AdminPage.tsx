import { useParams, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import AdminLayout from "../components/admin/AdminLayout";
import DashboardSection from "../components/admin/DashboardSection";
import UsersSection from "../components/admin/UsersSection";
import PermissionsSection from "../components/admin/PermissionsSection";
import UsageSection from "../components/admin/UsageSection";
import ModelsSection from "../components/admin/ModelsSection";
import SystemSection from "../components/admin/SystemSection";
import SettingsSection from "../components/admin/SettingsSection";
import LogsSection from "../components/admin/LogsSection";

const sections: Record<string, React.FC> = {
  dashboard: DashboardSection,
  users: UsersSection,
  permissions: PermissionsSection,
  usage: UsageSection,
  models: ModelsSection,
  system: SystemSection,
  settings: SettingsSection,
  logs: LogsSection,
};

export default function AdminPage() {
  const { section } = useParams();
  const navigate = useNavigate();
  const currentSection = section || "dashboard";
  const SectionComponent = sections[currentSection] || DashboardSection;

  function handleSectionChange(newSection: string) {
    navigate(`/admin/${newSection}`);
  }

  return (
    <Layout>
      <AdminLayout
        currentSection={currentSection}
        onSectionChange={handleSectionChange}
      >
        <SectionComponent />
      </AdminLayout>
    </Layout>
  );
}
