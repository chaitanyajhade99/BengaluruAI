"""Generate BengaluruAI pitch deck PDF"""
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm
import os

W, H = A4  # 595 x 842

# ── Palette ──────────────────────────────────────────────────────────────────
BG      = HexColor('#0a0e1a')
BG2     = HexColor('#0f1524')
CARD    = HexColor('#1a2240')
ACCENT  = HexColor('#4f7cff')
GREEN   = HexColor('#00d4aa')
AMBER   = HexColor('#ffb800')
RED     = HexColor('#ff3860')
PURPLE  = HexColor('#7b5ff7')
TEXT    = HexColor('#e8eaf6')
TEXT2   = HexColor('#8a9cc8')
TEXT3   = HexColor('#5a6b9a')
BORDER  = HexColor('#1e2d55')

def slide(c, num, total=8):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    # Page number
    c.setFillColor(TEXT3)
    c.setFont('Helvetica', 9)
    c.drawRightString(W - 24, 20, f"{num} / {total}")
    # Bottom bar
    c.setFillColor(ACCENT)
    c.rect(0, 0, W * (num/total), 2, fill=1, stroke=0)

def header_tag(c, text, y, color=ACCENT):
    c.setFillColor(color)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(48, y, text.upper())

def heading(c, text, y, size=28, color=TEXT):
    c.setFillColor(color)
    c.setFont('Helvetica-Bold', size)
    c.drawString(48, y, text)

def body(c, text, y, size=13, color=TEXT2, x=48, maxW=500):
    c.setFillColor(color)
    c.setFont('Helvetica', size)
    # Simple word wrap
    words = text.split()
    line, lines = [], []
    for w in words:
        test = ' '.join(line + [w])
        if c.stringWidth(test, 'Helvetica', size) < maxW:
            line.append(w)
        else:
            lines.append(' '.join(line))
            line = [w]
    if line:
        lines.append(' '.join(line))
    for i, l in enumerate(lines):
        c.drawString(x, y - i * (size + 4), l)
    return y - len(lines) * (size + 4)

def card_rect(c, x, y, w, h, fill=CARD, radius=8):
    c.setFillColor(fill)
    c.setStrokeColor(BORDER)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)

def accent_bar(c, x, y, h=H*0.6, color=ACCENT, w=3):
    c.setFillColor(color)
    c.rect(x, y, w, h, fill=1, stroke=0)

def stat_box(c, x, y, w, h, value, label, color=ACCENT):
    card_rect(c, x, y, w, h)
    c.setFillColor(color)
    c.setFont('Helvetica-Bold', 28)
    c.drawCentredString(x + w/2, y + h - 42, value)
    c.setFillColor(TEXT3)
    c.setFont('Helvetica', 10)
    c.drawCentredString(x + w/2, y + 14, label)
    # top accent
    c.setFillColor(color)
    c.rect(x, y + h - 3, w, 3, fill=1, stroke=0)

def bullet(c, x, y, text, color=ACCENT, size=12):
    c.setFillColor(color)
    c.circle(x + 5, y + 4, 3, fill=1, stroke=0)
    c.setFillColor(TEXT)
    c.setFont('Helvetica', size)
    c.drawString(x + 16, y, text)

OUT = '/home/claude/gridlock_project/submission/BengaluruAI_Pitch_Deck.pdf'
c = canvas.Canvas(OUT, pagesize=A4)

# ════════════════════════════════════════════════════════════════════════
# SLIDE 1 — COVER
# ════════════════════════════════════════════════════════════════════════
slide(c, 1)
# Left accent strip
c.setFillColor(ACCENT)
c.rect(0, 0, 4, H, fill=1, stroke=0)
# Gradient feel - overlay rectangles
for i, alpha in enumerate([0.03, 0.02, 0.01]):
    c.setFillColor(HexColor('#4f7cff'))
    c.setFillAlpha(alpha)
    c.rect(0, H * (0.3 + i*0.15), W, H * 0.15, fill=1, stroke=0)
c.setFillAlpha(1)

# Badge
card_rect(c, 48, H - 90, 160, 28, fill=HexColor('#0d1830'))
c.setFillColor(ACCENT)
c.setFont('Helvetica-Bold', 9)
c.drawString(60, H - 82, 'FLIPKART GRIDLOCK 2.0 · THEME 2')

heading(c, 'BengaluruAI', H - 150, size=46, color=TEXT)
heading(c, 'Traffic Intelligence', H - 195, size=36, color=TEXT2)

c.setFillColor(ACCENT)
c.rect(48, H - 215, 80, 3, fill=1, stroke=0)

body(c, 'AI-powered event-driven congestion forecasting for Bengaluru traffic command.', H - 245, size=15, color=TEXT2)
body(c, 'Predicts road closure probability, event duration, and recommends optimal', H - 270, size=13, color=TEXT3)
body(c, 'manpower deployment and diversion plans from historical event data.', H - 287, size=13, color=TEXT3)

# 3 pillars
for i, (icon, label, col) in enumerate([
    ('PREDICT', 'Closure probability & duration', ACCENT),
    ('RECOMMEND', 'Officers, barricades & diversion', PURPLE),
    ('LEARN', 'Post-event correction loop', GREEN),
]):
    bx = 48 + i * 175
    card_rect(c, bx, H - 390, 165, 80, fill=CARD)
    c.setFillColor(col)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(bx + 14, H - 330, icon)
    c.setFillColor(TEXT3)
    c.setFont('Helvetica', 10)
    words = label.split(' & ')
    c.drawString(bx + 14, H - 345, words[0])
    if len(words) > 1:
        c.drawString(bx + 14, H - 360, '& ' + words[1])

# Dataset note
c.setFillColor(TEXT3)
c.setFont('Helvetica', 10)
c.drawString(48, 70, 'Dataset: Astram Event Data (Bengaluru)  ·  8,173 events  ·  Nov 2023 – Apr 2024')

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 2 — PROBLEM STATEMENT
# ════════════════════════════════════════════════════════════════════════
slide(c, 2)
accent_bar(c, 0, 0)

header_tag(c, 'The problem', H - 60)
heading(c, 'Bengaluru loses thousands of', H - 100, size=26)
heading(c, 'officer-hours to reactive deployment', H - 133, size=26)

# 3 pain cards
pains = [
    ('No advance impact score', 'Events are assessed on the ground, not before deployment. Officers arrive without a congestion forecast.', RED),
    ('Patrol-based, not data-driven', 'Resource allocation depends on officer experience. No quantification of which corridors need what.', AMBER),
    ('Zero post-event learning', 'After every event closes, the data vanishes. Predictions never improve from past outcomes.', PURPLE),
]
for i, (title, desc, col) in enumerate(pains):
    y = H - 230 - i * 140
    card_rect(c, 48, y, W - 96, 120)
    c.setFillColor(col)
    c.rect(48, y, 4, 120, fill=1, stroke=0)
    c.setFillColor(TEXT)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(68, y + 90, title)
    body(c, desc, y + 70, size=11, color=TEXT2, x=68, maxW=470)

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 3 — DATASET EDA
# ════════════════════════════════════════════════════════════════════════
slide(c, 3)
accent_bar(c, 0, 0, color=GREEN)

header_tag(c, 'Dataset insights', H - 60, color=GREEN)
heading(c, '8,173 real-world events,', H - 100, size=26)
heading(c, 'rich with actionable signal', H - 133, size=26)

# Stat boxes row 1
for i, (v, l, col) in enumerate([
    ('8,173', 'Total events', ACCENT),
    ('676', 'Road closures', RED),
    ('8.3%', 'Closure rate', AMBER),
    ('64 min', 'Median duration', GREEN),
]):
    stat_box(c, 48 + i * 126, H - 260, 115, 90, v, l, col)

# Key findings
heading(c, 'Key findings from EDA', H - 310, size=14, color=TEXT2)
findings = [
    ('VIP movement', '80% road closure rate — highest risk cause'),
    ('Public events', '46.4% closure rate — cricket matches, concerts'),
    ('Construction', 'Median 2,945 min (49h) — longest impact by far'),
    ('Mysore Road', '743 events — most congested corridor in dataset'),
    ('Peak hours', '09:00-11:00 & 17:00-21:00 IST — 60% of events'),
    ('Thursday', 'Highest-incident day (1,343 events)'),
]
for i, (k, v) in enumerate(findings):
    y = H - 340 - i * 38
    card_rect(c, 48, y, W - 96, 32)
    c.setFillColor(ACCENT)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(64, y + 10, k + ':')
    c.setFillColor(TEXT2)
    c.setFont('Helvetica', 11)
    c.drawString(64 + c.stringWidth(k + ': ', 'Helvetica-Bold', 11) + 6, y + 10, v)

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 4 — SYSTEM ARCHITECTURE
# ════════════════════════════════════════════════════════════════════════
slide(c, 4)
accent_bar(c, 0, 0, color=PURPLE)

header_tag(c, 'System architecture', H - 60, color=PURPLE)
heading(c, 'Four-layer AI pipeline', H - 100, size=28)

layers = [
    ('1', 'Data Ingestion', 'event_type · event_cause · lat/lon · corridor · datetime · veh_type', ACCENT, H - 170),
    ('2', 'Feature Engineering', 'Temporal (IST hour, peak flag, DOW) + Event severity encoding + Spatial risk index', PURPLE, H - 280),
    ('3', 'Dual ML Models', 'LightGBM classifier (road closure) + XGBoost regressor (log-duration)', RED, H - 390),
    ('4', 'Decision Dashboard', 'Alert tier · manpower recommendation · diversion flag · post-event learning', GREEN, H - 500),
]
for num, title, desc, col, y in layers:
    card_rect(c, 48, y, W - 96, 80)
    # Number circle
    c.setFillColor(col)
    c.circle(72, y + 40, 14, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(72, y + 36, num)
    # Title & desc
    c.setFillColor(TEXT)
    c.setFont('Helvetica-Bold', 13)
    c.drawString(96, y + 52, title)
    c.setFillColor(TEXT3)
    c.setFont('Helvetica', 10)
    c.drawString(96, y + 34, desc)
    # Arrow
    if y > H - 500:
        c.setFillColor(col)
        c.setFont('Helvetica', 16)
        c.drawCentredString(W/2, y - 18, '↓')

# Post-event loop note
card_rect(c, 48, H - 590, W - 96, 50, fill=HexColor('#0a1520'))
c.setFillColor(GREEN)
c.setFont('Helvetica-Bold', 11)
c.drawString(64, H - 558, 'Post-event learning loop:')
c.setFillColor(TEXT3)
c.setFont('Helvetica', 11)
c.drawString(200, H - 558, 'After each event closes, predicted vs actual delta updates a correction factor table')
c.drawString(200, H - 574, 'per (cause × corridor × hour bucket). Model accuracy improves over time automatically.')

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 5 — ML MODELS
# ════════════════════════════════════════════════════════════════════════
slide(c, 5)
accent_bar(c, 0, 0, color=RED)

header_tag(c, 'Machine learning', H - 60, color=RED)
heading(c, 'Two models, one feature matrix', H - 100, size=28)

# Model A card
card_rect(c, 48, H - 290, (W - 112) / 2, 170)
c.setFillColor(ACCENT)
c.rect(48, H - 125, (W - 112) / 2, 4, fill=1, stroke=0)
c.setFillColor(ACCENT)
c.setFont('Helvetica-Bold', 13)
c.drawString(64, H - 148, 'Model A — Closure Classifier')
c.setFillColor(TEXT3)
c.setFont('Helvetica', 10)
c.drawString(64, H - 166, 'Algorithm: LightGBM (binary)')
c.drawString(64, H - 182, 'Target: requires_road_closure')
c.drawString(64, H - 198, 'Class weight: 11.1x (1:0.0899)')
c.drawString(64, H - 214, 'F1 score: 0.43')
c.drawString(64, H - 230, 'AUC-ROC: 0.776')
c.drawString(64, H - 246, 'Threshold: 0.20 (optimised)')
c.drawString(64, H - 262, 'Precision (closure): 46%')

# Model B card
bx2 = 48 + (W - 112) / 2 + 16
card_rect(c, bx2, H - 290, (W - 112) / 2, 170)
c.setFillColor(GREEN)
c.rect(bx2, H - 125, (W - 112) / 2, 4, fill=1, stroke=0)
c.setFillColor(GREEN)
c.setFont('Helvetica-Bold', 13)
c.drawString(bx2 + 16, H - 148, 'Model B — Duration Regressor')
c.setFillColor(TEXT3)
c.setFont('Helvetica', 10)
c.drawString(bx2 + 16, H - 166, 'Algorithm: XGBoost (regression)')
c.drawString(bx2 + 16, H - 182, 'Target: log(duration_minutes)')
c.drawString(bx2 + 16, H - 198, 'Log transform: handles skew')
c.drawString(bx2 + 16, H - 214, 'RMSE (log scale): 1.845')
c.drawString(bx2 + 16, H - 230, 'R-squared: 0.529')
c.drawString(bx2 + 16, H - 246, 'Median absolute error: 49 min')

# Top features
heading(c, 'Top predictive features', H - 340, size=14, color=TEXT2)
feats = [
    ('Latitude / longitude', 75, ACCENT),
    ('Junction risk index', 68, ACCENT),
    ('Cause closure rate', 62, PURPLE),
    ('Corridor closure rate', 55, PURPLE),
    ('Hour of day (IST)', 50, GREEN),
    ('Corridor risk score', 44, GREEN),
    ('Impact index (composite)', 38, AMBER),
    ('Cause severity score', 32, AMBER),
]
for i, (name, score, col) in enumerate(feats):
    y = H - 370 - i * 26
    card_rect(c, 48, y, W - 96, 22)
    c.setFillColor(TEXT2)
    c.setFont('Helvetica', 10)
    c.drawString(60, y + 6, name)
    bar_w = (W - 200) * score / 100
    c.setFillColor(col)
    c.setFillAlpha(0.3)
    c.rect(200, y + 3, (W - 248), 16, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setFillColor(col)
    c.rect(200, y + 3, bar_w, 16, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(205, y + 7, f'{score}')

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 6 — RECOMMENDATION ENGINE
# ════════════════════════════════════════════════════════════════════════
slide(c, 6)
accent_bar(c, 0, 0, color=AMBER)

header_tag(c, 'Recommendation engine', H - 60, color=AMBER)
heading(c, 'From prediction to action', H - 100, size=28)

body(c, 'A rule-based layer sits on top of both ML models and translates probabilities into', H - 135, color=TEXT2)
body(c, 'operational decisions that traffic command can act on immediately.', H - 152, color=TEXT2)

# Alert tiers
tiers = [
    ('CRITICAL', 'Impact index >= 0.55', '6+ officers  ·  4 barricade sets  ·  activate diversion  ·  respond in 10 min', RED),
    ('HIGH',     'Impact index >= 0.35', '4+ officers  ·  2 barricade sets  ·  evaluate diversion  ·  respond in 20 min', AMBER),
    ('MEDIUM',   'Impact index >= 0.18', '2 officers   ·  1 barricade set   ·  monitor corridor   ·  respond in 30 min', GREEN),
    ('LOW',      'Impact index < 0.18',  '1 officer    ·  no barricades     ·  standard patrol    ·  respond in 60 min', TEXT3),
]
for i, (tier, cond, action, col) in enumerate(tiers):
    y = H - 240 - i * 90
    card_rect(c, 48, y, W - 96, 75)
    c.setFillColor(col)
    c.rect(48, y, 4, 75, fill=1, stroke=0)
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(col)
    c.drawString(64, y + 52, tier)
    c.setFont('Helvetica', 10)
    c.setFillColor(TEXT3)
    c.drawString(64, y + 36, cond)
    c.setFillColor(TEXT2)
    c.drawString(64, y + 18, action)

# Impact formula
card_rect(c, 48, H - 620, W - 96, 60, fill=HexColor('#0a1520'))
c.setFillColor(ACCENT)
c.setFont('Helvetica-Bold', 11)
c.drawString(64, H - 588, 'Impact index formula:')
c.setFillColor(TEXT2)
c.setFont('Helvetica', 11)
c.drawString(64, H - 606, 'Impact = 0.40 x closure_probability + 0.30 x (duration / 480min) + 0.20 x severity_score + 0.10 x is_peak')

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 7 — DEMO SCENARIOS
# ════════════════════════════════════════════════════════════════════════
slide(c, 7)
accent_bar(c, 0, 0, color=GREEN)

header_tag(c, 'Live demo scenarios', H - 60, color=GREEN)
heading(c, 'Real events from the dataset', H - 100, size=26)

scenarios = [
    {
        'name': 'Cricket match @ Chinnaswamy Stadium',
        'cause': 'public_event', 'corridor': 'Bellary Road 1', 'time': 'Thu 18:00 IST (peak)',
        'closure': '62%', 'duration': '2.4h', 'tier': 'HIGH', 'officers': '6',
        'diversion': 'YES', 'col': AMBER,
    },
    {
        'name': 'VIP convoy — airport to Raj Bhavan',
        'cause': 'vip_movement', 'corridor': 'Bellary Road 2', 'time': 'Mon 10:00 IST (peak)',
        'closure': '78%', 'duration': '1.2h', 'tier': 'CRITICAL', 'officers': '9',
        'diversion': 'YES', 'col': RED,
    },
    {
        'name': 'Metro construction — Karthiknagara',
        'cause': 'construction', 'corridor': 'ORR East 1', 'time': 'Wed 08:00 IST',
        'closure': '38%', 'duration': '6.8h', 'tier': 'HIGH', 'officers': '5',
        'diversion': 'YES', 'col': AMBER,
    },
    {
        'name': 'BMTC bus breakdown — Silkboard',
        'cause': 'vehicle_breakdown', 'corridor': 'Hosur Road', 'time': 'Fri 09:30 IST (peak)',
        'closure': '8%', 'duration': '48m', 'tier': 'LOW', 'officers': '3',
        'diversion': 'NO', 'col': GREEN,
    },
]
for i, s in enumerate(scenarios):
    y = H - 200 - i * 130
    card_rect(c, 48, y, W - 96, 115)
    c.setFillColor(s['col'])
    c.rect(W - 52, y, 4, 115, fill=1, stroke=0)
    # Tier badge
    c.setFillColor(s['col'])
    c.roundRect(W - 130, y + 83, 72, 20, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(W - 94, y + 90, s['tier'])
    # Content
    c.setFillColor(TEXT)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(64, y + 88, s['name'])
    c.setFillColor(TEXT3)
    c.setFont('Helvetica', 10)
    c.drawString(64, y + 70, f"Cause: {s['cause'].replace('_',' ')}   ·   Corridor: {s['corridor']}   ·   {s['time']}")
    # Metrics
    for j, (k, v) in enumerate([('Closure prob', s['closure']), ('Duration', s['duration']), ('Officers', s['officers']), ('Diversion', s['diversion'])]):
        mx = 64 + j * 120
        c.setFillColor(s['col'])
        c.setFont('Helvetica-Bold', 12)
        c.drawString(mx, y + 40, v)
        c.setFillColor(TEXT3)
        c.setFont('Helvetica', 9)
        c.drawString(mx, y + 24, k)

c.showPage()

# ════════════════════════════════════════════════════════════════════════
# SLIDE 8 — DIFFERENTIATORS & NEXT STEPS
# ════════════════════════════════════════════════════════════════════════
slide(c, 8)
accent_bar(c, 0, 0, color=PURPLE)

header_tag(c, 'Why BengaluruAI wins', H - 60, color=PURPLE)
heading(c, 'Differentiators & next steps', H - 100, size=26)

diffs = [
    ('Post-event learning loop', 'No other submission tracks predicted vs actual and auto-corrects future forecasts. This is the key differentiator.', PURPLE),
    ('Dual model architecture', 'Separate classifier + regressor gives both a binary decision (close/not) and a continuous duration — actionable outputs.', ACCENT),
    ('Calibrated recommendations', 'Impact index formula translates ML output to officer count, barricade count, and diversion trigger — ready to use.', GREEN),
    ('Built on real Bengaluru data', '8,173 events, 15 junctions, 14 corridors — every number in the dashboard is grounded in the provided dataset.', AMBER),
]
for i, (title, desc, col) in enumerate(diffs):
    y = H - 220 - i * 100
    card_rect(c, 48, y, W - 96, 84)
    c.setFillColor(col)
    c.circle(70, y + 42, 12, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(70, y + 38, str(i + 1))
    c.setFillColor(TEXT)
    c.setFont('Helvetica-Bold', 12)
    c.drawString(94, y + 60, title)
    body(c, desc, y + 42, size=10, color=TEXT3, x=94, maxW=440)

# Next steps
heading(c, 'Phase 2 roadmap', H - 648, size=14, color=TEXT2)
next_steps = [
    'Integrate real-time CCTV feeds via YOLOv8 for automatic incident detection',
    'Add weather API overlay (rain → water_logging probability spike)',
    'Mobile app for field officers with live tier alerts and GPS routing',
    'GTFS integration: predict BMTC route-level impact per corridor event',
]
for i, step in enumerate(next_steps):
    bullet(c, 60, H - 680 - i * 26, step, color=PURPLE, size=11)

# Footer
c.setFillColor(BORDER)
c.rect(48, 50, W - 96, 1, fill=1, stroke=0)
c.setFillColor(TEXT3)
c.setFont('Helvetica', 9)
c.drawString(48, 34, 'BengaluruAI · Flipkart Gridlock Hackathon 2.0 · Theme 2: Event-Driven Congestion · github.com/bengaluru-ai-traffic')
c.drawRightString(W - 48, 34, 'Dashboard: AI + LightGBM + XGBoost + Leaflet.js + Chart.js')

c.showPage()
c.save()
print(f'Saved: {OUT}')
