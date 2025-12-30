import { Route, Routes } from "react-router-dom";

import IndexPage from "@/pages/index";
import DocsPage from "@/pages/docs";
import PricingPage from "@/pages/pricing";
import BlogPage from "@/pages/blog";
import AboutPage from "@/pages/about";
import TradersPage from "@/pages/traders";
import TraderDetailPage from "@/pages/trader-detail";
import CopyTradingPage from "@/pages/copy-trading";
import OrdersPage from "@/pages/orders";

function App() {
  return (
    <Routes>
      <Route element={<IndexPage />} path="/" />
      <Route element={<DocsPage />} path="/docs" />
      <Route element={<PricingPage />} path="/pricing" />
      <Route element={<BlogPage />} path="/blog" />
      <Route element={<AboutPage />} path="/about" />
      <Route element={<TradersPage />} path="/traders" />
      <Route element={<TraderDetailPage />} path="/traders/:address" />
      <Route element={<CopyTradingPage />} path="/copy-trading" />
      <Route element={<OrdersPage />} path="/orders" />
    </Routes>
  );
}

export default App;
