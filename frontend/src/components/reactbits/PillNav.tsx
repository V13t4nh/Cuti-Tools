import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import './PillNav.css';

// Official React Bits source: https://reactbits.dev/components/pill-nav
// CUTI adaptation: History API callback buttons replace router links; CUTI's
// existing four-item mobile bottom navigation replaces the optional menu.
export type PillNavItem = { label: string; shortLabel?: string; href: string; ariaLabel?: string };

export interface PillNavProps {
  items: PillNavItem[];
  activeHref?: string;
  onNavigate: (href: string) => void;
  className?: string;
  ease?: string;
  baseColor?: string;
  pillColor?: string;
  hoveredPillTextColor?: string;
  pillTextColor?: string;
  initialLoadAnimation?: boolean;
}

const PillNav: React.FC<PillNavProps> = ({
  items,
  activeHref,
  onNavigate,
  className = '',
  ease = 'power3.easeOut',
  baseColor = 'var(--ink)',
  pillColor = 'var(--surface-muted)',
  hoveredPillTextColor = 'var(--surface)',
  pillTextColor,
  initialLoadAnimation = false
}) => {
  const navItemsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (initialLoadAnimation && navItemsRef.current && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      gsap.set(navItemsRef.current, { width: 0, overflow: 'hidden' });
      gsap.to(navItemsRef.current, { width: 'auto', duration: 0.6, ease });
    }
  }, [items, ease, initialLoadAnimation]);

  const cssVars = {
    ['--base']: baseColor,
    ['--pill-bg']: pillColor,
    ['--hover-text']: hoveredPillTextColor,
    ['--pill-text']: pillTextColor ?? baseColor
  } as React.CSSProperties;

  return (
    <div className="pill-nav-container">
      <nav className={`pill-nav ${className}`} aria-label="Điều hướng chính" style={cssVars}>
        <div className="pill-nav-items" ref={navItemsRef}>
          <ul className="pill-list" role="menubar">
            {items.map((item) => (
              <li key={item.href} role="none">
                <button
                  type="button"
                  role="menuitem"
                  className={`pill${activeHref === item.href ? ' is-active' : ''}`}
                  aria-label={item.ariaLabel || item.label}
                  aria-current={activeHref === item.href ? 'page' : undefined}
                  onClick={() => onNavigate(item.href)}
                >
                  <span className="label-stack">
                    <span className="pill-label">
                      <span className="label-full">{item.label}</span>
                      <span className="label-short">{item.shortLabel ?? item.label}</span>
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </nav>
    </div>
  );
};

export default PillNav;
export { PillNav };
