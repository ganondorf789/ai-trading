"use client";

import React from "react";
import { Button, Spacer, Tooltip, useDisclosure, cn } from "@heroui/react";
import { Icon } from "@iconify/react";

import SidebarDrawer from "@/components/sidebar-drawer";
import Sidebar from "@/components/sidebar";
import { sidebarItems } from "@/config/sidebar-items";
import { ThemeSwitch } from "@/components/theme-switch";
import { Logo } from "@/components/icons";

export default function DefaultLayout({ children }: { children: React.ReactNode }) {
  const { isOpen, onOpenChange } = useDisclosure();
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const [isMobile, setIsMobile] = React.useState(false);

  React.useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const onToggle = React.useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    window.location.href = "/login";
  };

  return (
    <div className="flex h-dvh w-full gap-0">
      {/* Sidebar */}
      <SidebarDrawer
        className={cn("min-w-[288px] rounded-none", { "min-w-[76px]": isCollapsed })}
        hideCloseButton={true}
        isOpen={isOpen}
        onOpenChange={onOpenChange}
      >
        <div
          className={cn(
            "will-change bg-default-100 transition-width relative flex h-full w-72 flex-col p-6",
            {
              "w-[83px] items-center px-[6px] py-6": isCollapsed,
            }
          )}
        >
          {/* Logo */}
          <div
            className={cn("flex items-center gap-3 pl-2", {
              "justify-center gap-0 pl-0": isCollapsed,
            })}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-foreground">
              <Logo className="text-background" />
            </div>
            <span
              className={cn("w-full text-small font-bold uppercase opacity-100", {
                "w-0 opacity-0": isCollapsed,
              })}
            >
              Trading
            </span>
            <div className={cn("flex-end flex", { hidden: isCollapsed })}>
              <Icon
                className="cursor-pointer text-default-500 dark:text-primary-foreground/60 [&>g]:stroke-[1px]"
                icon="solar:round-alt-arrow-left-line-duotone"
                width={24}
                onClick={isMobile ? onOpenChange : onToggle}
              />
            </div>
          </div>

          <Spacer y={6} />

          {/* Navigation */}
          <Sidebar
            defaultSelectedKey="traders"
            iconClassName="group-data-[selected=true]:text-default-50"
            isCompact={isCollapsed}
            itemClasses={{
              base: "px-3 rounded-large data-[selected=true]:!bg-foreground",
              title: "group-data-[selected=true]:text-default-50",
            }}
            items={sidebarItems}
          />

          <Spacer y={8} />

          {/* Bottom Actions */}
          <div
            className={cn("mt-auto flex flex-col", {
              "items-center": isCollapsed,
            })}
          >
            {isCollapsed && (
              <Button
                isIconOnly
                className="flex h-10 w-10 text-default-600"
                size="sm"
                variant="light"
                onPress={onToggle}
              >
                <Icon
                  className="cursor-pointer text-default-500 dark:text-primary-foreground/60 [&>g]:stroke-[1px]"
                  height={24}
                  icon="solar:round-alt-arrow-right-line-duotone"
                  width={24}
                />
              </Button>
            )}

            {/* Theme Switch */}
            <div
              className={cn("flex items-center px-3 py-2", {
                "justify-center px-0": isCollapsed,
              })}
            >
              {isCollapsed ? (
                <Tooltip content="Toggle Theme" placement="right">
                  <div>
                    <ThemeSwitch />
                  </div>
                </Tooltip>
              ) : (
                <div className="flex w-full items-center gap-3">
                  <ThemeSwitch />
                  <span className="text-small font-medium text-default-500">Theme</span>
                </div>
              )}
            </div>

            <Tooltip content="Log Out" isDisabled={!isCollapsed} placement="right">
              <Button
                className={cn("justify-start text-default-500 data-[hover=true]:text-foreground", {
                  "justify-center": isCollapsed,
                })}
                isIconOnly={isCollapsed}
                startContent={
                  isCollapsed ? null : (
                    <Icon
                      className="flex-none rotate-180 text-default-500"
                      icon="solar:logout-2-line-duotone"
                      width={24}
                    />
                  )
                }
                variant="light"
                onPress={handleLogout}
              >
                {isCollapsed ? (
                  <Icon
                    className="rotate-180 text-default-500"
                    icon="solar:logout-2-line-duotone"
                    width={24}
                  />
                ) : (
                  "Log Out"
                )}
              </Button>
            </Tooltip>
          </div>
        </div>
      </SidebarDrawer>

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Header */}
        <div className="flex items-center gap-x-3 border-b border-default-200 px-4 py-3 sm:hidden">
          <Button
            isIconOnly
            size="sm"
            variant="flat"
            onPress={() => {
              setIsCollapsed(false);
              onOpenChange();
            }}
          >
            <Icon className="text-default-500" icon="solar:sidebar-minimalistic-linear" width={20} />
          </Button>
          <h1 className="text-lg font-bold text-default-foreground">Trading Dashboard</h1>
        </div>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
