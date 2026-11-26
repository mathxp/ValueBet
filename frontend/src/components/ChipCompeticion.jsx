import "./ChipCompeticion.css";

const CLASE = {
  "Liga de Primera": "liga",
  "Copa Chile": "copa-chile",
  "Copa de la Liga": "copa-liga",
};

export default function ChipCompeticion({ nombre }) {
  return <span className={`chip-comp chip-comp--${CLASE[nombre] ?? "otra"}`}>{nombre}</span>;
}
