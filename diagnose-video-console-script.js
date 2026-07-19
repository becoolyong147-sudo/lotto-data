/**
 * diagnose-video-console-script.js — 视频「手机打不开」诊断（在你自己的 Chrome 里跑）
 *
 * 用法：
 *  1. 用 Chrome 打开 http://localhost:7788/lottery.html（你平时那个页面）
 *  2. F12 → Console → 整段粘贴回车
 *  3. 看 console 摘要；会自动下载一个 2 秒测试片 video-test.mp4
 *  4. 把 video-test.mp4 发去手机试试能不能打开，回来告诉我结果
 *
 * 检查：浏览器实际用什么编码录、录出来是不是真 MP4/H.264、宽高是不是偶数、是不是碎片化MP4
 */
(function () {
  'use strict';
  var out = { ua: navigator.userAgent };
  if (!window.MediaRecorder) { console.log('❌ 浏览器不支持 MediaRecorder'); return; }

  // 1) 各候选编码支持情况
  var cands = [
    'video/mp4;codecs="avc1.42E01E,mp4a.40.2"',
    'video/mp4;codecs="avc1.4D401F,mp4a.40.2"',
    'video/mp4;codecs="avc1.640028,mp4a.40.2"',
    'video/mp4',
    'video/webm;codecs=vp9',
    'video/webm'
  ];
  out.support = {};
  cands.forEach(function (c) { out.support[c] = MediaRecorder.isTypeSupported(c); });
  var picked = cands.find(function (c) { return MediaRecorder.isTypeSupported(c); }) || 'video/webm';
  out.picked = picked;
  out.ext = picked.indexOf('mp4') >= 0 ? 'mp4' : 'webm';

  console.log('===== 视频诊断 =====');
  console.log('浏览器选用编码:', picked, '→ 文件扩展名: .' + out.ext);
  if (out.ext === 'webm') {
    console.log('❌ 关键问题：你的浏览器只能录 WebM，手机（尤其iPhone）和WhatsApp都打不开WebM。');
    console.log('   解决：把 Chrome 更新到最新版（chrome://settings/help），或换最新版 Chrome/Edge 打开页面。');
  } else {
    console.log('✓ 能录 MP4/H.264，手机应可打开（下面实录一段验证）');
  }

  // 2) 实录 2 秒测试片（偶数尺寸），检查真实字节
  var cv = document.createElement('canvas');
  cv.width = 640; cv.height = 360;                 // 偶数
  var ctx = cv.getContext('2d');
  var stream = cv.captureStream(30);
  var rec = new MediaRecorder(stream, { mimeType: picked, videoBitsPerSecond: 4000000 });
  var chunks = [];
  rec.ondataavailable = function (e) { if (e.data.size > 0) chunks.push(e.data); };
  rec.onstop = function () {
    var blob = new Blob(chunks, { type: picked.split(';')[0] });
    out.blobType = blob.type;
    out.sizeKB = (blob.size / 1024).toFixed(1);
    blob.slice(0, 4096).arrayBuffer().then(function (ab) {
      var buf = new Uint8Array(ab);
      var s = ''; for (var i = 0; i < buf.length; i++) s += (buf[i] >= 32 && buf[i] < 127) ? String.fromCharCode(buf[i]) : '.';
      out.isWebM = buf[0] === 0x1A && buf[1] === 0x45 && buf[2] === 0xDF && buf[3] === 0xA3;
      out.hasFtyp = s.indexOf('ftyp') >= 0;
      out.ftypBrand = out.hasFtyp ? s.slice(s.indexOf('ftyp') + 4, s.indexOf('ftyp') + 8) : null;
      out.hasMoov = s.indexOf('moov') >= 0;
      out.fragmentedMP4 = s.indexOf('moof') >= 0;   // 碎片化MP4：部分手机播放器/WhatsApp可能不认
      window.VIDEO_DIAG = out;
      console.log('实录结果:', JSON.stringify({
        类型: out.blobType, 大小KB: out.sizeKB, 是WebM: out.isWebM,
        含ftyp: out.hasFtyp, 品牌: out.ftypBrand, 含moov: out.hasMoov, 碎片化MP4: out.fragmentedMP4
      }));
      if (out.isWebM) console.log('→ 实锤是 WebM，手机打不开。更新 Chrome 后重试。');
      else if (out.fragmentedMP4) console.log('→ 是「碎片化MP4」。多数新手机能放；若WhatsApp仍不认，需要我加转码。请把下载的 video-test.mp4 发手机实测。');
      else console.log('→ 是标准 MP4，手机应该能正常打开。请把下载的 video-test.mp4 发手机确认。');
      // 下载测试片
      try {
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob); a.download = 'video-test.' + out.ext;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 3000);
        console.log('✅ 已下载 video-test.' + out.ext + ' — 发去手机试试能否打开，结果告诉Claude');
      } catch (e) { console.log('下载失败:', e.message); }
      console.log('（完整数据在 window.VIDEO_DIAG）');
    });
  };
  var t0 = performance.now();
  rec.start();
  (function frame() {
    var el = performance.now() - t0;
    ctx.fillStyle = '#0f0c29'; ctx.fillRect(0, 0, 640, 360);
    ctx.fillStyle = '#fde047'; ctx.font = '900 80px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(String(Math.floor(el / 100)), 320, 210);
    if (el < 2000) requestAnimationFrame(frame); else rec.stop();
  })();
  return '诊断录制中…等 console 出「实录结果」和自动下载';
})();
