export function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="page-heading"><span className="kicker">{eyebrow}</span><h1>{title}</h1><p className="lede">{description}</p></header>
}
