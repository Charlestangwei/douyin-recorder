#!/usr/bin/env python3
"""抖音搜索-API拦截版：搜泰国/日本/越南/美国
   入选条件: 在线>=10000 或 累计人数>=100000  -> 写入rooms_pending.txt
   混合策略: 已收录主播再次达标时覆盖(取最高值)，不达标时跳过"""
import os, sys, json, time, re, random, base64, urllib.request, traceback as tb
from datetime import datetime
from urllib.parse import quote

GH_REPO = os.environ.get("GH_REPO", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
DOUYIN_COOKIE = os.environ.get("DOUYIN_COOKIE", "")

SEARCH_KEYWORDS = ["泰国", "日本", "越南", "美国"]
MIN_ONLINE = 10000
MIN_TOTAL = 100000
MAX_RUNTIME = 2 * 3600  # 2小时

# ───── constants ─────
HEADER = "# Pending rooms (high traffic, threshold>=10000 online or >=100000 cumulative)\n"

def log(msg):
    _tz = datetime.utcfromtimestamp(time.time() + 7*3600)
    print(f"[{_tz.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def parse_line(line):
    """解析 rooms_pending.txt 的一行，返回 dict 或 None"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = re.match(r'^(\d+)\s*=\s*([^|]+)\s*\|\s*online=(\d+)\s*\|\s*total_user=(\d+)', line)
    if m:
        return {
            'rid': m.group(1),
            'nickname': m.group(2).strip(),
            'online': int(m.group(3)),
            'total': int(m.group(4)),
            'raw': line,
        }
    return None


def build_line(rid, nickname, online, total, reason, keyword):
    return f"{rid} = {nickname} | online={online} | total_user={total} | {reason} | keyword={keyword}"


def get_pending_rooms():
    """读取 rooms_pending.txt，返回 (pending_map, sha, content)
       pending_map: {short_id: {nickname, online, total, raw}, ...}"""
    pending = {}
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GH_REPO}/contents/rooms_pending.txt",
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        c = base64.b64decode(data["content"]).decode("utf-8")
        sha = data.get("sha", "")
        lines = c.split("\n")
        for line in lines:
            p = parse_line(line)
            if p:
                pending[p['rid']] = p
        log(f"rooms_pending.txt: {len(pending)} 个待处理房间")
        return pending, sha, c
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log("rooms_pending.txt: 尚不存在，将新建")
            return {}, "", ""
        log(f"读取rooms_pending.txt失败: {e}")
        return {}, "", ""
    except Exception as e:
        log(f"读取rooms_pending.txt异常: {e}")
        return {}, "", ""


def write_pending(content, msg, current_sha):
    """写 rooms_pending.txt，重试一次 409
       FIX #1: 使用 resp['content']['sha']（文件SHA）而非 resp['commit']['sha']（提交SHA）
       FIX #2: 409重试时保留已构建的 content（不覆盖为 c2）"""
    b64 = base64.b64encode(content.encode("utf-8")).decode()
    d = {"message": msg, "content": b64, "sha": current_sha}
    if not current_sha:
        d.pop("sha")
    for _ in range(2):
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{GH_REPO}/contents/rooms_pending.txt",
                data=json.dumps(d).encode(),
                headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"},
                method="PUT")
            resp = json.loads(urllib.request.urlopen(req).read())
            # FIX: content.sha 是文件blob SHA，commit.sha 是提交SHA
            # update_or_add 把 SHA 传给下一次 PUT，必须用文件SHA
            file_sha = resp['content']['sha']
            return file_sha, content
        except urllib.error.HTTPError as e:
            if e.code == 409:
                log("  409冲突，重新读取后重试...")
                p2, sha2, c2 = get_pending_rooms()
                if sha2:
                    d["sha"] = sha2
                    # FIX: 保留 content（已含新增行），不覆盖为 c2
                    continue
                log("  409重试失败: 无法获取最新文件SHA")
                return current_sha, content
            log(f"  ✗ 写入失败: {e}")
            return current_sha, content
    log("  ✗ 重试2次均失败")
    return current_sha, content


def update_or_add(rid, nickname, online, total, reason, keyword,
                  pending_map, current_sha, current_content):
    """核心逻辑: already in pending → compare & update; new → append"""
    if rid in pending_map:
        existing = pending_map[rid]
        new_online = max(existing['online'], online)
        new_total = max(existing['total'], total)

        if new_online == existing['online'] and new_total == existing['total']:
            log(f"  {rid} {nickname}: 已在列表中，数据未变化(online={online},total={total})，跳过")
            return current_sha, current_content, False

        # 取最大在线 + 最大累计，用更高的理由
        new_reason_parts = []
        if new_online >= MIN_ONLINE:
            new_reason_parts.append(f"在线>={MIN_ONLINE}")
        if new_total >= MIN_TOTAL:
            new_reason_parts.append(f"累计>={MIN_TOTAL}")
        new_reason = "+".join(new_reason_parts)

        new_line = build_line(rid, nickname, new_online, new_total, new_reason, keyword)
        log(f"  ★ {rid}: 更新 {existing['online']}/{existing['total']} → {new_online}/{new_total} {new_reason}")

        # 替换该行
        lines = current_content.split("\n")
        new_lines = []
        updated = False
        for line in lines:
            p = parse_line(line)
            if p and p['rid'] == rid:
                new_lines.append(new_line)
                updated = True
            else:
                new_lines.append(line.rstrip())
        if not updated:
            new_lines.append(new_line)

        updated_content = "\n".join(new_lines) + ("\n" if not current_content.endswith("\n") else "")
        new_sha, new_content = write_pending(updated_content,
            f"searcher: 更新 {rid} {nickname} online={new_online} total={new_total}", current_sha)
        return new_sha, new_content, True
    else:
        # 新记录
        new_line = build_line(rid, nickname, online, total, reason, keyword)
        new_content = (current_content or HEADER) + new_line + "\n"
        new_sha, new_content = write_pending(new_content,
            f"searcher: 发现 {rid} = {nickname} (online={online}, total={total})", current_sha)
        log(f"  ✓ 新增: {new_line}")
        return new_sha, new_content, True


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


def search_keyword(page, keyword, pending_map):
    """搜索关键词，返回达标数据 [(sid, nick, uc, total, reason, is_new), ...]
       is_new=True → 尚未在pending中; is_new=False → 已存在但数据变高了"""
    search_url = f"https://www.douyin.com/search/{quote(keyword)}?type=live"
    log(f"搜索: {keyword}")
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
            if inp and not inp.get_attribute('disabled'):
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

    results = []  # [(sid, nick, uc, total, reason, is_new)]
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

            is_new = sid not in pending_map

            if is_new:
                # 全新房间 - 判断是否达标
                reasons = []
                if uc >= MIN_ONLINE:
                    reasons.append(f"在线>={MIN_ONLINE}")
                if total >= MIN_TOTAL:
                    reasons.append(f"累计>={MIN_TOTAL}")
                if reasons:
                    reason_str = "+".join(reasons)
                    results.append((sid, nick, uc, total, reason_str, True))
                    log(f"  ✓ {sid} {nick}: 在线={uc} 累计={total} -> {reason_str} (新增)")
                else:
                    log(f"  ✗ {sid} {nick}: 在线={uc} 累计={total} (未达标, 跳过)")
            else:
                # 已有房间 - 比较取最高值
                old = pending_map[sid]
                max_online = max(uc, old['online'])
                max_total = max(total, old['total'])
                updated = (max_online > old['online'] or max_total > old['total'])
                still_qualifies = (max_online >= MIN_ONLINE or max_total >= MIN_TOTAL)

                if updated and still_qualifies:
                    reasons = []
                    if max_online >= MIN_ONLINE:
                        reasons.append(f"在线>={MIN_ONLINE}")
                    if max_total >= MIN_TOTAL:
                        reasons.append(f"累计>={MIN_TOTAL}")
                    reason_str = "+".join(reasons)
                    results.append((sid, nick, max_online, max_total, reason_str, False))
                    log(f"  ★ {sid} {nick}: 在线={uc}(旧={old['online']}) 累计={total}(旧={old['total']}) -> 更新为{max_online}/{max_total}")
                elif not still_qualifies:
                    log(f"  ◇ {sid} {nick}: 在线={uc} 累计={total} (原记录已存在但不达标数据，跳过)")
                else:
                    log(f"  ◇ {sid} {nick}: 在线={uc} 累计={total} (数据未变高，跳过)")

    log(f"  关键词'{keyword}': 去重后{len(seen)}个房间, {len(results)}个需写入")
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
    total_new = 0
    total_updates = 0

    try:
        while time.time() - start_time < MAX_RUNTIME:
            round_num += 1
            log(f"\n{'='*60}")
            log(f"第{round_num}轮 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            log(f"条件: 在线>={MIN_ONLINE} 或 累计>={MIN_TOTAL}")
            log(f"运行{time.time()-start_time:.0f}s/{MAX_RUNTIME}s, 累计新发现{total_new}个, 更新{total_updates}次")
            log(f"{'='*60}")

            pending_map, pending_sha, pending_content = get_pending_rooms()

            round_new = 0
            round_upd = 0
            for i, keyword in enumerate(SEARCH_KEYWORDS):
                if time.time() - start_time >= MAX_RUNTIME:
                    break
                log(f"\n--- {keyword} ---")
                try:
                    results = search_keyword(page, keyword, pending_map)
                    for sid, nick, uc, total, reason, is_new in results:
                        new_sha, new_content, ok = update_or_add(
                            sid, nick, uc, total, reason, keyword,
                            pending_map, pending_sha, pending_content)
                        if ok:
                            pending_sha = new_sha
                            pending_content = new_content
                            if is_new:
                                pending_map[sid] = parse_line(build_line(sid, nick, uc, total, reason, keyword))
                                round_new += 1
                            else:
                                pending_map[sid] = parse_line(build_line(sid, nick, uc, total, reason, keyword))
                                round_upd += 1
                except Exception as e:
                    log(f"'{keyword}'异常: {e}")
                    tb.print_exc()

                if i < len(SEARCH_KEYWORDS) - 1 and time.time() - start_time < MAX_RUNTIME:
                    delay = random.randint(300, 360)
                    log(f"等待{delay}s后下一个关键词...")
                    time.sleep(delay)

            total_new += round_new
            total_updates += round_upd
            log(f"\n本轮: 新增{round_new}个, 更新{round_upd}个 (累计新增{total_new}, 更新{total_updates})")

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
    log(f"结束: 运行{total:.0f}s ({total/60:.0f}min), 新增{total_new}, 更新{total_updates}")

    # ── 自续命: 触发下一轮 ──
    log("自续命: 触发下一轮...")
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GH_REPO}/actions/workflows/searcher.yml/dispatches",
            data=json.dumps({"ref": "main"}).encode(),
            headers={
                "Authorization": f"Bearer {GH_TOKEN}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "self-renew",
            },
            method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        log(f"  自续命: HTTP {resp.status}")
    except Exception as e:
        log(f"  自续命失败: {e}")


if __name__ == "__main__":
    main()
