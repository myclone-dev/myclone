import type { SVGProps } from "react";

export function GoHighLevelIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="100"
      height="100"
      viewBox="0 0 100 100"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <g id="yellow">
        <rect x="20" y="30" width="12" height="60" fill="#fdc400" />
        <path d="M32 30L26 30L32 45V30Z" fill="black" fillOpacity="0.15" />
        <path d="M26 5L44 30H8L26 5Z" fill="#fdc400" />
      </g>

      <g id="blue">
        <rect x="44" y="55" width="12" height="35" fill="#2896fb" />
        <path d="M56 55L50 55L56 70V55Z" fill="black" fillOpacity="0.15" />
        <path d="M50 30L68 55H32L50 30Z" fill="#2896fb" />
      </g>

      <g id="green">
        <rect x="68" y="30" width="12" height="60" fill="#4acf27" />
        <path d="M80 30L74 30L80 45V30Z" fill="black" fillOpacity="0.15" />
        <path d="M74 5L92 30H56L74 5Z" fill="#4acf27" />
      </g>
    </svg>
  );
}
