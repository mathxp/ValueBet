import "./InfoBox.css";

export default function InfoBox({ title, children }) {
  return (
    <div className="info-box">
      <div className="info-box__icon" aria-hidden="true">
        ⓘ
      </div>
      <div>
        {title && <p className="info-box__title">{title}</p>}
        <div className="info-box__body">{children}</div>
      </div>
    </div>
  );
}
