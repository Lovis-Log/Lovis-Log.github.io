import { useState } from 'react';

export default function DayCard({ label, title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`day-card${open ? ' open' : ''}`}>
      <div className="day-card-header" onClick={() => setOpen(!open)}>
        <h3>
          <span className="day-label">{label}</span>
          {title}
        </h3>
        <span className="toggle">▼</span>
      </div>
      {open && (
        <div className="day-card-body">
          <div className="day-card-body-inner">{children}</div>
        </div>
      )}
    </div>
  );
}
