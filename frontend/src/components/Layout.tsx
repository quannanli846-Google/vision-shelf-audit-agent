import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { VisionProviderSwitch } from "./VisionProviderSwitch";

const navLinkClasses = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
    isActive ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
  }`;

/** Minimal app shell: a header with the product name and a two-item nav.
 * Deliberately not a full dashboard chrome - the point is to frame the
 * workflow, not decorate it. */
export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
              <svg className="h-4.5 w-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
            </div>
            <span className="text-lg font-semibold text-gray-900">Vision AI Shelf Audit</span>
          </div>
          <div className="flex items-center gap-4">
            <nav className="flex items-center gap-1">
              <NavLink to="/" className={navLinkClasses} end>
                New Audit
              </NavLink>
              <NavLink to="/history" className={navLinkClasses}>
                Audit History
              </NavLink>
            </nav>
            <VisionProviderSwitch />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
