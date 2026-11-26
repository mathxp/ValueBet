import { useState } from "react";

import "./InfoBox.css";

export default function InfoBox({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="info-box">
      <button
        type="button"
        className="info-box__header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="info-box__icon" aria-hidden="true">
          ⓘ
        </span>
        <span className="info-box__title">{title}</span>
        <span className="info-box__chevron" aria-hidden="true">
          {open ? "−" : "+"}
        </span>
      </button>
      {open && <div className="info-box__body">{children}</div>}
    </div>
  );
}
