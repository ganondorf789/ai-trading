import { Route, Routes, Navigate } from "react-router-dom";

import LoginPage from "@/pages/login";
import TradersPage from "@/pages/traders";
import TraderDetailPage from "@/pages/trader-detail";
import CopyTradingPage from "@/pages/copy-trading";
import TraderPositionsPage from "@/pages/trader-positions";
import PositionHistoryPage from "@/pages/position-history";
import PositionTrackingPage from "@/pages/position-tracking";
import DefaultConfigRulesPage from "@/pages/default-config-rules";
import ImmediateConfigRulesPage from "@/pages/immediate-config-rules";
import UsersPage from "@/pages/users";
import SecretKeysPage from "@/pages/secret-keys";
import AppVersionsPage from "@/pages/app-versions";
import AnnouncementsPage from "@/pages/announcements";

function App() {
  return (
    <Routes>
      <Route element={<LoginPage />} path="/login" />
      <Route element={<Navigate to="/traders" replace />} path="/" />
      <Route element={<TradersPage />} path="/traders" />
      <Route element={<TraderDetailPage />} path="/traders/:address" />
      <Route element={<CopyTradingPage />} path="/copy-trading" />
      <Route element={<TraderPositionsPage />} path="/trader-positions" />
      <Route element={<PositionHistoryPage />} path="/position-history" />
      <Route element={<PositionTrackingPage />} path="/position-tracking" />
      <Route element={<DefaultConfigRulesPage />} path="/default-config-rules" />
      <Route element={<ImmediateConfigRulesPage />} path="/immediate-config-rules" />
      <Route element={<UsersPage />} path="/users" />
      <Route element={<SecretKeysPage />} path="/secret-keys" />
      <Route element={<AppVersionsPage />} path="/app-versions" />
      <Route element={<AnnouncementsPage />} path="/announcements" />
    </Routes>
  );
}

export default App;
