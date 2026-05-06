import { NavLink } from 'react-router-dom';

const Logo = () => (
  <svg width="22" height="22" viewBox="0 0 18 18" fill="none">
    <circle cx="4" cy="4" r="2.5" fill="white" opacity="0.95"/>
    <circle cx="14" cy="4" r="2.5" fill="white" opacity="0.55"/>
    <circle cx="4" cy="14" r="2.5" fill="white" opacity="0.55"/>
    <circle cx="14" cy="14" r="2.5" fill="white" opacity="0.95"/>
    <line x1="4" y1="4" x2="14" y2="14" stroke="white" strokeWidth="1.2" opacity="0.4"/>
    <line x1="14" y1="4" x2="4" y2="14" stroke="white" strokeWidth="1.2" opacity="0.4"/>
    <circle cx="9" cy="9" r="1.5" fill="white" opacity="0.7"/>
  </svg>
);

const LINKS = [
  { to: '/',           label: 'Predict' },
  { to: '/compare',    label: 'Compare' },
  { to: '/evaluate',   label: 'Evaluate'   },
  { to: '/docs',       label: 'Docs'    },
  { to: '/about',      label: 'About'   },
];

export default function Nav() {
  return (
    <nav style={styles.nav}>
      <div style={styles.logo}>
        <div style={styles.logoIcon}><Logo /></div>
        <span style={styles.logoText}>NeuralProt</span>
        <span style={styles.logoBadge}>beta</span>
      </div>

      <div style={styles.links}>
        {LINKS.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              ...styles.link,
              ...(isActive ? styles.linkActive : {}),
            })}
          >
            {label}
          </NavLink>
        ))}
      </div>

      <div style={styles.right}>
        <a href="https://github.com/cod3astro/neuralprot_beta" target="_blank" rel="noreferrer" style={styles.ghLink}>
          GitHub Repository →
        </a>
      </div>
    </nav>
  );
}

const styles = {
  nav: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 32px',
    height: '72px',
    background: 'var(--surface)',
    borderBottom: '1px solid var(--border)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    boxShadow: 'var(--shadow-sm)',
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    textDecoration: 'none',
  },
  logoIcon: {
    width: '38px',
    height: '38px',
    background: 'linear-gradient(135deg, #1D9E75, #0F6E56)',
    borderRadius: '10px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 2px 8px rgba(29,158,117,0.35)',
  },
  logoText: {
    fontSize: '24px',
    fontWeight: '700',
    color: 'var(--text-1)',
    letterSpacing: '-0.01em',
  },
  logoBadge: {
    fontSize: '13px',
    fontWeight: '600',
    color: 'var(--teal-deep)',
    background: 'var(--teal-dim)',
    padding: '3px 9px',
    borderRadius: '20px',
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
  },
  links: {
    display: 'flex',
    gap: '4px',
  },
  link: {
    fontSize: '25px',
    fontWeight: '500',
    color: 'var(--text-2)',
    padding: '10px 28px',
    borderRadius: 'var(--radius-sm)',
    textDecoration: 'none',
    transition: 'all 0.15s',
  },
  linkActive: {
    color: 'var(--text-1)',
    fontWeight: '700',
    background: 'var(--surface-2)',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    margin: '30px'
  },
  ghLink: {
    fontSize: '15px',
    fontWeight: '500',
    color: 'var(--text-3)',
    textDecoration: 'none',
  },
};