import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';
import './PillNav.css';

// Official React Bits source: https://reactbits.dev/components/pill-nav
// CUTI adaptation: History API callback buttons replace router links; CUTI's
// existing four-item mobile bottom navigation replaces the optional menu.
export type PillNavItem = { label: string; href: string; ariaLabel?: string };

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
  initialLoadAnimation = true
}) => {
  const circleRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const tlRefs = useRef<Array<gsap.core.Timeline | null>>([]);
  const activeTweenRefs = useRef<Array<gsap.core.Tween | null>>([]);
  const navItemsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const layout = () => {
      circleRefs.current.forEach(circle => {
        if (!circle?.parentElement) return;
        const pill = circle.parentElement as HTMLElement;
        const { width: w, height: h } = pill.getBoundingClientRect();
        const R = ((w * w) / 4 + h * h) / (2 * h);
        const D = Math.ceil(2 * R) + 2;
        const delta = Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1;
        const originY = D - delta;
        circle.style.width = `${D}px`;
        circle.style.height = `${D}px`;
        circle.style.bottom = `-${delta}px`;
        gsap.set(circle, { xPercent: -50, scale: 0, transformOrigin: `50% ${originY}px` });
        const label = pill.querySelector<HTMLElement>('.pill-label');
        const hover = pill.querySelector<HTMLElement>('.pill-label-hover');
        if (label) gsap.set(label, { y: 0 });
        if (hover) gsap.set(hover, { y: h + 12, opacity: 0 });
        const index = circleRefs.current.indexOf(circle);
        if (index === -1) return;
        tlRefs.current[index]?.kill();
        const tl = gsap.timeline({ paused: true });
        tl.to(circle, { scale: 1.2, xPercent: -50, duration: 2, ease, overwrite: 'auto' }, 0);
        if (label) tl.to(label, { y: -(h + 8), duration: 2, ease, overwrite: 'auto' }, 0);
        if (hover) tl.to(hover, { y: 0, opacity: 1, duration: 2, ease, overwrite: 'auto' }, 0);
        tlRefs.current[index] = tl;
      });
    };
    layout();
    window.addEventListener('resize', layout);
    if (document.fonts?.ready) document.fonts.ready.then(layout).catch(() => {});
    if (initialLoadAnimation && navItemsRef.current && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      gsap.set(navItemsRef.current, { width: 0, overflow: 'hidden' });
      gsap.to(navItemsRef.current, { width: 'auto', duration: 0.6, ease });
    }
    return () => {
      window.removeEventListener('resize', layout);
      tlRefs.current.forEach(t => t?.kill());
    };
  }, [items, ease, initialLoadAnimation]);

  const handleEnter = (i: number) => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tl = tlRefs.current[i];
    if (!tl) return;
    activeTweenRefs.current[i]?.kill();
    activeTweenRefs.current[i] = tl.tweenTo(tl.duration(), { duration: 0.3, ease, overwrite: 'auto' });
  };
  const handleLeave = (i: number) => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const tl = tlRefs.current[i];
    if (!tl) return;
    activeTweenRefs.current[i]?.kill();
    activeTweenRefs.current[i] = tl.tweenTo(0, { duration: 0.2, ease, overwrite: 'auto' });
  };
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
            {items.map((item, i) => (
              <li key={item.href} role="none">
                <button
                  type="button"
                  role="menuitem"
                  className={`pill${activeHref === item.href ? ' is-active' : ''}`}
                  aria-label={item.ariaLabel || item.label}
                  aria-current={activeHref === item.href ? 'page' : undefined}
                  onClick={() => onNavigate(item.href)}
                  onMouseEnter={() => handleEnter(i)}
                  onMouseLeave={() => handleLeave(i)}
                >
                  <span className="hover-circle" aria-hidden="true" ref={el => { circleRefs.current[i] = el; }} />
                  <span className="label-stack">
                    <span className="pill-label">{item.label}</span>
                    <span className="pill-label-hover" aria-hidden="true">{item.label}</span>
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
