import { Link } from "@heroui/link";

import { Navbar } from "@/components/navbar";

export default function DefaultLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="relative flex flex-col h-screen">
      <Navbar />
      <main className="w-full max-w-[1800px] mx-auto px-6 flex-grow">
        {children}
      </main>
    </div>
  );
}
