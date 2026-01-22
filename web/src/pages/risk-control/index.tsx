import { useState } from "react";
import { Tabs, Tab } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { RiskControlTab, DefaultCopyConfigTab, ImmediateCopyConfigTab } from "./components";

export default function RiskControlPage() {
  const [activeTab, setActiveTab] = useState("risk-control");
  const [riskHasChanges, setRiskHasChanges] = useState(false);
  const [copyHasChanges, setCopyHasChanges] = useState(false);
  const [immediateHasChanges, setImmediateHasChanges] = useState(false);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6 max-w-4xl mx-auto">
        {/* 标题栏 */}
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Icon icon="lucide:shield-check" width={28} />
            系统配置
          </h1>
          <p className="text-default-500 mt-1">
            配置跟单交易的风险控制和默认参数
          </p>
        </div>

        {/* Tabs */}
        <Tabs
          selectedKey={activeTab}
          onSelectionChange={(key) => setActiveTab(key as string)}
          color="primary"
          variant="underlined"
          classNames={{
            tabList: "gap-6",
            cursor: "w-full",
            tab: "max-w-fit px-0 h-12",
          }}
        >
          <Tab
            key="risk-control"
            title={
              <div className="flex items-center gap-2">
                <Icon icon="lucide:shield-alert" width={18} />
                <span>风控配置</span>
                {riskHasChanges && (
                  <span className="w-2 h-2 rounded-full bg-warning" />
                )}
              </div>
            }
          >
            <div className="pt-4">
              <RiskControlTab onHasChanges={setRiskHasChanges} />
            </div>
          </Tab>
          <Tab
            key="copy-config"
            title={
              <div className="flex items-center gap-2">
                <Icon icon="lucide:copy" width={18} />
                <span>默认跟单配置</span>
                {copyHasChanges && (
                  <span className="w-2 h-2 rounded-full bg-warning" />
                )}
              </div>
            }
          >
            <div className="pt-4">
              <DefaultCopyConfigTab onHasChanges={setCopyHasChanges} />
            </div>
          </Tab>
          <Tab
            key="immediate-copy"
            title={
              <div className="flex items-center gap-2">
                <Icon icon="lucide:zap" width={18} />
                <span>立即跟单配置</span>
                {immediateHasChanges && (
                  <span className="w-2 h-2 rounded-full bg-warning" />
                )}
              </div>
            }
          >
            <div className="pt-4">
              <ImmediateCopyConfigTab onHasChanges={setImmediateHasChanges} />
            </div>
          </Tab>
        </Tabs>
      </div>
    </DefaultLayout>
  );
}
