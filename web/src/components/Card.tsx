// Card section: titled panel used to lay each view's blocks out.

import type { ReactNode } from "react";

export function Card({
  title,
  note,
  children,
  className,
}: {
  title: string;
  note?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card${className ? ` ${className}` : ""}`}>
      <header className="card-head">
        <h2>{title}</h2>
        {note ? <div className="card-note">{note}</div> : null}
      </header>
      <div className="card-body">{children}</div>
    </section>
  );
}
