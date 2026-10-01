import { useEffect, useMemo, useState } from "react";
import {
  ApiOutlined,
  ArrowRightOutlined,
  CheckOutlined,
  CloudServerOutlined,
  CodeOutlined,
  CopyOutlined,
  DatabaseOutlined,
  GlobalOutlined,
  MenuOutlined,
  PlayCircleOutlined,
  RadarChartOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import "./earthscope.css";

const navItems = [
  { label: "Product", href: "#product" },
  { label: "Solutions", href: "#solutions" },
  { label: "Developers", href: "#developers" },
  { label: "Pricing", href: "#pricing" },
  { label: "Resources", href: "#resources" },
];

const stars = [
  [8, 14, 2], [14, 31, 1], [21, 8, 1], [28, 22, 2], [35, 11, 1], [42, 28, 1],
  [49, 16, 2], [56, 5, 1], [64, 24, 1], [72, 12, 2], [79, 29, 1], [86, 8, 1],
  [93, 20, 2], [5, 49, 1], [12, 67, 2], [19, 44, 1], [27, 59, 1], [34, 39, 2],
  [41, 71, 1], [48, 51, 1], [55, 64, 2], [62, 43, 1], [69, 76, 1], [77, 53, 2],
  [84, 68, 1], [91, 46, 1], [97, 61, 2], [9, 88, 1], [18, 79, 1], [26, 93, 2],
  [37, 84, 1], [46, 95, 1], [58, 87, 2], [67, 96, 1], [78, 83, 1], [89, 91, 2],
];

const features = [
  {
    eyebrow: "01 / UNIFIED ACCESS",
    title: "One endpoint. Every satellite source.",
    copy: "Query optical, SAR, elevation, weather, and change-detection products through one stable contract. No provider-specific glue code.",
    bullets: ["Consistent geometry and time filters", "Provider-aware fallback routing", "Cloud-native delivery formats"],
    icon: <ApiOutlined />,
    visual: "api",
  },
  {
    eyebrow: "02 / DEVELOPER SPEED",
    title: "Ship geospatial products in hours, not quarters.",
    copy: "Typed SDKs, signed assets, webhooks, and a transparent job model give your team a production path from first request to global scale.",
    bullets: ["Python, TypeScript, and REST", "Async jobs with delivery webhooks", "Copy-ready examples for every endpoint"],
    icon: <CodeOutlined />,
    visual: "sdk",
  },
  {
    eyebrow: "03 / BUILT TO OPERATE",
    title: "Reliable data pipelines across clouds and borders.",
    copy: "EarthScope normalizes source metadata, tracks lineage, and keeps retrieval fast with an edge-aware delivery layer.",
    bullets: ["99.99% API availability target", "Regional routing and audit logs", "Usage controls at workspace level"],
    icon: <CloudServerOutlined />,
    visual: "network",
  },
];

const testimonials = [
  {
    quote: "EarthScope replaced four brittle vendor integrations. Our imagery workflow became simpler and substantially easier to audit.",
    name: "Maya Chen",
    role: "VP Engineering, Terragrid",
  },
  {
    quote: "We went from raw AOI polygons to delivered analysis-ready scenes in a single sprint. The SDK feels designed by practitioners.",
    name: "Jon Bell",
    role: "Geospatial Lead, Northstar",
  },
  {
    quote: "The predictable data model lets our product team focus on decisions, not remote-sensing infrastructure.",
    name: "Elena Rossi",
    role: "Founder, Fieldline AI",
  },
];

const faqs = [
  ["What data sources are available?", "EarthScope unifies optical, SAR, elevation, weather, and derived analytics from a growing network of commercial and open-data providers."],
  ["Can I use my own cloud storage?", "Yes. Growth and Enterprise workspaces can deliver assets to customer-managed object storage with scoped credentials and audit logs."],
  ["How does usage-based billing work?", "Plans include monthly request and processing credits. Overage is metered transparently by endpoint, data class, and processing workload."],
  ["Do you support private or regulated workloads?", "Enterprise deployments support regional routing, private networking, custom retention controls, and dedicated support agreements."],
];

const apiExamples = {
  scenes: {
    label: "Search scenes",
    method: "POST",
    path: "/v1/scenes/search",
    code: `const scenes = await earthscope.scenes.search({\n  intersects: aoi,\n  capturedAfter: "2026-01-01",\n  cloudCover: { max: 12 },\n  sources: ["optical", "sar"]\n});`,
  },
  analytics: {
    label: "Run analysis",
    method: "POST",
    path: "/v1/analytics/run",
    code: `const job = await earthscope.analytics.run({\n  sceneIds: scenes.items.map(({ id }) => id),\n  pipeline: "vegetation-change",\n  delivery: { format: "cog" }\n});`,
  },
  delivery: {
    label: "Get delivery",
    method: "GET",
    path: "/v1/jobs/{job_id}",
    code: `const delivery = await earthscope.jobs.wait(job.id);\n\nconsole.log(delivery.assets);\n// Signed, analysis-ready assets with lineage metadata`,
  },
};

type ApiExampleKey = keyof typeof apiExamples;

function LogoMark() {
  return (
    <span className="earthscope-logo-mark" aria-hidden="true">
      <GlobalOutlined />
      <span className="earthscope-logo-orbit" />
    </span>
  );
}

function HeroVisual() {
  return (
    <div className="earthscope-orbit-stage" aria-label="Live satellite network visualization">
      {stars.map(([left, top, size], index) => (
        <span
          className="earthscope-star"
          key={`${left}-${top}-${index}`}
          style={{ left: `${left}%`, top: `${top}%`, width: size, height: size }}
        />
      ))}
      <span className="earthscope-orbit earthscope-orbit--one" />
      <span className="earthscope-orbit earthscope-orbit--two" />
      <span className="earthscope-orbit earthscope-orbit--three" />
      <div className="earthscope-planet">
        <GlobalOutlined />
        <span className="earthscope-planet-grid earthscope-planet-grid--one" />
        <span className="earthscope-planet-grid earthscope-planet-grid--two" />
      </div>
      <span className="earthscope-satellite earthscope-satellite--one"><RocketOutlined /></span>
      <span className="earthscope-satellite earthscope-satellite--two"><RadarChartOutlined /></span>
      <span className="earthscope-satellite earthscope-satellite--three"><ApiOutlined /></span>
      <span className="earthscope-signal earthscope-signal--one" />
      <span className="earthscope-signal earthscope-signal--two" />
      <div className="earthscope-orbit-status">
        <span className="earthscope-live-dot" />
        LIVE CONSTELLATION
        <strong>148 active feeds</strong>
      </div>
    </div>
  );
}

function FeatureVisual({ type }: { type: string }) {
  if (type === "api") {
    return (
      <div className="earthscope-feature-console">
        <div className="earthscope-console-bar"><span /><span /><span /><small>api.earthscope.dev</small></div>
        <pre><code><b>POST</b> /v1/scenes/search{"\n\n"}{`{\n  "intersects": "aoi.geojson",\n  "captured_after": "2026-01-01",\n  "resolution": "10m"\n}`}</code></pre>
        <div className="earthscope-console-result"><CheckOutlined /> 36 scenes normalized in 418ms</div>
      </div>
    );
  }
  if (type === "sdk") {
    return (
      <div className="earthscope-sdk-grid">
        <div><CodeOutlined /><strong>TypeScript</strong><span>Typed client</span></div>
        <div><span className="earthscope-language-mark">Py</span><strong>Python</strong><span>Async SDK</span></div>
        <div><ApiOutlined /><strong>REST</strong><span>OpenAPI spec</span></div>
        <div><ThunderboltOutlined /><strong>Webhooks</strong><span>Event delivery</span></div>
      </div>
    );
  }
  return (
    <div className="earthscope-network-map">
      <span className="earthscope-network-node earthscope-network-node--a"><DatabaseOutlined /></span>
      <span className="earthscope-network-node earthscope-network-node--b"><CloudServerOutlined /></span>
      <span className="earthscope-network-node earthscope-network-node--c"><SafetyCertificateOutlined /></span>
      <span className="earthscope-network-node earthscope-network-node--d"><GlobalOutlined /></span>
      <span className="earthscope-network-line earthscope-network-line--one" />
      <span className="earthscope-network-line earthscope-network-line--two" />
      <span className="earthscope-network-line earthscope-network-line--three" />
      <div className="earthscope-network-caption">Multi-region delivery fabric</div>
    </div>
  );
}

export default function EarthScopeLanding() {
  useEffect(() => {
    document.documentElement.classList.add("earthscope-scroll-smooth");
    return () => document.documentElement.classList.remove("earthscope-scroll-smooth");
  }, []);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [annualBilling, setAnnualBilling] = useState(true);
  const [activeApiExample, setActiveApiExample] = useState<ApiExampleKey>("scenes");
  const [copied, setCopied] = useState(false);
  const [openFaq, setOpenFaq] = useState(0);
  const activeExample = apiExamples[activeApiExample];

  const prices = useMemo(() => ({
    starter: annualBilling ? 39 : 49,
    growth: annualBilling ? 119 : 149,
  }), [annualBilling]);

  const copyExample = async () => {
    await navigator.clipboard?.writeText(activeExample.code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div className="earthscope-page">
      <div className="earthscope-announcement">
        <span>NEW</span>
        Global SAR coverage is now available in the Unified Scenes API.
        <a href="#developers">Explore the release <ArrowRightOutlined /></a>
      </div>

      <header className="earthscope-header">
        <a className="earthscope-brand" href="#top" aria-label="EarthScope home">
          <LogoMark />
          <span>EarthScope</span>
        </a>
        <nav className={mobileMenuOpen ? "earthscope-nav is-open" : "earthscope-nav"} aria-label="EarthScope navigation">
          {navItems.map((item) => <a key={item.href} href={item.href} onClick={() => setMobileMenuOpen(false)}>{item.label}</a>)}
        </nav>
        <div className="earthscope-header-actions">
          <Link className="earthscope-login-link" to="/login">Sign in</Link>
          <Link className="earthscope-button earthscope-button--small" to="/register">Get started</Link>
          <button
            className="earthscope-menu-button"
            aria-label="Toggle navigation"
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen((value) => !value)}
            type="button"
          >
            <MenuOutlined />
          </button>
        </div>
      </header>

      <main id="top">
        <section className="earthscope-hero">
          <div className="earthscope-hero-copy">
            <div className="earthscope-kicker"><span /> PLANETARY DATA INFRASTRUCTURE</div>
            <h1>Satellite data,<br /><em>without the complexity.</em></h1>
            <p>
              One API for discovering, processing, and delivering global Earth observation data—built for teams shipping real products.
            </p>
            <div className="earthscope-hero-actions">
              <Link className="earthscope-button" to="/register">Start building free <ArrowRightOutlined /></Link>
              <a className="earthscope-text-button" href="#developers"><PlayCircleOutlined /> View API explorer</a>
            </div>
            <div className="earthscope-proof">
              <span><CheckOutlined /> No credit card</span>
              <span><CheckOutlined /> 10k free requests</span>
              <span><CheckOutlined /> Cancel anytime</span>
            </div>
          </div>
          <HeroVisual />
        </section>

        <section className="earthscope-trust-strip" aria-label="EarthScope platform metrics">
          <div><strong>180+</strong><span>countries covered</span></div>
          <div><strong>24 PB</strong><span>catalogued imagery</span></div>
          <div><strong>418 ms</strong><span>median search latency</span></div>
          <div><strong>99.99%</strong><span>API availability target</span></div>
          <div><strong>10 m</strong><span>global optical baseline</span></div>
        </section>

        <section className="earthscope-section earthscope-intro" id="product">
          <div className="earthscope-section-heading">
            <span>THE PLATFORM</span>
            <h2>From area of interest to analysis-ready data.</h2>
            <p>EarthScope removes the operational layers between your product and the world’s observation systems.</p>
          </div>
          <div className="earthscope-capability-row">
            <div><RadarChartOutlined /><strong>Discover</strong><span>Search by space, time, quality, and source.</span></div>
            <ArrowRightOutlined />
            <div><ApiOutlined /><strong>Normalize</strong><span>One metadata and geometry contract.</span></div>
            <ArrowRightOutlined />
            <div><ThunderboltOutlined /><strong>Process</strong><span>Run common geospatial pipelines on demand.</span></div>
            <ArrowRightOutlined />
            <div><CloudServerOutlined /><strong>Deliver</strong><span>Stream or export assets to your cloud.</span></div>
          </div>
        </section>

        <section className="earthscope-feature-stack" id="solutions">
          {features.map((feature, index) => (
            <article className={index % 2 ? "earthscope-feature earthscope-feature--reverse" : "earthscope-feature"} key={feature.title}>
              <div className="earthscope-feature-copy">
                <div className="earthscope-feature-icon">{feature.icon}</div>
                <span className="earthscope-eyebrow">{feature.eyebrow}</span>
                <h2>{feature.title}</h2>
                <p>{feature.copy}</p>
                <ul>{feature.bullets.map((bullet) => <li key={bullet}><CheckOutlined /> {bullet}</li>)}</ul>
                <a href="#developers">Explore capability <ArrowRightOutlined /></a>
              </div>
              <FeatureVisual type={feature.visual} />
            </article>
          ))}
        </section>

        <section className="earthscope-section earthscope-developers" id="developers">
          <div className="earthscope-section-heading earthscope-section-heading--left">
            <span>FOR DEVELOPERS</span>
            <h2>Explore the API before you integrate.</h2>
            <p>Switch endpoints, inspect the request shape, and copy a production-ready SDK example.</p>
          </div>
          <div className="earthscope-api-explorer">
            <div className="earthscope-api-sidebar">
              <small>EARTHSCOPE API</small>
              {(Object.entries(apiExamples) as [ApiExampleKey, typeof apiExamples[ApiExampleKey]][]).map(([key, example]) => (
                <button
                  className={activeApiExample === key ? "is-active" : ""}
                  key={key}
                  onClick={() => { setActiveApiExample(key); setCopied(false); }}
                  type="button"
                >
                  <span>{example.method}</span>{example.label}
                </button>
              ))}
              <div className="earthscope-api-health"><span /> All systems operational</div>
            </div>
            <div className="earthscope-api-panel">
              <div className="earthscope-api-path"><b>{activeExample.method}</b><code>{activeExample.path}</code></div>
              <pre><code>{activeExample.code}</code></pre>
              <button type="button" className="earthscope-copy-button" onClick={() => void copyExample()}>
                {copied ? <CheckOutlined /> : <CopyOutlined />} {copied ? "Copied" : "Copy example"}
              </button>
            </div>
          </div>
        </section>

        <section className="earthscope-section earthscope-pricing" id="pricing">
          <div className="earthscope-section-heading">
            <span>PRICING</span>
            <h2>Start small. Scale to planetary.</h2>
            <p>Transparent platform access with usage that grows alongside your product.</p>
          </div>
          <div className="earthscope-billing-toggle" aria-label="Billing frequency">
            <button className={!annualBilling ? "is-active" : ""} onClick={() => setAnnualBilling(false)} type="button">Monthly</button>
            <button className={annualBilling ? "is-active" : ""} onClick={() => setAnnualBilling(true)} type="button">Annual <span>save 20%</span></button>
          </div>
          <div className="earthscope-pricing-grid">
            <article>
              <span>STARTER</span><h3>${prices.starter}<small>/month</small></h3><p>For prototypes and early production workloads.</p>
              <ul><li><CheckOutlined /> 100k API requests</li><li><CheckOutlined /> 250 processing credits</li><li><CheckOutlined /> Community support</li></ul>
              <Link to="/register">Start free</Link>
            </article>
            <article className="is-featured">
              <div className="earthscope-plan-badge">MOST POPULAR</div>
              <span>GROWTH</span><h3>${prices.growth}<small>/month</small></h3><p>For teams operating customer-facing products.</p>
              <ul><li><CheckOutlined /> 1M API requests</li><li><CheckOutlined /> 4,000 processing credits</li><li><CheckOutlined /> Webhooks and cloud delivery</li><li><CheckOutlined /> Priority support</li></ul>
              <Link to="/register">Start building</Link>
            </article>
            <article>
              <span>ENTERPRISE</span><h3>Custom</h3><p>For high-volume, regulated, or private deployments.</p>
              <ul><li><CheckOutlined /> Committed capacity</li><li><CheckOutlined /> Regional data controls</li><li><CheckOutlined /> Private networking</li><li><CheckOutlined /> Dedicated support</li></ul>
              <a href="mailto:sales@earthscope.dev">Talk to sales</a>
            </article>
          </div>
        </section>

        <section className="earthscope-section earthscope-testimonials">
          <div className="earthscope-section-heading"><span>CUSTOMER SIGNAL</span><h2>Built with teams observing what matters.</h2></div>
          <div className="earthscope-testimonial-grid">
            {testimonials.map((item) => (
              <figure key={item.name}>
                <blockquote>“{item.quote}”</blockquote>
                <figcaption><span>{item.name.split(" ").map((part) => part[0]).join("")}</span><div><strong>{item.name}</strong><small>{item.role}</small></div></figcaption>
              </figure>
            ))}
          </div>
        </section>

        <section className="earthscope-section earthscope-faq" id="resources">
          <div className="earthscope-section-heading earthscope-section-heading--left"><span>FAQ</span><h2>Questions, answered.</h2></div>
          <div className="earthscope-faq-list">
            {faqs.map(([question, answer], index) => (
              <article key={question}>
                <button type="button" onClick={() => setOpenFaq(openFaq === index ? -1 : index)} aria-expanded={openFaq === index}>
                  <span>{question}</span><b>{openFaq === index ? "−" : "+"}</b>
                </button>
                {openFaq === index && <p>{answer}</p>}
              </article>
            ))}
          </div>
        </section>

        <section className="earthscope-final-cta">
          <div><span>READY FOR ORBIT</span><h2>Build with the planet in your stack.</h2><p>Start free, search live data, and ship your first Earth observation workflow today.</p></div>
          <div><Link className="earthscope-button" to="/register">Create your workspace <ArrowRightOutlined /></Link><a href="mailto:sales@earthscope.dev">Contact sales</a></div>
        </section>
      </main>

      <footer className="earthscope-footer">
        <div className="earthscope-footer-brand"><a className="earthscope-brand" href="#top"><LogoMark /><span>EarthScope</span></a><p>Unified satellite data infrastructure for builders.</p></div>
        <div><strong>Platform</strong><a href="#product">Product</a><a href="#developers">API</a><a href="#pricing">Pricing</a></div>
        <div><strong>Resources</strong><a href="#resources">FAQ</a><a href="mailto:support@earthscope.dev">Support</a><a href="#developers">Status</a></div>
        <div><strong>Company</strong><a href="mailto:hello@earthscope.dev">Contact</a><Link to="/login">Sign in</Link><Link to="/register">Get started</Link></div>
        <small>© 2026 EarthScope Systems. All systems observing.</small>
      </footer>
    </div>
  );
}
