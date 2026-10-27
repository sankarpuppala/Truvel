#!/usr/bin/env python3
"""Generate a standalone turn-by-turn interactive transcript.html from transcript.md."""
import html
import os
import re

def parse_transcript(md_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Match each turn
    turn_pattern = re.compile(
        r"##\s*(\d+)\.\s*(.*?)\n\n\*\*User:\*\*\s*(.*?)\n\n\*\*What happened:\*\*\s*(.*?)(?=\n---\n|\n## Where things stand|\Z)",
        re.DOTALL,
    )
    turns = []
    for match in turn_pattern.finditer(content):
        num = int(match.group(1))
        title = match.group(2).strip().replace("", "—")
        user = match.group(3).strip().replace("", "—")
        what = match.group(4).strip().replace("", "—")
        turns.append({"num": num, "title": title, "user": user, "what": what})

    # Match "Where things stand"
    stand_match = re.search(r"## Where things stand\s*\n\n(.*?)(?=\Z)", content, re.DOTALL)
    where_things_stand = stand_match.group(1).strip() if stand_match else ""

    return turns, where_things_stand

def format_content(text: str) -> str:
    # Escape HTML
    lines = text.split("\n")
    out = []
    in_list = False
    in_sublist = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_sublist:
                out.append("</ul></li>")
                in_sublist = False
            if in_list:
                out.append("</ul>")
                in_list = False
            continue

        # Format inline formatting
        formatted = html.escape(stripped)
        formatted = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", formatted)
        formatted = re.sub(r"\*(.*?)\*", r"<em>\1</em>", formatted)
        formatted = re.sub(r"`(.*?)`", r"<code>\1</code>", formatted)

        if line.startswith("  - ") or line.startswith("    - "):
            if not in_sublist:
                out.append("<ul>")
                in_sublist = True
            content = formatted.lstrip(" -")
            out.append(f"<li>{content}</li>")
        elif line.startswith("- "):
            if in_sublist:
                out.append("</ul></li>")
                in_sublist = False
            if not in_list:
                out.append("<ul>")
                in_list = True
            content = formatted[2:]
            out.append(f"<li>{content}</li>")
        elif re.match(r"^\d+\.\s", stripped):
            if in_sublist:
                out.append("</ul></li>")
                in_sublist = False
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<div class="num-step">{formatted}</div>')
        else:
            if in_sublist:
                out.append("</ul></li>")
                in_sublist = False
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{formatted}</p>")

    if in_sublist:
        out.append("</ul></li>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)

def generate_html(turns, where_things_stand, output_path: str):
    turns_html = []
    for t in turns:
        formatted_user = html.escape(t["user"])
        formatted_user = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", formatted_user)
        formatted_user = re.sub(r"`(.*?)`", r"<code>\1</code>", formatted_user)
        formatted_user = formatted_user.replace("\n", "<br/>")

        formatted_what = format_content(t["what"])

        card = f"""
        <article class="turn-card" data-turn="{t['num']}" id="turn-{t['num']}">
          <div class="turn-header">
            <div class="turn-badge-group">
              <span class="turn-pill">Turn {t['num']}</span>
              <h2 class="turn-title">{html.escape(t['title'])}</h2>
            </div>
            <a href="#turn-{t['num']}" class="turn-anchor" title="Direct link to Turn {t['num']}">#{t['num']}</a>
          </div>

          <div class="user-bubble">
            <div class="bubble-header">
              <span class="user-avatar">👤</span>
              <span class="bubble-sender">User Prompt / Request</span>
            </div>
            <div class="bubble-text">{formatted_user}</div>
          </div>

          <details class="response-drawer">
            <summary class="response-summary">
              <div class="summary-left">
                <span class="summary-icon">💡</span>
                <span class="summary-title">Assistant Response &amp; Implementation</span>
                <span class="summary-hint">(click to collapse/expand)</span>
              </div>
              <span class="chevron-icon">▾</span>
            </summary>
            <div class="response-content">
              {formatted_what}
            </div>
          </details>
        </article>
        """
        turns_html.append(card)

    stand_html = format_content(where_things_stand)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Truvel (Pagdandi) — Turn-by-Turn Session Transcript</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --surface: #ffffff;
      --card-bg: #ffffff;
      --card-border: #e2e8f0;
      --primary: #c2410c; /* Truvel Laterite */
      --primary-light: #ffedd5;
      --text: #0f172a;
      --text-muted: #64748b;
      --line: #e2e8f0;
      --code-bg: #f1f5f9;
      --user-bg: #f8fafc;
      --user-border: #cbd5e1;
      --summary-bg: #fafaf9;
      --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
      --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.08);
      --radius: 12px;
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0b0f19;
        --surface: #111827;
        --card-bg: #111827;
        --card-border: #1f2937;
        --primary: #ea580c;
        --primary-light: #431407;
        --text: #f8fafc;
        --text-muted: #94a3b8;
        --line: #1f2937;
        --code-bg: #1e293b;
        --user-bg: #172033;
        --user-border: #334155;
        --summary-bg: #131d2e;
        --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.3);
        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.4);
      }}
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding-bottom: 80px;
    }}

    header.hero {{
      background: var(--surface);
      border-bottom: 1px solid var(--line);
      padding: 40px 20px 24px;
      text-align: center;
    }}

    .hero-badge {{
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--primary);
      background: var(--primary-light);
      padding: 4px 12px;
      border-radius: 9999px;
      margin-bottom: 12px;
    }}

    .hero h1 {{
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 8px;
    }}

    .hero p {{
      color: var(--text-muted);
      max-width: 750px;
      margin: 0 auto 20px;
      font-size: 16px;
    }}

    .stats-row {{
      display: flex;
      justify-content: center;
      gap: 16px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}

    .stat-chip {{
      background: var(--bg);
      border: 1px solid var(--line);
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 13.5px;
      font-weight: 500;
    }}

    .stat-chip strong {{
      color: var(--primary);
    }}

    /* Control bar */
    .controls-wrapper {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: color-mix(in srgb, var(--surface) 92%, transparent);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--line);
      padding: 12px 20px;
      box-shadow: var(--shadow-sm);
    }}

    .controls {{
      max-width: 900px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }}

    .search-box {{
      position: relative;
      flex: 1;
      min-width: 240px;
    }}

    .search-box input {{
      width: 100%;
      padding: 8px 14px 8px 34px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--bg);
      color: var(--text);
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s ease;
    }}

    .search-box input:focus {{
      border-color: var(--primary);
    }}

    .search-icon {{
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 14px;
      color: var(--text-muted);
      pointer-events: none;
    }}

    .btn-group {{
      display: flex;
      gap: 8px;
    }}

    button.ctrl-btn {{
      padding: 8px 14px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--text);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }}

    button.ctrl-btn:hover {{
      border-color: var(--primary);
      color: var(--primary);
    }}

    /* Main Container */
    main.container {{
      max-width: 900px;
      margin: 30px auto;
      padding: 0 20px;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}

    /* Turn card */
    .turn-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-sm);
      overflow: hidden;
      transition: box-shadow 0.2s ease;
    }}

    .turn-card:hover {{
      box-shadow: var(--shadow-md);
    }}

    .turn-header {{
      padding: 16px 20px;
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--surface) 97%, var(--primary));
    }}

    .turn-badge-group {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}

    .turn-pill {{
      background: var(--primary);
      color: #ffffff;
      font-size: 12px;
      font-weight: 700;
      padding: 3px 10px;
      border-radius: 6px;
      letter-spacing: 0.03em;
      white-space: nowrap;
    }}

    .turn-title {{
      font-size: 17px;
      font-weight: 700;
      color: var(--text);
    }}

    .turn-anchor {{
      color: var(--text-muted);
      text-decoration: none;
      font-size: 14px;
      font-weight: 600;
      opacity: 0.5;
      transition: opacity 0.15s;
    }}

    .turn-anchor:hover {{
      opacity: 1;
      color: var(--primary);
    }}

    /* User request block */
    .user-bubble {{
      padding: 18px 20px;
      background: var(--user-bg);
      border-bottom: 1px solid var(--line);
    }}

    .bubble-header {{
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
    }}

    .bubble-sender {{
      font-size: 12.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--primary);
    }}

    .bubble-text {{
      font-size: 15px;
      font-weight: 500;
      line-height: 1.5;
      color: var(--text);
    }}

    /* Collapsible response */
    details.response-drawer {{
      width: 100%;
    }}

    summary.response-summary {{
      padding: 14px 20px;
      background: var(--summary-bg);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
      font-size: 14.5px;
      font-weight: 600;
      color: var(--text);
      transition: background-color 0.15s ease;
    }}

    summary.response-summary:hover {{
      background: color-mix(in srgb, var(--summary-bg) 90%, var(--primary));
    }}

    summary.response-summary::-webkit-details-marker {{
      display: none;
    }}

    .summary-left {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .summary-icon {{
      font-size: 16px;
    }}

    .summary-hint {{
      font-size: 12.5px;
      font-weight: 400;
      color: var(--text-muted);
    }}

    .chevron-icon {{
      font-size: 18px;
      color: var(--text-muted);
      transition: transform 0.2s ease;
    }}

    details[open] .chevron-icon {{
      transform: rotate(180deg);
    }}

    .response-content {{
      padding: 20px;
      border-top: 1px solid var(--line);
      background: var(--surface);
      font-size: 14.5px;
      color: var(--text);
    }}

    .response-content p {{
      margin-bottom: 12px;
    }}

    .response-content p:last-child {{
      margin-bottom: 0;
    }}

    .response-content ul {{
      margin: 8px 0 16px 22px;
    }}

    .response-content li {{
      margin-bottom: 8px;
    }}

    .response-content ul ul {{
      margin: 6px 0 6px 20px;
    }}

    .sub-num, .num-step {{
      margin: 10px 0 6px 4px;
      font-weight: 600;
    }}

    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 13px;
      background: var(--code-bg);
      padding: 2px 6px;
      border-radius: 4px;
      color: var(--text);
      border: 1px solid var(--line);
    }}

    strong {{
      font-weight: 700;
      color: var(--text);
    }}

    /* Stand card */
    .stand-card {{
      background: var(--card-bg);
      border: 1.5px solid var(--primary);
      border-radius: var(--radius);
      padding: 24px;
      box-shadow: var(--shadow-md);
      margin-top: 16px;
    }}

    .stand-card h2 {{
      font-size: 20px;
      font-weight: 800;
      margin-bottom: 14px;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--primary);
    }}

    .stand-card ul {{
      margin-left: 20px;
    }}

    .stand-card li {{
      margin-bottom: 10px;
      font-size: 14.5px;
    }}

    footer {{
      text-align: center;
      padding: 30px 20px;
      color: var(--text-muted);
      font-size: 13.5px;
      border-top: 1px solid var(--line);
      margin-top: 40px;
    }}

    .no-results {{
      text-align: center;
      padding: 40px;
      color: var(--text-muted);
      display: none;
    }}
  </style>
</head>
<body>

  <header class="hero">
    <span class="hero-badge">Academic Verification Artifact</span>
    <h1>Truvel (Pagdandi) Build Transcript</h1>
    <p>A complete chronological record of user requests and assistant decisions, architecture, and code implementations across the entire project lifecycle.</p>
    <div class="stats-row">
      <div class="stat-chip"><strong>23</strong> Total Turns</div>
      <div class="stat-chip"><strong>18,320</strong> Seeded Places</div>
      <div class="stat-chip"><strong>10</strong> Seeded Cities + Nationwide</div>
      <div class="stat-chip"><strong>100%</strong> Tests Passing (257 Backend / 26 Frontend)</div>
    </div>
  </header>

  <div class="controls-wrapper">
    <div class="controls">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="Search prompts, decisions, keywords (e.g. auth, location, maps, docker)..." aria-label="Search turns">
      </div>
      <div class="btn-group">
        <button type="button" class="ctrl-btn" id="expandAllBtn">
          <span>▾</span> Expand All Responses
        </button>
        <button type="button" class="ctrl-btn" id="collapseAllBtn">
          <span>▸</span> Collapse All
        </button>
      </div>
    </div>
  </div>

  <main class="container" id="turnsContainer">
    {''.join(turns_html)}

    <div id="noResults" class="no-results">
      <h3>No turns match your search.</h3>
      <p>Try searching for other keywords like "auth", "location", "photos", or "docker".</p>
    </div>

    <section class="stand-card">
      <h2>🏆 Where Things Stand</h2>
      {stand_html}
    </section>
  </main>

  <footer>
    <p>Truvel Build Session Transcript &middot; Designed for Academic Verification &amp; Evaluation &middot; Generated 2026-10-27</p>
  </footer>

  <script>
    const searchInput = document.getElementById('searchInput');
    const expandAllBtn = document.getElementById('expandAllBtn');
    const collapseAllBtn = document.getElementById('collapseAllBtn');
    const turns = document.querySelectorAll('.turn-card');
    const noResults = document.getElementById('noResults');

    // Expand / Collapse all
    expandAllBtn.addEventListener('click', () => {{
      document.querySelectorAll('details.response-drawer').forEach(d => d.open = true);
    }});

    collapseAllBtn.addEventListener('click', () => {{
      document.querySelectorAll('details.response-drawer').forEach(d => d.open = false);
    }});

    // Live search filter
    searchInput.addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase().trim();
      let matches = 0;

      turns.forEach(card => {{
        const text = card.textContent.toLowerCase();
        if (!query || text.includes(query)) {{
          card.style.display = 'block';
          matches++;
        }} else {{
          card.style.display = 'none';
        }}
      }});

      noResults.style.display = (matches === 0 && query) ? 'block' : 'none';
    }});
  </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as out_fp:
        out_fp.write(html_doc)
    print(f"Generated {output_path} successfully ({len(turns)} turns).")

if __name__ == "__main__":
    md_file = "transcript.md"
    html_file = "transcript.html"
    parsed_turns, where_stand = parse_transcript(md_file)
    generate_html(parsed_turns, where_stand, html_file)
