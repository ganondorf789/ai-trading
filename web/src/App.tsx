import { Route, Routes } from "react-router-dom";

import IndexPage from "@/pages/index";
import TradersPage from "@/pages/traders";
import TraderDetailPage from "@/pages/trader-detail";
import CopyTradingPage from "@/pages/copy-trading";
import CopyOrdersPage from "@/pages/copy-orders";
import PositionsPage from "@/pages/positions";
import TraderPositionsPage from "@/pages/trader-positions";
import PositionHistoryPage from "@/pages/position-history";
import RiskControlPage from "@/pages/risk-control";
import BestSTradersPage from "@/pages/best-s-traders";
import PositionTrackingPage from "@/pages/position-tracking";

function App() {
  return (
    <Routes>
      <Route element={<IndexPage />} path="/" />
      <Route element={<TradersPage />} path="/traders" />
      <Route element={<TraderDetailPage />} path="/traders/:address" />
      <Route element={<BestSTradersPage />} path="/best-s-traders" />
      <Route element={<CopyTradingPage />} path="/copy-trading" />
      <Route element={<CopyOrdersPage />} path="/copy-orders" />
      <Route element={<PositionsPage />} path="/positions" />
      <Route element={<TraderPositionsPage />} path="/trader-positions" />
      <Route element={<PositionHistoryPage />} path="/position-history" />
      <Route element={<RiskControlPage />} path="/risk-control" />
      <Route element={<PositionTrackingPage />} path="/position-tracking" />
    </Routes>
  );
}

export default App;
