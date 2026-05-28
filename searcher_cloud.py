#!/usr/bin/env python3
"""抖音搜索-API拦截版：搜泰国/日本/越南/美国
   入选条件: 在线>=10000 或 累计人数>=100000  -> 写入rooms_pending.txt"""
import os, sys, json, time, re, random, base64, urllib.request, traceback as tb
from datetime import datetime
from urllib.parse import quote

GH_REPO = os.environ.get("GH_REPO", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
DOUYIN_COOKIE = os.environ.get("DOUYIN_COOKIE", "")

# 4个关键词，统一条件
SEARCH_KEYWORDS = ["泰国", "日本", "越南", "美国"]
MIN_ONLINE = 10000
MIN_TOTAL = 100000

MAX_RUNTIME = 5 * 3600

def log(msg):
    _tz_utc7 = datetime.utcfromtimestamp(time.time() + 7*3600)
    print(f"[{_tz_utc7.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def get_pending_rooms():
    """读取rooms_pending.txt，返回set(room_id)和内容"""
    existing = set()
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GH_REPO}/contents/rooms_pending.txt",
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        c = base64.b64decode(data["content"]).decode("utf-8")
        for line in c.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rid = line.split("=", 1)[0].strip()
            if rid.isdigit():
                existing.add(rid)
        existing_sha = data.get("sha", "")
        log(f"rooms_pending.txt: {len(existing)} 个待处理房间")
        return existing, existing_sha, c
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log("rooms_pending.txt: 尚不存在，将新建")
            return set(), "", ""
        log(f"读取rooms_pending.txt失败: {e}")
        return set(), "", ""
    except Exception as e:
        log(f"读取rooms_pending.txt异常: {e}")
        return set(), "", ""


def append_pending_room(rid, nickname, online, total, match_reason, keyword, current_content, current_sha):
    """向rooms_pending.txt添加一条记录"""
    line = f"{rid} = {nickname} | online={online} | total_user={total} | {match_reason} | keyword={keyword}"
    if current_content and rid in current_content:
        log(f"  {rid}: 已在rooms_pending.txt中，跳过")
        return current_content, current_sha, False

    new_content = (current_content or "") + line + "\n"
    b64 = base64.b64encode(new_content.encode("utf-8")).decode()

    for attempt in range(2):
        try:
            msg_data = json.dumps({
                "message": f"searcher: 发现 {rid} = {nickname} (online={online}, total={total})",
                "content": b64,
                "sha": current_sha
            }).encode()
            if not current_sha:
                msg_data = json.dumps({
                    "message": f"searcher: 发现 {rid} = {nickname} (online={online}, total={total})",
                    "content": b64
                }).encode()

            req = urllib.request.Request(
                f"https://api.github.com/repos/{GH_REPO}/contents/rooms_pending.txt",
                data=msg_data,
                headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"},
                method="PUT")
            resp = json.loads(urllib.request.urlopen(req).read())
            current_sha = resp['commit']['sha']
            current_content = new_content
            log(f"  ✓ 已追加: {line}")
            return current_content, current_sha, True
        except urllib.error.HTTPError as e:
            if e.code == 409 and attempt == 0:
                log(f"  409冲突，重新读取后重试...")
                try:
                    req2 = urllib.request.Request(
                        f"https://api.github.com/repos/{GH_REPO}/contents/rooms_pending.txt",
                        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
                    data2 = json.loads(urllib.request.urlopen(req2, timeout=30).read())
                    current_sha = data2["sha"]
                    c2 = base64.b64decode(data2["content"]).decode("utf-8")
                    if rid in c2:
                        log(f"  {rid}: 其他进程已添加，跳过")
                        return current_content, current_sha, False
                    new_content = c2 + line + "\n"
                    b64 = base64.b64encode(new_content.encode("utf-8")).decode()
                    current_content = new_content
                except:
                    log(f"  重试读取失败")
                    return current_content, current_sha, False
            else:
                log(f"  ✗ 写入失败: {e}")
                return current_content, current_sha, False
        except Exception as e:
            log(f"  ✗ 写入失败: {e}")
            return current_content, current_sha, False
    return current_content, current_sha, False


_api_buffer = []

def _on_api_response(response):
    url = response.url
    if '/aweme/v1/web/live/search/' not in url:
        return
    try:
        data = response.json()
        if data.get('status_code') == 0 and 'data' in data:
            _api_buffer.append(data)
    except:
        pass


def search_keyword(page, keyword, pending_ids):
    """搜索一个关键词，返回满足条件的rooms"""
    search_url = f"https://www.douyin.com/search/{quote(keyword)}?type=live"
    log(f"搜索: {keyword}")
    log(f"URL: {search_url}")

    _api_buffer.clear()

    try:
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
    except:
        pass
    page.wait_for_timeout(12000)

    if not _api_buffer:
        log("  API未返回，按Enter触发...")
        try:
            inp = page.query_selector('input')
            if inp:
                inp.focus()
                page.keyboard.press('Enter')
                page.wait_for_timeout(10000)
        except:
            pass

    if not _api_buffer:
        log("  API仍未返回，reload...")
        try:
            page.reload(wait_until='domcontentloaded')
            page.wait_for_timeout(12000)
        except:
            pass

    log(f"  捕获API响应: {len(_api_buffer)}次")

    results = []  # [(sid, nick, uc, total, reason), ...]
    seen = set()
    for data in _api_buffer:
        for item in data.get('data', []):
            if 'lives' not in item:
                continue
            a = item['lives'].get('author', {})
            sid = a.get('short_id', '')
            if not sid or not sid.isdigit():
                continue
            if sid in seen:
                continue
            seen.add(sid)

            nick = a.get('nickname', '').strip()
            raw = item['lives'].get('rawdata', '{}')
            uc = 0
            total = 0
            try:
                rd = json.loads(raw) if isinstance(raw, str) else raw
                uc = int(rd.get('user_count', 0))
                total = int(rd.get('stats', {}).get('total_user', 0))
            except:
                pass

            if sid in pending_ids:
                log(f"  {sid} {nick}: 在线={uc} 累计={total} (已在待处理列表，跳过)")
                continue

            reasons = []
            if uc >= MIN_ONLINE:
                reasons.append(f"在线>={MIN_ONLINE}")
            if total >= MIN_TOTAL:
                reasons.append(f"累计>={MIN_TOTAL}")

            if reasons:
                reason_str = "+".join(reasons)
                results.append((sid, nick or sid, uc, total, reason_str))
                log(f"  ✓ {sid} {nick}: 在线={uc} 累计={total} -> {reason_str}")
            else:
                log(f"  ✗ {sid} {nick}: 在线={uc} 累计={total} (不达标)")

    log(f"  关键词'{keyword}': 去重后{len(seen)}个房间, {len(results)}个达标")
    return results


def main():
    if not DOUYIN_COOKIE:
        log("缺少DOUYIN_COOKIE，终止")
        return
    if not GH_REPO or not GH_TOKEN:
        log("缺少GH_REPO或GH_TOKEN，终止")
        return

    try:
        cookie_dict = json.loads(base64.b64decode(DOUYIN_COOKIE).decode("utf-8"))
        log(f"Cookies: {len(cookie_dict)}个")
    except Exception as e:
        log(f"Cookie解析失败: {e}")
        return

    log("启动Playwright headless浏览器...")
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
    )
    context.add_cookies(cookie_dict)
    page = context.new_page()
    page.on('response', _on_api_response)

    log("预热: 访问douyin.com...")
    try:
        page.goto('https://www.douyin.com/', wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)
    except:
        pass

    start_time = time.time()
    round_num = 0
    all_time_new = 0

    cond_str = f"在线>={MIN_ONLINE}或累计>={MIN_TOTAL}"

    try:
        while time.time() - start_time < MAX_RUNTIME:
            round_num += 1
            log(f"\n{'='*60}")
            log(f"第{round_num}轮 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            log(f"条件: {cond_str}")
            log(f"运行{time.time()-start_time:.0f}s/{MAX_RUNTIME}s, 已发现{all_time_new}个")
            log(f"{'='*60}")

            pending_ids, pending_sha, pending_content = get_pending_rooms()

            round_new = 0
            for i, keyword in enumerate(SEARCH_KEYWORDS):
                if time.time() - start_time >= MAX_RUNTIME:
                    break

                log(f"\n--- {keyword} ---")
                try:
                    results = search_keyword(page, keyword, pending_ids)
                    for sid, nick, uc, total, reason in results:
                        pending_content, pending_sha, ok = append_pending_room(
                            sid, nick, uc, total, reason, keyword,
                            pending_content, pending_sha)
                        if ok:
                            pending_ids.add(sid)
                            round_new += 1
                except Exception as e:
                    log(f"'{keyword}'异常: {e}")
                    tb.print_exc()

                if i < len(SEARCH_KEYWORDS) - 1 and time.time() - start_time < MAX_RUNTIME:
                    delay = random.randint(30, 60)
                    log(f"等待{delay}s后下一个关键词...")
                    time.sleep(delay)

            all_time_new += round_new
            log(f"\n本轮新增{round_new}个 (累计{all_time_new})")

            remaining = MAX_RUNTIME - (time.time() - start_time)
            if remaining > 30:
                wait = min(60, remaining)
                log(f"等待{wait:.0f}s后第{round_num+1}轮...")
                time.sleep(wait)

    except Exception as e:
        log(f"异常终止: {e}")
        tb.print_exc()
    finally:
        browser.close()
        pw.stop()

    total = time.time() - start_time
    log(f"结束: 运行{total:.0f}s ({total/60:.0f}min), 共发现{all_time_new}个达标房间")

if __name__ == "__main__":
    main()
