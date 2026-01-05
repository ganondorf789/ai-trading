import { Route, Routes } from "react-router-dom";

import IndexPage from "@/pages/index";
import TradersPage from "@/pages/traders";
import TraderDetailPage from "@/pages/trader-detail";
import CopyTradingPage from "@/pages/copy-trading";
import PositionsPage from "@/pages/positions";
import GroupComparisonPage from "@/pages/group-comparison";

function App() {
  return (
    <Routes>
      <Route element={<IndexPage />} path="/" />
      <Route element={<TradersPage />} path="/traders" />
      <Route element={<TraderDetailPage />} path="/traders/:address" />
      <Route element={<CopyTradingPage />} path="/copy-trading" />
      <Route element={<PositionsPage />} path="/positions" />
      <Route element={<GroupComparisonPage />} path="/group-comparison" />
    </Routes>
  );
}

export default App;
