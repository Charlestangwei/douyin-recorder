(() => {
    var links = document.querySelectorAll('a[href*="live.douyin.com/"]');
    var seen = {};
    var result = [];
    links.forEach(function(a) {
        var m = a.href.match(/live\.douyin\.com\/(\d+)/);
        if (m && !seen[m[1]]) {
            seen[m[1]] = true;
            result.push(m[1]);
        }
    });
    return JSON.stringify(result);
})()
