export type SiteConfig = typeof siteConfig;

export const siteConfig = {
  name: "Vite + HeroUI",
  description: "Make beautiful websites regardless of your design experience.",
  navItems: [
    {
      label: "Traders",
      href: "/traders",
    },
    {
      label: "Group Comparison",
      href: "/group-comparison",
    },
    {
      label: "Copy Trading",
      href: "/copy-trading",
    },
    {
      label: "Copy Orders",
      href: "/copy-orders",
    },
    {
      label: "Trader Positions",
      href: "/trader-positions",
    },
    {
      label: "Position History",
      href: "/position-history",
    },
    {
      label: "Position States",
      href: "/positions",
    },
    {
      label: "Risk Control",
      href: "/risk-control",
    }
  ],
  navMenuItems: [
    {
      label: "Profile",
      href: "/profile",
    },
    {
      label: "Dashboard",
      href: "/dashboard",
    },
    {
      label: "Projects",
      href: "/projects",
    },
    {
      label: "Team",
      href: "/team",
    },
    {
      label: "Calendar",
      href: "/calendar",
    },
    {
      label: "Settings",
      href: "/settings",
    },
    {
      label: "Help & Feedback",
      href: "/help-feedback",
    },
    {
      label: "Logout",
      href: "/logout",
    },
  ],
  links: {
    github: "https://github.com/heroui-inc/heroui",
    twitter: "https://twitter.com/hero_ui",
    docs: "https://heroui.com",
    discord: "https://discord.gg/9b6yyZKmH4",
    sponsor: "https://patreon.com/jrgarciadev",
  },
};
