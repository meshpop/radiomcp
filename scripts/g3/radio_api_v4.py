#!/usr/bin/env python3
"""Radio Unified API v4 - Korean search, CORS, full-text"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import sqlite3
import json
from datetime import datetime
from math import cos, radians, sin, acos

PORT = 8092

# Multilingual search keyword lookup
KEYWORD_LOOKUP = {'뉴스': 'news', 'ニュース': 'news', '新闻': 'news', 'nouvelles': 'news', 'nachrichten': 'news', 'noticias': 'news', 'notizie': 'news', 'новости': 'news', 'notícias': 'news', 'tin tức': 'news', 'ข่าว': 'news', 'berita': 'news', 'haberleri': 'news', '재즈': 'jazz', 'ジャズ': 'jazz', '爵士': 'jazz', 'джаз': 'jazz', '클래식': 'classical', 'クラシック': 'classical', '古典': 'classical', 'classique': 'classical', 'klassik': 'classical', 'clásica': 'classical', 'classica': 'classical', 'классика': 'classical', 'clássica': 'classical', '록': 'rock', 'ロック': 'rock', '摇滚': 'rock', 'рок': 'rock', '팝': 'pop', 'ポップ': 'pop', '流行': 'pop', 'поп': 'pop', '일렉트로닉': 'electronic', '電子': 'electronic', 'электронная': 'electronic', 'electronica': 'electronic', 'électronique': 'electronic', 'elektronisch': 'electronic', '힙합': 'hip hop', 'ヒップホップ': 'hip hop', '嘻哈': 'hip hop', 'хип-хоп': 'hip hop', '컨트리': 'country', 'カントリー': 'country', '乡村': 'country', '블루스': 'blues', 'ブルース': 'blues', '蓝调': 'blues', 'блюз': 'blues', '레게': 'reggae', 'レゲエ': 'reggae', '雷鬼': 'reggae', '메탈': 'metal', 'メタル': 'metal', '金属': 'metal', '포크': 'folk', 'フォーク': 'folk', '民謠': 'folk', 'фолк': 'folk', '소울': 'soul', 'ソウル': 'soul', '灵魂': 'soul', '댄스': 'dance', 'ダンス': 'dance', '舞曲': 'dance', 'танцевальная': 'dance', '앰비언트': 'ambient', 'アンビエント': 'ambient', '环境': 'ambient', '라운지': 'lounge', 'ラウンジ': 'lounge', '休闲': 'lounge', '칠아웃': 'chillout', 'チルアウト': 'chillout', '放松': 'chillout', '토크': 'talk', 'トーク': 'talk', '脱口秀': 'talk', 'разговорное': 'talk', '스포츠': 'sports', 'スポーツ': 'sports', '体育': 'sports', 'спорт': 'sports', 'deportes': 'sports', 'sport': 'sports', '올디스': 'oldies', 'オールディーズ': 'oldies', '老歌': 'oldies', 'ретро': 'oldies', '케이팝': 'kpop', '韩流': 'kpop', '제이팝': 'jpop', '日本流行': 'jpop', '라틴': 'latin', 'ラテン': 'latin', '拉丁': 'latin', '기독교': 'christian', 'クリスチャン': 'christian', '基督教': 'christian', 'христианская': 'christian', '명상': 'meditation', '瞑想': 'meditation', '冥想': 'meditation', 'медитация': 'meditation', '휴식': 'relaxing', 'リラックス': 'relaxing', '轻松': 'relaxing', 'расслабляющая': 'relaxing', '편안한': 'relaxing', '운동': 'workout', 'ワークアウト': 'workout', '健身': 'workout', 'тренировка': 'workout', '수면': 'sleep', '睡眠': 'sleep', 'сон': 'sleep', '공부': 'study', '勉強': 'study', '学习': 'study', 'учёба': 'study', '한국': 'korea', '韓国': 'korea', '韩国': 'korea', 'corée': 'korea', 'corea': 'korea', 'корея': 'korea', '일본': 'japan', '日本': 'japan', 'japon': 'japan', 'japón': 'japan', 'япония': 'japan', '중국': 'china', '中国': 'china', 'chine': 'china', 'китай': 'china', '미국': 'usa', 'アメリカ': 'usa', '美国': 'usa', 'états-unis': 'usa', 'estados unidos': 'usa', 'сша': 'usa', '영국': 'uk', 'イギリス': 'uk', '英国': 'uk', 'royaume-uni': 'uk', 'reino unido': 'uk', 'великобритания': 'uk', '프랑스': 'france', 'フランス': 'france', '法国': 'france', 'франция': 'france', '독일': 'germany', 'ドイツ': 'germany', '德国': 'germany', 'allemagne': 'germany', 'alemania': 'germany', 'германия': 'germany', '스페인': 'spain', 'スペイン': 'spain', '西班牙': 'spain', 'espagne': 'spain', 'españa': 'spain', 'испания': 'spain', '이탈리아': 'italy', 'イタリア': 'italy', '意大利': 'italy', 'italie': 'italy', 'italia': 'italy', 'италия': 'italy', '러시아': 'russia', 'ロシア': 'russia', '俄罗斯': 'russia', 'russie': 'russia', 'rusia': 'russia', 'россия': 'russia', '브라질': 'brazil', 'ブラジル': 'brazil', '巴西': 'brazil', 'brésil': 'brazil', 'brasil': 'brazil', 'бразилия': 'brazil'}

def translate_search_query(query):
    """Translate multilingual search terms to English"""
    words = query.lower().split()
    translated = []
    for word in words:
        if word in KEYWORD_LOOKUP:
            translated.append(KEYWORD_LOOKUP[word])
        else:
            translated.append(word)
    return ' '.join(translated)


DB = '/opt/radiomcp/data/radio_unified.db'
# Common country name aliases
from korean_resolvers import resolve_url, KOREAN_STATIONS

def refresh_resolver_url(row):
    """Refresh URL for resolver-based stations"""
    resolver = row.get('resolver')
    station_id = row.get('id')
    if resolver and station_id:
        fresh_url = resolve_url(resolver, station_id)
        if fresh_url:
            row['url'] = fresh_url
            row['url_resolved'] = fresh_url
    return row

COUNTRY_ALIASES = {
    'usa': 'United States',
    'uk': 'United Kingdom',
    'england': 'United Kingdom',
    'britain': 'United Kingdom',
    'great britain': 'United Kingdom',
    'korea': 'South Korea',
    'south korea': 'South Korea',
    'north korea': 'North Korea',
    'russia': 'Russian Federation',
    'taiwan': 'Taiwan',
    'czech': 'Czech Republic',
    'holland': 'Netherlands',
    'uae': 'United Arab Emirates',
}


def calc_health(row):
    score = 0
    if row.get('is_verified'): score += 40
    bytes_recv = row.get('bytes_received')
    if bytes_recv and bytes_recv > 4000: score += 20
    br = row.get('bitrate') or 0
    if br >= 128: score += 20
    elif br >= 64: score += 10
    listeners = row.get('listeners')
    if listeners and listeners > 0: score += 10
    votes = row.get('votes')
    if votes and votes > 0: score += 10
    grade = 'A' if score >= 80 else 'B' if score >= 60 else 'C' if score >= 40 else 'D'
    row['health_score'] = score
    row['health_grade'] = grade
    row['stream_verified'] = bool(row.get('is_verified'))
    return row

class RadioAPI(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): print(fmt % args)
    
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    


    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        
        # Get client IP
        client_ip = self.headers.get('X-Forwarded-For', self.client_address[0])
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        try:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            
            # /stations/{id}/click - 클릭 기록
            if '/click' in path:
                parts = path.split('/')
                # /stations/123/click
                station_id = None
                for i, p in enumerate(parts):
                    if p == 'stations' and i+1 < len(parts):
                        try:
                            station_id = parts[i+1]
                        except:
                            pass
                        break
                
                if not station_id:
                    self.send_json({'error': 'station_id required'}, 400)
                    conn.close()
                    return
                
                # Check station exists
                c.execute('SELECT id, name FROM stations WHERE id = ?', (station_id,))
                row = c.fetchone()
                if not row:
                    self.send_json({'error': 'station not found'}, 404)
                    conn.close()
                    return
                
                # Record click
                c.execute('INSERT INTO clicks (station_id, ip) VALUES (?, ?)', 
                         (station_id, client_ip))
                
                # Update recent_clicks count (last 24h)
                c.execute("""
                    UPDATE stations SET recent_clicks = (
                        SELECT COUNT(*) FROM clicks 
                        WHERE station_id = ? 
                        AND clicked_at > datetime('now', '-24 hours')
                    ) WHERE id = ?
                """, (station_id, station_id))
                
                conn.commit()
                self.send_json({
                    'ok': True, 
                    'station_id': station_id,
                    'station_name': row[1]
                })
            else:
                self.send_json({'error': 'Not found'}, 404)
            
            conn.close()
        except Exception as e:
            self.send_json({'error': str(e)}, 500)


    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        qs = parse_qs(parsed.query)
        params = {k: unquote(v[0]) if v else '' for k, v in qs.items()}
        
        try:
            conn = sqlite3.connect(DB)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            limit = min(int(params.get('limit', 30)), 500)
            offset = int(params.get('offset', 0))
            order = params.get('order', 'listeners')
            order_map = {'listeners': 'listeners DESC', 'votes': 'votes DESC', 
                        'bitrate': 'bitrate DESC', 'name': 'name ASC', 'random': 'RANDOM()'}
            order_sql = order_map.get(order, 'listeners DESC')
            
            # /search?q= (full-text)
            if path == '/search':
                q = translate_search_query(params.get('q', '').strip())
                if not q:
                    self.send_json({'error': 'q parameter required'}, 400)
                    conn.close()
                    return
                like = '%' + q + '%'

                # Build WHERE clause with optional filters
                where = '(name LIKE ? OR tags LIKE ? OR country LIKE ? OR language LIKE ?)'
                args = [like, like, like, like]

                # Optional countrycode filter
                if params.get('countrycode'):
                    where += ' AND countrycode = ?'
                    args.append(params['countrycode'].upper())

                # Optional tag filter
                if params.get('tag'):
                    where += ' AND tags LIKE ?'
                    args.append('%' + params['tag'] + '%')

                sql = f'SELECT * FROM stations WHERE {where} ORDER BY (CASE WHEN name LIKE ? THEN 2 ELSE 1 END) DESC, ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, args + [q + ' %', limit, offset])
                rows = [refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()]
                c.execute(f'SELECT COUNT(*) FROM stations WHERE {where}', args)
                total = c.fetchone()[0]
                self.send_json({'total': total, 'limit': limit, 'offset': offset, 'data': rows})
            

            # /health
            elif path == "/health":
                c.execute("SELECT COUNT(*) FROM stations")
                total = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM stations WHERE is_verified = 1")
                verified = c.fetchone()[0]
                self.send_json({
                    "status": "ok",
                    "stations": total,
                    "verified": verified,
                    "timestamp": datetime.now().isoformat()
                })
            
            # /station/{id}
            elif path.startswith("/station/") and not path.startswith("/stations"):
                station_id = path.split("/")[-1]
                c.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
                row = c.fetchone()
                if row:
                    self.send_json(refresh_resolver_url(calc_health(dict(row))))
                else:
                    self.send_json({"error": "Station not found"}, 404)

            # /stations (with filters)
            elif path in ['/stations', '/json/stations', '/stations/search', '/json/stations/search']:
                where_parts = ['1=1']
                args = []
                if params.get('name'):
                    where_parts.append('name LIKE ?')
                    args.append('%' + params['name'] + '%')
                if params.get('tag'):
                    where_parts.append('tags LIKE ?')
                    args.append('%' + params['tag'] + '%')
                if params.get('country'):
                    where_parts.append('country LIKE ?')
                    args.append('%' + params['country'] + '%')
                if params.get('countrycode'):
                    where_parts.append('countrycode = ?')
                    args.append(params['countrycode'].upper())
                if params.get('language'):
                    where_parts.append('language LIKE ?')
                    args.append('%' + params['language'] + '%')
                if params.get('codec'):
                    where_parts.append('codec LIKE ?')
                    args.append('%' + params['codec'] + '%')
                if params.get('bitrateMin'):
                    where_parts.append('bitrate >= ?')
                    args.append(int(params['bitrateMin']))
                if params.get('bitrateMax'):
                    where_parts.append('bitrate <= ?')
                    args.append(int(params['bitrateMax']))
                if params.get('hidebroken', 'true') == 'true':
                    where_parts.append('is_verified = 1')
                
                where_sql = ' AND '.join(where_parts)
                sql = 'SELECT * FROM stations WHERE ' + where_sql + ' ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, args + [limit, offset])
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/bylanguage/{lang}
            elif path.startswith('/stations/bylanguage/'):
                lang = unquote(path.split('/')[-1])
                sql = 'SELECT * FROM stations WHERE language LIKE ? ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, ('%' + lang + '%', limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/byname/{n}
            elif path.startswith('/stations/byname/'):
                name = unquote(path.split('/')[-1])
                sql = 'SELECT * FROM stations WHERE name LIKE ? ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, ('%' + name + '%', limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/bycountry/{c}
            elif path.startswith('/stations/bycountry/'):
                country = unquote(path.split('/')[-1])
                country = COUNTRY_ALIASES.get(country.lower(), country)
                sql = 'SELECT * FROM stations WHERE country LIKE ? ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, ('%' + country + '%', limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/bycountrycode/{cc}
            elif path.startswith('/stations/bycountrycode/'):
                cc = path.split('/')[-1].upper()
                sql = 'SELECT * FROM stations WHERE countrycode = ? ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, (cc, limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/bytag/{t}
            elif path.startswith('/stations/bytag/'):
                tag = unquote(path.split('/')[-1])
                sql = 'SELECT * FROM stations WHERE tags LIKE ? ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, ('%' + tag + '%', limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/bycodec/{c}
            elif path.startswith('/stations/bycodec/'):
                codec = path.split('/')[-1]
                sql = 'SELECT * FROM stations WHERE codec LIKE ? ORDER BY ' + order_sql + ' LIMIT ? OFFSET ?'
                c.execute(sql, ('%' + codec + '%', limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/random
            elif path in ['/stations/random', '/json/stations/random']:
                c.execute('SELECT * FROM stations WHERE is_verified=1 ORDER BY RANDOM() LIMIT ?', (limit,))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/toplisteners
            elif path in ['/stations/toplisteners', '/json/stations/topvote', '/stations/topvote']:
                c.execute('SELECT * FROM stations ORDER BY listeners DESC LIMIT ? OFFSET ?', (limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /stations/recent
            elif path in ['/stations/recent', '/json/stations/lastchange']:
                c.execute('SELECT * FROM stations ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset))
                self.send_json([refresh_resolver_url(calc_health(dict(r))) for r in c.fetchall()])
            
            # /languages
            elif path in ['/languages', '/json/languages']:
                c.execute("SELECT language as name, COUNT(*) as stationcount FROM stations WHERE language IS NOT NULL AND language != '' GROUP BY language ORDER BY stationcount DESC")
                self.send_json([dict(r) for r in c.fetchall()])
            
            # /countries
            elif path in ['/countries', '/json/countries']:
                c.execute('SELECT country as name, countrycode, COUNT(*) as stationcount FROM stations WHERE country IS NOT NULL GROUP BY country ORDER BY stationcount DESC')
                self.send_json([dict(r) for r in c.fetchall()])
            
            # /tags
            elif path in ['/tags', '/json/tags']:
                c.execute('SELECT tags FROM stations WHERE tags IS NOT NULL')
                tag_count = {}
                for row in c.fetchall():
                    for t in (row[0] or '').split(','):
                        t = t.strip().lower()
                        if t: tag_count[t] = tag_count.get(t, 0) + 1
                tags = sorted([{'name': k, 'stationcount': v} for k,v in tag_count.items()], key=lambda x: -x['stationcount'])[:200]
                self.send_json(tags)
            
            # /codecs
            elif path in ['/codecs', '/json/codecs']:
                c.execute('SELECT codec as name, COUNT(*) as stationcount FROM stations WHERE codec IS NOT NULL GROUP BY codec ORDER BY stationcount DESC')
                self.send_json([dict(r) for r in c.fetchall()])
            
            # /stats
            elif path in ['/stats', '/json/stats']:
                c.execute('SELECT COUNT(*) FROM stations')
                total = c.fetchone()[0]
                c.execute('SELECT source, COUNT(*) FROM stations GROUP BY source')
                by_src = dict(c.fetchall())
                c.execute('SELECT COUNT(*) FROM stations WHERE is_verified=1')
                verified = c.fetchone()[0]
                c.execute('SELECT COUNT(*) FROM stations WHERE bitrate>=128')
                hq = c.fetchone()[0]
                c.execute('SELECT COUNT(DISTINCT countrycode) FROM stations')
                countries = c.fetchone()[0]
                c.execute("SELECT COUNT(DISTINCT language) FROM stations WHERE language IS NOT NULL AND language != ''")
                languages = c.fetchone()[0]
                c.execute('SELECT SUM(listeners) FROM stations')
                listeners = c.fetchone()[0] or 0
                self.send_json({
                    'stations': total, 'stations_verified': verified,
                    'stations_highquality': hq, 'sources': by_src,
                    'countries': countries, 'languages': languages,
                    'total_listeners': listeners,
                    'last_update': datetime.now().isoformat()
                })
            
            # / (API info) - serve HTML homepage
            elif path in ['', '/', '/json']:
                try:
                    with open('/opt/radiomcp/data/radio_api_home.html', 'rb') as f:
                        html = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(html)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(html)
                except:
                    self.send_json({
                        'name': 'Radio Unified API',
                        'version': '4.0',
                        'description': '55,000+ verified radio stations from 4 sources'
                    })
            


            # /stations/trending - clicktrend 기반 인기 상승 방송
            elif path in ['/stations/trending', '/json/stations/trending']:
                sql = """SELECT * FROM stations 
                         WHERE is_verified = 1
                         ORDER BY (COALESCE(recent_clicks, 0) * 100 + COALESCE(clickcount, 0) / 10) DESC 
                         LIMIT ? OFFSET ?"""
                c.execute(sql, (limit, offset))
                rows = []
                for r in c.fetchall():
                    row = refresh_resolver_url(calc_health(dict(r)))
                    row['trend_score'] = row.get('clicktrend', 0)
                    rows.append(row)
                self.send_json(rows)

            # /stations/nearby?lat=&lon=&radius=
            elif path in ['/stations/nearby', '/json/stations/nearby']:
                try:
                    lat = float(params.get('lat', 0))
                    lon = float(params.get('lon', 0))
                    radius = float(params.get('radius', 200))
                except:
                    self.send_json({'error': 'lat and lon required'}, 400)
                    conn.close()
                    return
                
                lat_range = radius / 111.0
                lon_range = radius / (111.0 * max(0.1, abs(cos(radians(lat)))))
                
                sql = """
                    SELECT *, 
                        (6371 * acos(min(1.0,
                            cos(radians(?)) * cos(radians(geo_lat)) * 
                            cos(radians(geo_long) - radians(?)) + 
                            sin(radians(?)) * sin(radians(geo_lat))
                        ))) as distance
                    FROM stations 
                    WHERE geo_lat IS NOT NULL 
                        AND geo_lat BETWEEN ? AND ?
                        AND geo_long BETWEEN ? AND ?
                    ORDER BY distance
                    LIMIT ?
                """
                
                c.execute(sql, (lat, lon, lat, 
                               lat - lat_range, lat + lat_range,
                               lon - lon_range, lon + lon_range, 
                               limit))
                rows = []
                for r in c.fetchall():
                    row = dict(r)
                    dist = row.pop('distance', 0)
                    row['distance_km'] = round(dist, 1) if dist else 0
                    rows.append(calc_health(row))
                self.send_json(rows)

            else:
                self.send_json({'error': 'Not found'}, 404)
            
            conn.close()
        except Exception as e:
            self.send_json({'error': str(e)}, 500)

if __name__ == '__main__':
    print('Radio Unified API v4 on port', PORT)
    HTTPServer(('0.0.0.0', PORT), RadioAPI).serve_forever()
