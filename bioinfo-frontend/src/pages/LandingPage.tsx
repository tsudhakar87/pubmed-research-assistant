import { useNavigate } from 'react-router-dom';

const EXAMPLE_QUERIES = [
  'CRISPR-Cas9 off-target effects in clinical trials',
  'GLP-1 receptor agonists cardiovascular outcomes meta-analysis',
  'BRCA1 BRCA2 variant pathogenicity classification',
  'mRNA vaccine immunogenicity T cell response',
];

const FEATURES = [
  {
    label: '01 · SEARCH',
    title: 'PubMed + preprints',
    desc: 'Searches PubMed, bioRxiv, and medRxiv in parallel, then deduplicates by DOI.',
  },
  {
    label: '02 · RANK',
    title: 'Semantic relevance',
    desc: 'Each paper is scored against your query embedding (Vertex AI text-embedding-004) and sorted by cosine similarity.',
  },
  {
    label: '03 · EXTRACT',
    title: 'Structured evidence',
    desc: 'Gemini extracts study design, population size, effect size, and stance (supports / refutes / neutral) from every abstract.',
  },
  {
    label: '04 · SYNTHESIZE',
    title: 'AI summary',
    desc: 'A 350–400-word narrative synthesis with inline [n] citation links back to the ranked papers.',
  },
];

export function LandingPage() {
  const navigate = useNavigate();

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-canvas)',
      fontFamily: 'var(--font-sans)',
    }}>

      {/* Top nav */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '18px 32px',
        borderBottom: '1px solid var(--border-default)',
        background: 'var(--bg-canvas)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}>
        <div style={{
          fontFamily: 'var(--font-serif)',
          fontStyle: 'italic',
          fontWeight: 600,
          fontSize: 20,
          color: 'var(--text-navy)',
          letterSpacing: '-0.01em',
        }}>
          pub<span style={{ color: 'var(--text-teal)', fontStyle: 'normal' }}>/</span>med assistant
        </div>
        <button
          onClick={() => navigate('/login')}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--text-teal-dark)',
            background: 'transparent',
            border: '1.5px solid var(--text-teal)',
            borderRadius: 3,
            padding: '7px 16px',
            cursor: 'pointer',
          }}
        >
          Sign in
        </button>
      </div>

      {/* Hero */}
      <div style={{
        maxWidth: 720,
        margin: '0 auto',
        padding: '80px 32px 64px',
        textAlign: 'center',
      }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--text-teal-dark)',
          fontWeight: 600,
          marginBottom: 20,
        }}>
          Literature Synthesis · PubMed + bioRxiv + medRxiv
        </div>
        <h1 style={{
          fontFamily: 'var(--font-serif)',
          fontStyle: 'italic',
          fontWeight: 600,
          fontSize: 52,
          lineHeight: 1.1,
          letterSpacing: '-0.02em',
          color: 'var(--text-navy)',
          marginBottom: 20,
        }}>
          Ask a research question.<br />
          <span style={{ color: 'var(--text-teal)' }}>Get synthesized evidence.</span>
        </h1>
        <p style={{
          fontSize: 17,
          lineHeight: 1.65,
          color: 'var(--text-secondary)',
          maxWidth: 560,
          margin: '0 auto 36px',
        }}>
          Search PubMed and preprint servers, rank results by semantic similarity,
          extract structured evidence, and get an AI-synthesized summary with inline citations —
          all in one pipeline.
        </p>
        <button
          onClick={() => navigate('/login')}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#fff',
            background: 'var(--text-teal)',
            border: 'none',
            borderRadius: 3,
            padding: '13px 32px',
            cursor: 'pointer',
          }}
        >
          Get started free →
        </button>
        <div style={{
          marginTop: 12,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-muted)',
          letterSpacing: '0.04em',
        }}>
          Sign in with Google · no credit card needed
        </div>
      </div>

      {/* Example queries */}
      <div style={{
        maxWidth: 720,
        margin: '0 auto',
        padding: '0 32px 64px',
      }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          marginBottom: 14,
        }}>
          Example queries
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {EXAMPLE_QUERIES.map((q) => (
            <div
              key={q}
              style={{
                background: '#fff',
                border: '1px solid var(--border-default)',
                borderRadius: 4,
                padding: '11px 16px',
                fontFamily: 'var(--font-sans)',
                fontSize: 13.5,
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--text-teal)',
              }}>→</span>
              {q}
            </div>
          ))}
        </div>
      </div>

      {/* Demo screenshot */}
      <div style={{
        maxWidth: 960,
        margin: '0 auto',
        padding: '0 32px 64px',
      }}>
        <img
          src="/demo-screenshot.png"
          alt="pub/med assistant — metformin and gut microbiome query result"
          style={{
            width: '100%',
            border: '1px solid var(--border-default)',
            borderRadius: 6,
            boxShadow: '0 2px 8px rgba(28,36,48,.10), 0 16px 40px rgba(28,36,48,.08)',
            display: 'block',
          }}
        />
      </div>

      {/* Pipeline steps */}
      <div style={{
        background: '#fff',
        borderTop: '1px solid var(--border-default)',
        borderBottom: '1px solid var(--border-default)',
        padding: '56px 32px',
      }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            marginBottom: 36,
            textAlign: 'center',
          }}>
            How it works
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
            gap: 24,
          }}>
            {FEATURES.map((f) => (
              <div key={f.label}>
                <div style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 9.5,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--text-teal-dark)',
                  fontWeight: 600,
                  marginBottom: 8,
                }}>
                  {f.label}
                </div>
                <div style={{
                  fontFamily: 'var(--font-serif)',
                  fontWeight: 600,
                  fontSize: 16,
                  color: 'var(--text-navy)',
                  marginBottom: 6,
                }}>
                  {f.title}
                </div>
                <div style={{
                  fontSize: 13,
                  lineHeight: 1.6,
                  color: 'var(--text-secondary)',
                }}>
                  {f.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer CTA */}
      <div style={{
        borderTop: '1px solid var(--border-default)',
        padding: '48px 32px',
        textAlign: 'center',
      }}>
        <div style={{
          fontFamily: 'var(--font-serif)',
          fontStyle: 'italic',
          fontWeight: 600,
          fontSize: 26,
          color: 'var(--text-navy)',
          marginBottom: 16,
        }}>
          Ready to search the literature?
        </div>
        <button
          onClick={() => navigate('/login')}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#fff',
            background: 'var(--text-teal)',
            border: 'none',
            borderRadius: 3,
            padding: '11px 28px',
            cursor: 'pointer',
          }}
        >
          Sign in with Google
        </button>
        <div style={{
          marginTop: 32,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-muted)',
          letterSpacing: '0.04em',
        }}>
          <a
            href="https://github.com/tsudhakar87/pubmed-research-assistant"
            style={{ color: 'var(--text-muted)', textDecoration: 'underline dotted' }}
            target="_blank"
            rel="noopener noreferrer"
          >
            View source on GitHub
          </a>
        </div>
      </div>

    </div>
  );
}
