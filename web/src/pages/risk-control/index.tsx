import { useState } from "react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { RiskControlTab } from "./components";

export default function RiskControlPage() {
  const [riskHasChanges, setRiskHasChanges] = useState(false);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6 max-w-4xl mx-auto">
        {/* 标题栏 */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Icon icon="lucide:shield-check" width={28} />
            风控配置
            {riskHasChanges && (
              <span className="w-2 h-2 rounded-full bg-warning" />
            )}
          </h1>
          <p className="text-default-500 mt-1">
            配置跟单交易的风险控制参数
          </p>
        </div>

        {/* 风控配置内容 */}
        <RiskControlTab onHasChanges={setRiskHasChanges} />
      </div>
    </DefaultLayout>
  );
}
