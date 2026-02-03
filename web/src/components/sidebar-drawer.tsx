"use client";

import React from "react";
import { cn, Drawer, DrawerBody, DrawerContent } from "@heroui/react";

interface SidebarDrawerProps {
  children: React.ReactNode;
  className?: string;
  onOpenChange?: () => void;
  isOpen?: boolean;
  sidebarWidth?: number;
  classNames?: {
    wrapper?: string;
    base?: string;
    body?: string;
    closeButton?: string;
  };
  sidebarPlacement?: "left" | "right";
  hideCloseButton?: boolean;
}

const SidebarDrawer = React.forwardRef<HTMLDivElement, SidebarDrawerProps>(
  (
    {
      children,
      className,
      onOpenChange,
      isOpen,
      sidebarWidth = 288,
      classNames = {},
      sidebarPlacement = "left",
      hideCloseButton,
    },
    ref
  ) => {
    const motionProps = React.useMemo(() => {
      return {
        variants: {
          enter: {
            x: 0,
            transition: {
              x: {
                duration: 0.3,
                ease: [0.32, 0.72, 0, 1],
              },
            },
          },
          exit: {
            x: sidebarPlacement === "left" ? -sidebarWidth : sidebarWidth,
            transition: {
              x: {
                duration: 0.2,
                ease: [0.32, 0.72, 0, 1],
              },
            },
          },
        },
      };
    }, [sidebarWidth, sidebarPlacement]);

    return (
      <>
        <Drawer
          ref={ref}
          classNames={{
            ...classNames,
            wrapper: cn("!w-[--sidebar-width]", classNames?.wrapper, {
              "!items-start !justify-start": sidebarPlacement === "left",
              "!items-end !justify-end": sidebarPlacement === "right",
            }),
            base: cn(
              "w-[--sidebar-width] !m-0 !p-0 h-full max-h-full",
              classNames?.base,
              className,
              {
                "inset-y-0 left-0 max-h-none rounded-l-none !justify-start":
                  sidebarPlacement === "left",
                "inset-y-0 right-0 max-h-none rounded-r-none !justify-end":
                  sidebarPlacement === "right",
              }
            ),
            body: cn("p-0", classNames?.body),
            closeButton: cn("z-50", classNames?.closeButton),
          }}
          hideCloseButton={hideCloseButton}
          isOpen={isOpen}
          motionProps={motionProps}
          radius="none"
          scrollBehavior="inside"
          style={
            {
              "--sidebar-width": `${sidebarWidth}px`,
            } as React.CSSProperties
          }
          onOpenChange={onOpenChange}
        >
          <DrawerContent>
            <DrawerBody>{children}</DrawerBody>
          </DrawerContent>
        </Drawer>
        <div
          className={cn(
            "hidden h-full max-w-[--sidebar-width] overflow-x-hidden overflow-y-auto sm:flex",
            className
          )}
          style={
            {
              "--sidebar-width": `${sidebarWidth}px`,
            } as React.CSSProperties
          }
        >
          {children}
        </div>
      </>
    );
  }
);

SidebarDrawer.displayName = "SidebarDrawer";

export default SidebarDrawer;
