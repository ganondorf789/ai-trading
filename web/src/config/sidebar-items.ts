import type { ListboxProps, ListboxSectionProps } from "@heroui/react";

export enum SidebarItemType {
  Nest = "nest",
}

export interface SidebarItem {
  key: string;
  title: string;
  icon?: string;
  href?: string;
  type?: SidebarItemType;
  startContent?: React.ReactNode;
  endContent?: React.ReactNode;
  items?: SidebarItem[];
  className?: string;
}

export type SidebarProps = Omit<ListboxProps<SidebarItem>, "children"> & {
  items: SidebarItem[];
  isCompact?: boolean;
  hideEndContent?: boolean;
  iconClassName?: string;
  sectionClasses?: ListboxSectionProps["classNames"];
  classNames?: ListboxProps["classNames"];
  defaultSelectedKey: string;
  onSelect?: (key: string) => void;
};

export const sidebarItems: SidebarItem[] = [
  {
    key: "main",
    title: "Main",
    items: [
      {
        key: "traders",
        href: "/traders",
        icon: "solar:users-group-rounded-line-duotone",
        title: "Traders",
      },
    ],
  },
  {
    key: "copy-trading",
    title: "Copy Trading",
    items: [
      {
        key: "copy-trading-page",
        href: "/copy-trading",
        icon: "solar:copy-line-duotone",
        title: "Copy Trading",
      },
    ],
  },
  {
    key: "positions",
    title: "Positions",
    items: [
      {
        key: "trader-positions",
        href: "/trader-positions",
        icon: "solar:graph-up-line-duotone",
        title: "Trader Positions",
      },
      {
        key: "position-history",
        href: "/position-history",
        icon: "solar:history-line-duotone",
        title: "Position History",
      },
      {
        key: "position-tracking",
        href: "/position-tracking",
        icon: "solar:target-line-duotone",
        title: "Position Tracking",
      },
    ],
  },
  {
    key: "settings",
    title: "Settings",
    items: [
      {
        key: "default-config-rules",
        href: "/default-config-rules",
        icon: "solar:settings-line-duotone",
        title: "Default Config Rules",
      },
      {
        key: "immediate-config-rules",
        href: "/immediate-config-rules",
        icon: "solar:bolt-line-duotone",
        title: "Immediate Config Rules",
      },
    ],
  },
  {
    key: "admin",
    title: "Admin",
    items: [
      {
        key: "users",
        href: "/users",
        icon: "solar:user-id-line-duotone",
        title: "Users",
      },
      {
        key: "secret-keys",
        href: "/secret-keys",
        icon: "solar:key-line-duotone",
        title: "Secret Keys",
      },
      {
        key: "app-versions",
        href: "/app-versions",
        icon: "solar:box-line-duotone",
        title: "App Versions",
      },
      {
        key: "announcements",
        href: "/announcements",
        icon: "solar:bell-line-duotone",
        title: "Announcements",
      },
    ],
  },
];
