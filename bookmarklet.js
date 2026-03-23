/*
 * Data Center Testimony Bookmarklet
 *
 * How to install:
 *   1. Create a new bookmark in your browser
 *   2. Set the name to "Submit Testimony"
 *   3. Set the URL to the contents of bookmarklet_url.txt
 *
 * How to use:
 *   1. Highlight text on any news article
 *   2. Click the bookmark
 *   3. Pick a data center, click Submit
 *
 * Change SERVER below if you deploy somewhere other than localhost.
 */
(function () {
  var SERVER = 'http://localhost:5001';

  if (document.getElementById('dc-bm')) {
    document.getElementById('dc-bm').remove();
    return;
  }

  var text = window.getSelection().toString().trim();
  var pageUrl = window.location.href;
  var pageTitle = document.title.replace(/"/g, '&quot;').slice(0, 100);

  var d = document.createElement('div');
  d.id = 'dc-bm';
  d.style.cssText = 'position:fixed;top:0;right:0;width:340px;max-height:100vh;overflow-y:auto;background:#1a1a2e;color:#e0e0e0;font:14px/1.5 system-ui,sans-serif;z-index:999999;padding:16px;border-left:2px solid #4a4a6a;box-shadow:-4px 0 20px rgba(0,0,0,.5)';

  var s = 'width:100%;padding:6px;margin-bottom:10px;background:#2a2a3e;color:#e0e0e0;border:1px solid #4a4a6a;border-radius:4px';
  var lbl = 'display:block;margin-bottom:4px;font-size:12px;color:#aaa';

  d.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><strong>Submit Testimony</strong><span id="dc-x" style="cursor:pointer;font-size:20px;color:#888">&times;</span></div>' +
    '<label style="' + lbl + '">Data Center *</label>' +
    '<select id="dc-f" style="' + s + '"><option value="">Loading…</option></select>' +
    '<label style="' + lbl + '">Testimony *</label>' +
    '<textarea id="dc-t" rows="5" style="' + s + ';resize:vertical">' + (text || '') + '</textarea>' +
    '<label style="' + lbl + '">Source URL</label>' +
    '<input id="dc-u" value="' + pageUrl.replace(/"/g, '&quot;') + '" style="' + s + '">' +
    '<label style="' + lbl + '">Source Name</label>' +
    '<input id="dc-n" value="' + pageTitle + '" style="' + s + '">' +
    '<button id="dc-go" style="width:100%;padding:8px;background:#4a6cf7;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px">Submit</button>' +
    '<p id="dc-m" style="margin-top:8px;font-size:13px"></p>';

  document.body.appendChild(d);
  document.getElementById('dc-x').onclick = function () { d.remove(); };

  fetch(SERVER + '/api/centers')
    .then(function (r) { return r.json(); })
    .then(function (list) {
      var sel = document.getElementById('dc-f');
      sel.innerHTML = '<option value="">Select a facility…</option>';
      list.forEach(function (c) {
        var o = document.createElement('option');
        o.value = c.name;
        o.textContent = c.name;
        sel.appendChild(o);
      });
    })
    .catch(function () {
      document.getElementById('dc-f').innerHTML = '<option>Server not reachable</option>';
    });

  document.getElementById('dc-go').onclick = function () {
    var f = document.getElementById('dc-f').value;
    var t = document.getElementById('dc-t').value.trim();
    var m = document.getElementById('dc-m');
    if (!f || !t) { m.style.color = '#ff6b6b'; m.textContent = 'Select a facility and enter text.'; return; }
    document.getElementById('dc-go').disabled = true;
    document.getElementById('dc-go').textContent = 'Submitting…';
    fetch(SERVER + '/api/testimonies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        facility: f,
        statement: t,
        date: new Date().toLocaleDateString('en-US'),
        source: document.getElementById('dc-u').value.trim(),
        'source-details': document.getElementById('dc-n').value.trim() || 'Community submission'
      })
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok) { m.style.color = '#51cf66'; m.textContent = 'Submitted!'; setTimeout(function () { d.remove(); }, 1500); }
      else { m.style.color = '#ff6b6b'; m.textContent = data.error || 'Error'; document.getElementById('dc-go').disabled = false; document.getElementById('dc-go').textContent = 'Submit'; }
    })
    .catch(function () { m.style.color = '#ff6b6b'; m.textContent = 'Network error'; document.getElementById('dc-go').disabled = false; document.getElementById('dc-go').textContent = 'Submit'; });
  };
})();