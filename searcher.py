#!/usr/bin/env python3
"""抖音自动搜索 - Playwright 24h 常驻版（浏览器常开，增量滚动检查，单条写入）"""
import os, sys, json, time, re, random, base64, urllib.request, traceback as tb
from datetime import datetime
from urllib.parse import quote
GH_REPO = os.environ.get("GH_REPO", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
DOUYIN_COOKIE = os.environ.get("DOUYIN_COOKIE", "")

SEARCH_KEYWORDS = [
    ("泰国", 3000),
    ("美国", 3000),
]

MAX_RUNTIME = 5 * 3600          # 5 小时
RENEW_AT = MAX_RUNTIME - 1800   # 4.5h 触发续命
SEARCH_INTERVAL = 0               # 轮间隔已取消（关键词间已有 2-3 分钟等待）
TOP_N = 10                       # 每关键词只看前 10

def log(msg):
    _tz_utc7 = datetime.utcfromtimestamp(time.time() + 7*3600)
    print(f"[{_tz_utc7.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def get_rooms():
    """读取所有 3 个 rooms_{0,1,2}.txt，返回统一房间集合"""
    all_contents = {}
    all_rooms = {}
    all_shas = {}
    for idx in range(3):
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{GH_REPO}/contents/rooms_{idx}.txt",
                headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
            data = json.loads(urllib.request.urlopen(req, timeout=30).read())
            c = base64.b64decode(data["content"]).decode("utf-8")
            rooms = {}
            for line in c.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                rid = parts[0].strip() if len(parts) == 2 else line.split()[0].strip()
                if rid.isdigit():
                    rooms[rid] = line
            all_contents[idx] = c
            all_rooms.update(rooms)
            all_shas[idx] = data["sha"]
            log(f"  rooms_{idx}.txt: {len(rooms)} 个房间")
        except Exception as e:
            log(f"  读取 rooms_{idx}.txt 失败: {e}")
            all_contents[idx] = ""
            all_shas[idx] = ""
    log(f"总计: {len(all_rooms)} 个房间")
    return all_contents, all_rooms, all_shas

def update_rooms_add_one(all_contents, rid, nickname, all_shas):
    """将新房号写入房间最少的那组 rooms_{idx}.txt（409 冲突时重试一次）"""
    line = f"{rid} = {nickname}"
    # 检查 3 个文件是否已存在该房间
    for idx in range(3):
        if rid in all_contents.get(idx, ""):
            log(f"  {rid}: 已在 rooms_{idx}.txt 中, 跳过")
            return all_contents, all_shas, False
    # 选房间最少的组
    counts = {idx: all_contents.get(idx, "").count("\n") for idx in range(3)}
    # But filter to only count lines that have room IDs
    for idx in range(3):
        cnt = 0
        for line2 in all_contents.get(idx, "").split("\n"):
            lt = line2.strip()
            if lt and not lt.startswith("#") and lt.split("=", 1)[0].strip().isdigit():
                cnt += 1
        counts[idx] = cnt
    min_val = min(counts.values())
    tied = [k for k, v in counts.items() if v == min_val]
    target = random.choice(tied) if len(tied) > 1 else tied[0]
    log(f"  选组: rooms_{target}.txt ({counts[target]} 个房间, 其他组 {counts[(target+1)%3]}/{counts[(target+2)%3]})")
    
    c = all_contents.get(target, "")
    if c and not c.endswith("\n"):
        c += "\n"
    c = line + "\n" + c
    
    b64 = base64.b64encode(c.encode("utf-8")).decode()
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{GH_REPO}/contents/rooms_{target}.txt",
            data=json.dumps({"message": f"searcher: 新增 {rid} = {nickname}",
                "content": b64, "sha": all_shas.get(target, "")}).encode(),
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"},
            method="PUT")
        resp = json.loads(urllib.request.urlopen(req).read())
        new_sha = resp['commit']['sha']
        all_contents[target] = c
        all_shas[target] = new_sha
        log(f"  ✓ rooms_{target}.txt 已更新: 新增 {rid} = {nickname}")
        return all_contents, all_shas, True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            log(f"  409 冲突: 重新读取 rooms_{target}.txt 并重试...")
            try:
                req2 = urllib.request.Request(
                    f"https://api.github.com/repos/{GH_REPO}/contents/rooms_{target}.txt",
                    headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
                data2 = json.loads(urllib.request.urlopen(req2, timeout=30).read())
                fresh_c = base64.b64decode(data2["content"]).decode("utf-8")
                fresh_sha = data2["sha"]
                if rid in fresh_c:
                    log(f"  {rid}: 其他进程已添加, 跳过")
                    all_contents[target] = fresh_c
                    all_shas[target] = fresh_sha
                    return all_contents, all_shas, False
                if fresh_c and not fresh_c.endswith("\n"):
                    fresh_c += "\n"
                fresh_c = line + "\n" + fresh_c
                b64_retry = base64.b64encode(fresh_c.encode("utf-8")).decode()
                retry_req = urllib.request.Request(
                    f"https://api.github.com/repos/{GH_REPO}/contents/rooms_{target}.txt",
                    data=json.dumps({"message": f"searcher: 新增 {rid} = {nickname} (重试)",
                        "content": b64_retry, "sha": fresh_sha}).encode(),
                    headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"},
                    method="PUT")
                retry_resp = json.loads(urllib.request.urlopen(retry_req).read())
                new_sha2 = retry_resp['commit']['sha']
                all_contents[target] = fresh_c
                all_shas[target] = new_sha2
                log(f"  ✓ rooms_{target}.txt 重试成功: 新增 {rid} = {nickname}")
                return all_contents, all_shas, True
            except Exception as e2:
                log(f"  ✗ 重试也失败: {e2}")
                return all_contents, all_shas, False
        else:
            log(f"  ✗ 更新 rooms_{target}.txt 失败: {e}")
            return all_contents, all_shas, False
    except Exception as e:
        log(f"  ✗ 更新 rooms_{target}.txt 失败: {e}")
        return all_contents, all_shas, False

def search_and_check(page, context, keyword, min_watchers, existing_rooms, all_contents, all_shas):
    """搜索一个关键词：只取第一页初始可见房间，不滚动"""
    search_url = f"https://www.douyin.com/search/{quote(keyword)}?type=live"
    log(f"导航搜索页: {search_url}")
    room_ids = []

    # 导航到搜索页 + 等待 SPA 完全加载（networkidle 确保搜索 API 返回）
    try:
        page.goto(search_url, wait_until='networkidle', timeout=30000)
    except Exception as _e:
        log(f"  goto 超时, 继续等待渲染: {_e}")
    page.wait_for_timeout(8000)

    # 触发搜索：聚焦输入框按 Enter，触发 SPA 重新搜索
    try:
        inp = page.query_selector('input')
        if inp:
            inp.focus()
            page.keyboard.press('Enter')
            log(f"  已按 Enter 触发搜索")
        else:
            log(f"  未找到输入框, 尝试刷新页面")
            page.reload(wait_until='networkidle', timeout=30000)
    except Exception as _e:
        log(f"  触发搜索失败: {_e}")
    page.wait_for_timeout(10000)

    # 备用：如果仍然 0 房间, 再直接 reload
    _room_ids = page.evaluate("""() => [...new Set([...document.querySelectorAll('a')].map(a =>
        (a.href||'').match(/live\.douyin\.com\/(\d+)/)?.[1]).filter(Boolean))]""")
    if not _room_ids:
        log(f"  初始 0 房间, 尝试直接 reload...")
        try:
            page.goto(search_url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(12000)
        except:
            pass

    # 只取初始可见房间（不滚动）— 如果 reload 过了, 用最新的 room_ids
    try:
        room_ids = page.evaluate("""() => [...new Set([...document.querySelectorAll('a')].map(a =>
            (a.href||'').match(/live\.douyin\.com\/(\d+)/)?.[1]).filter(Boolean))]""")
    except:
        room_ids = _room_ids

    log(f"初始可见 {len(room_ids)} 个房间, 检查前 {TOP_N}")

    found_new = 0
    for idx, rid in enumerate(room_ids[:TOP_N]):
        if not rid:
            continue
        if rid in existing_rooms:
            log(f"  {idx+1}. — {rid}: 已存在")
            continue

        # 开新标签页检查，用完关闭
        rp = context.new_page()
        try:
            rp.goto(f'https://live.douyin.com/{rid}', wait_until='domcontentloaded', timeout=15000)
            rp.wait_for_timeout(5000)

            info = rp.evaluate("""() => {
                var t = document.body.innerText;
                var nick = '';
                var lines = t.split('\\n').map(function(l){return l.trim();}).filter(function(l){return l;});
                for (var i = 0; i < lines.length; i++) {
                    if (lines[i].includes('本场点赞')) { if (i > 0) nick = lines[i-1]; break; }
                }
                var vc = '';
                var m = t.match(/在线观众[·\s]*(\d[\d.]*[万k]?)/);
                if (m) vc = m[1];
                var isLive = t.includes('在线观众') || t.includes('本场点赞');
                return {nickname: nick, viewers: vc, isLive: isLive};
            }""")

            watchers = 0
            vc_str = info.get('viewers', '0')
            if '万' in vc_str:
                try: watchers = int(float(vc_str.replace('万', '')) * 10000)
                except: pass
            elif 'k' in vc_str.lower():
                try: watchers = int(float(vc_str.lower().replace('k', '')) * 1000)
                except: pass
            elif vc_str:
                try: watchers = int(float(vc_str))
                except: pass

            nickname = info.get('nickname', '').strip() or rid
            is_live = info.get('isLive', False)

            if is_live and watchers >= min_watchers:
                log(f"  {idx+1}. ✓ {rid} = {nickname} 在线={watchers} → 立即写入")
                content, sha, updated = update_rooms_add_one(all_contents, rid, nickname, all_shas)
                if updated:
                    existing_rooms[rid] = f"{rid} = {nickname}"
                    found_new += 1
            else:
                reason = '不在播' if not is_live else f'在线{watchers}<阈值{min_watchers}'
                log(f"  {idx+1}. ✗ {rid}: {reason}")

            rp.close()
        except Exception as e:
            log(f"  {idx+1}. ✗ {rid}: {e}")
            try: rp.close()
            except: pass

    return all_contents, existing_rooms, all_shas, found_new



def renew_self():
    """触发下一次 workflow 运行（自续命，去重）"""
    try:
        check_req = urllib.request.Request(
            f"https://api.github.com/repos/{GH_REPO}/actions/workflows/searcher.yml/runs?per_page=5&status=in_progress",
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json"})
        existing = json.loads(urllib.request.urlopen(check_req, timeout=15).read())
        run_num = os.environ.get("GH_RUN_NUMBER", "0")
        others = [r for r in existing.get("workflow_runs", []) if str(r["run_number"]) != run_num]
        if len(others) > 0:
            log(f"自续命跳过: 已有 {len(others)} 个其他正在运行的任务")
            return
        dispatch_req = urllib.request.Request(
            f"https://api.github.com/repos/{GH_REPO}/actions/workflows/searcher.yml/dispatches",
            data=json.dumps({"ref": "main"}).encode(),
            headers={"Authorization": f"Bearer {GH_TOKEN}", "Content-Type": "application/json"},
            method="POST")
        urllib.request.urlopen(dispatch_req, timeout=10)
        log("自续命成功")
    except Exception as e:
        log(f"自续命失败: {e}")

def main():
    if not DOUYIN_COOKIE:
        log("缺少 DOUYIN_COOKIE")
        return
    if not GH_REPO or not GH_TOKEN:
        log("缺少 GH_REPO 或 GH_TOKEN")
        return

    # 解码 cookies
    try:
        cookie_dict = json.loads(base64.b64decode(DOUYIN_COOKIE).decode("utf-8"))
        log(f"Cookies: {len(cookie_dict)} 个")
    except Exception as e:
        log(f"Cookie 解析失败: {e}")
        return

    # 启动 Playwright（浏览器保持常开 5 小时，不关闭）
    log("启动 Playwright 浏览器...")
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        locale='zh-CN',
    )
    context.add_cookies(cookie_dict)
    page = context.new_page()  # 搜索页

    start_time = time.time()
    renew_done = False
    round_num = 0
    all_time_new = 0

    try:
        while time.time() - start_time < MAX_RUNTIME:
            round_num += 1
            log(f"\n{'='*60}")
            log(f"第 {round_num} 轮搜索 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            log(f"已运行 {time.time()-start_time:.0f}s / {MAX_RUNTIME}s, 已发现 {all_time_new} 个新房")
            log(f"{'='*60}")

            # 每轮拉取最新 rooms.txt
            all_contents, existing_rooms, all_shas = get_rooms()
            if not all_shas or not any(all_shas.values()):
                log("无法获取 rooms_{idx}.txt, 等待 60s 重试")
                time.sleep(60)
                continue

            round_new = 0
            for i, (keyword, min_watchers) in enumerate(SEARCH_KEYWORDS):
                if time.time() - start_time >= MAX_RUNTIME:
                    break
                log(f"\n--- {keyword} (≥{min_watchers}人) ---")
                try:
                    all_contents, existing_rooms, all_shas, found = search_and_check(
                        page, context, keyword, min_watchers, existing_rooms, all_contents, all_shas)
                    round_new += found
                except Exception as e:
                    log(f"关键词 '{keyword}' 异常: {e}")
                    tb.print_exc()
                # 搜索之间随机等 2-3 分钟
                if i < len(SEARCH_KEYWORDS) - 1 and time.time() - start_time < MAX_RUNTIME:
                    delay = random.randint(120, 180)
                    log(f"等待 {delay}s 后搜索下一个关键词...")
                    time.sleep(delay)

            all_time_new += round_new
            if round_new == 0:
                log(f"\n本轮没有新房间 (累计 {all_time_new})")
            else:
                log(f"\n本轮新增 {round_new} 个 (累计 {all_time_new})")

            # 自续命（4.5h 触发，仅一次）
            if not renew_done and time.time() - start_time >= RENEW_AT:
                log("\n--- 触发自续命 ---")
                renew_self()
                renew_done = True

            # 等待下一轮
            elapsed = time.time() - start_time
            remaining = MAX_RUNTIME - elapsed
            if remaining > 0 and SEARCH_INTERVAL > 0:
                wait = min(SEARCH_INTERVAL, remaining)
                log(f"\n等待 {wait:.0f}s 后第 {round_num+1} 轮...")
                while wait > 0 and time.time() - start_time < MAX_RUNTIME:
                    time.sleep(min(10, wait))
                    wait -= 10

    except Exception as e:
        log(f"搜索任务异常终止: {e}")
        tb.print_exc()
    finally:
        browser.close()
        pw.stop()

    total = time.time() - start_time
    log(f"搜索任务结束: 运行 {total:.0f}s ({total/60:.0f}min), 共发现 {all_time_new} 个新房间")

if __name__ == "__main__":
    main()
