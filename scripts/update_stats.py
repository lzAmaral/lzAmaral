"""Render GitHub profile charts as SVGs using the GitHub GraphQL API."""
import json
import os
import sys
from collections import Counter
from datetime import date
from html import escape
from math import cos, sin, pi
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets' / 'stats'
QUERY = '''query($login:String!, $cursor:String) {
 user(login:$login) {
  repositories(ownerAffiliations:OWNER,privacy:PUBLIC,isFork:false,first:100,after:$cursor) {
   totalCount pageInfo {hasNextPage endCursor}
   nodes {name stargazerCount languages(first:100) {edges {size node {name color}}}}
  }
  followers {totalCount}
  contributionsCollection {
   totalCommitContributions totalPullRequestContributions totalIssueContributions
   contributionCalendar {totalContributions weeks {contributionDays {contributionCount date weekday}}}
  }
 }
}'''


def fetch():
    token = os.environ['GH_TOKEN']
    repos, cursor, user = [], None, None
    while True:
        body = json.dumps({'query': QUERY, 'variables': {'login': 'lzAmaral', 'cursor': cursor}}).encode()
        req = Request('https://api.github.com/graphql', data=body, headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
            'User-Agent': 'lzAmaral-profile-stats'})
        with urlopen(req, timeout=30) as response:
            data = json.load(response)
        if data.get('errors'):
            raise RuntimeError('GitHub GraphQL request failed: ' + str(data['errors']))
        user = data['data']['user']
        repos.extend(user['repositories']['nodes'])
        page = user['repositories']['pageInfo']
        if not page['hasNextPage']:
            break
        cursor = page['endCursor']
    user['repositories']['nodes'] = repos
    return user


def label(x, y, value, size=14, color='#94a3b8', weight=400, extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" {extra}>{escape(str(value))}</text>'


def card(width, height, title, description, content):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="16" fill="#0d1117" stroke="#30363d"/>
<g font-family="Arial, Helvetica, sans-serif">{content}</g></svg>'''


def render(user):
    OUT.mkdir(parents=True, exist_ok=True)
    collection = user['contributionsCollection']
    calendar = collection['contributionCalendar']
    weeks = calendar['weeks']
    repos = user['repositories']['nodes']
    values = [('Contribuições', calendar['totalContributions']),
              ('Commits', collection['totalCommitContributions']),
              ('Pull requests', collection['totalPullRequestContributions'])]
    content = label(26, 36, 'GitHub em números', 19, '#e6edf3', 700)
    content += label(26, 59, 'Atividade nos últimos 12 meses', 12)
    for index, (name, value) in enumerate(values):
        x = 26 + index * 154
        content += label(x, 110, f'{value:,}'.replace(',', '.'), 31, '#a78bfa', 700)
        content += label(x, 132, name, 12)
    stars = sum(repo['stargazerCount'] for repo in repos)
    content += '<path d="M26 153H474" stroke="#30363d"/>'
    content += label(26, 179, f'{len(repos)} repositórios públicos · {stars} estrelas · {user["followers"]["totalCount"]} seguidores', 12)
    content += label(26, 218, 'Contribuições por semana', 12, '#e6edf3')
    counts = [sum(day['contributionCount'] for day in week['contributionDays']) for week in weeks]
    maximum = max(max(counts), 1)
    points = [(26 + i * 448 / max(len(counts) - 1, 1), 278 - value / maximum * 48) for i, value in enumerate(counts)]
    line = ' '.join(f'{x:.1f},{y:.1f}' for x, y in points)
    content += '<path d="M26 278H474" stroke="#30363d"/>'
    content += f'<polygon points="26,278 {line} 474,278" fill="#a78bfa" opacity=".12"/>'
    content += f'<polyline points="{line}" fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linejoin="round"/>'
    content += label(26, 302, 'Há um ano', 11) + label(474, 302, 'Hoje', 11, extra='text-anchor="end"')
    (OUT / 'overview.svg').write_text(card(500, 320, 'Estatísticas de Luiz Amaral',
        'Contribuições, commits e pull requests nos últimos 12 meses; totais de repositórios públicos próprios, estrelas e seguidores. Gráfico semanal de contribuições.', content))

    totals, colors = Counter(), {}
    for repo in repos:
        for edge in repo['languages']['edges']:
            name = edge['node']['name']
            totals[name] += edge['size']
            colors[name] = edge['node']['color'] or '#94a3b8'
    ranked = totals.most_common(5)
    if len(totals) > 5:
        ranked.append(('Outras', sum(totals.values()) - sum(v for _, v in ranked)))
        colors['Outras'] = '#64748b'
    total = sum(totals.values()) or 1
    content = label(26, 36, 'Linguagens nos projetos', 19, '#e6edf3', 700)
    content += label(26, 59, 'Distribuição por volume de código', 12)
    circumference = 2 * pi * 72
    offset = 0
    for name, value in ranked:
        length = value / total * circumference
        content += f'<circle cx="126" cy="175" r="72" fill="none" stroke="{colors[name]}" stroke-width="24" stroke-dasharray="{length:.3f} {circumference-length:.3f}" stroke-dashoffset="{-offset:.3f}" transform="rotate(-90 126 175)"/>'
        offset += length
    content += label(126, 173, str(len(totals)), 30, '#e6edf3', 700, 'text-anchor="middle"')
    content += label(126, 195, 'linguagens', 12, extra='text-anchor="middle"')
    for i, (name, value) in enumerate(ranked):
        y = 109 + i * 29
        content += f'<circle cx="238" cy="{y-4}" r="4" fill="{colors[name]}"/>'
        content += label(251, y, name, 13, '#e6edf3')
        percent = f'{value/total*100:.1f}%'.replace('.', ',')
        content += label(474, y, percent, 13, extra='text-anchor="end"')
    content += label(26, 285, 'Repositórios públicos próprios; forks excluídos.', 11)
    content += label(26, 303, 'Percentuais de código, sem medir domínio ou experiência.', 10)
    (OUT / 'languages.svg').write_text(card(500, 320, 'Linguagens de programação',
        '; '.join(f'{name}: {value/total*100:.1f} por cento' for name,value in ranked) + '. Distribuição em bytes dos repositórios públicos próprios, excluindo forks.', content))

    content = label(26, 36, 'Um ano construindo', 19, '#e6edf3', 700)
    content += label(26, 59, f'{calendar["totalContributions"]:,} contribuições nos últimos 12 meses'.replace(',', '.'), 12)
    shades = ['#161b22', '#163b37', '#1a695b', '#26a98b', '#5eead4']
    peak = max((day['contributionCount'] for w in weeks for day in w['contributionDays']), default=1)
    last_month = None
    for wi, week in enumerate(weeks):
        x = 54 + wi * 17.5
        first = week['contributionDays'][0]
        month = date.fromisoformat(first['date']).month
        if month != last_month:
            names = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
            if wi != 0 or date.fromisoformat(first['date']).day <= 20:
                content += label(x, 86, names[month-1], 10)
            last_month = month
        for day in week['contributionDays']:
            count = day['contributionCount']
            level = 0 if count == 0 else min(4, max(1, int((count / max(peak, 1))**.5 * 4)))
            y = 99 + day['weekday'] * 17.5
            content += f'<rect x="{x}" y="{y}" width="13.5" height="13.5" rx="3" fill="{shades[level]}"><title>{day["date"]}: {count} contribuições</title></rect>'
    for day, name in [(1,'seg'),(3,'qua'),(5,'sex')]:
        content += label(26, 110 + day * 17.5, name, 10)
    content += label(26, 249, 'Fonte: GitHub · Atualização semanal', 11)
    content += label(850, 249, 'Menos', 10)
    for i, color in enumerate(shades):
        content += f'<rect x="{890+i*17}" y="239" width="12" height="12" rx="2" fill="{color}"/>'
    content += label(984, 249, 'Mais', 10)
    (OUT / 'activity.svg').write_text(card(1020, 272, 'Calendário de contribuições de Luiz Amaral',
        'Calendário diário dos últimos 12 meses. Cores mais claras indicam mais contribuições.', content))


if __name__ == '__main__':
    if len(sys.argv) == 2:
        user = json.loads(Path(sys.argv[1]).read_text())['data']['user']
    else:
        user = fetch()
    render(user)
    print('Updated overview.svg, languages.svg and activity.svg')
