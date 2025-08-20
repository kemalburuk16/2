document.addEventListener("DOMContentLoaded", function() {
  // Tooltip aktif et
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.forEach(function(el) { new bootstrap.Tooltip(el); });

  // --- GENEL BAKIŞ --- //
  fetch("/srdr-proadmin/api/analytics/summary").then(res => res.json()).then(data => {
    let labels = [], users = [], newusers = [], views = [];
    data.forEach(row => {
      labels.push(row.date); users.push(row.active_users); newusers.push(row.new_users); views.push(row.pageviews);
    });
    // Son 7 gün tarihi
    document.getElementById("last7dates") && (document.getElementById("last7dates").innerText = labels.join(" - "));
    // Grafik
    let ctx = document.getElementById("summaryChart").getContext("2d");
    if (window.analyticsChart) window.analyticsChart.destroy();
    window.analyticsChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          { label: "Aktif Kullanıcı", data: users, borderColor: "#654FF0", backgroundColor: "#654FF033", borderWidth: 2, fill:true },
          { label: "Yeni Kullanıcı", data: newusers, borderColor: "#1DD197", backgroundColor: "#1DD19733", borderWidth: 2, fill:true },
          { label: "Sayfa Görüntüleme", data: views, borderColor: "#FD678A", backgroundColor: "#FD678A22", borderWidth: 2, fill:true }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "top" } }
      }
    });
    // Tablo
    let html = `<table class="table table-bordered table-striped"><thead><tr>
      <th>Tarih</th><th>Aktif Kullanıcı</th><th>Yeni Kullanıcı</th><th>Sayfa Görüntüleme</th></tr></thead><tbody>`;
    data.forEach(row => {
      html += `<tr><td>${row.date}</td><td>${row.active_users}</td><td>${row.new_users}</td><td>${row.pageviews}</td></tr>`;
    });
    html += "</tbody></table>";
    document.getElementById("analyticsTable").innerHTML = html;
  });

  // Canlı kullanıcı
  fetch("/srdr-proadmin/api/analytics/realtime").then(res => res.json()).then(data => {
    document.getElementById("realtimeUsers").innerHTML = '<i class="bi bi-person-lines-fill"></i> ' + data.active_users;
  });

  // --- ZİYARETÇİ BİLGİLERİ (Dummy data, API bağlanınca güncellenecek) --- //
  window.countryChart = new Chart(document.getElementById("countryChart"), {
    type: "pie",
    data: {
      labels: ["Türkiye", "Almanya", "ABD", "Fransa", "Rusya"],
      datasets: [{ data: [56, 22, 9, 8, 5], backgroundColor: ["#654ff0", "#1dd197", "#fd678a", "#f0b90b", "#29c6f6"] }]
    },
    options: {
      plugins: { legend: { position: "bottom" } }
    }
  });
  window.cityChart = new Chart(document.getElementById("cityChart"), {
    type: "bar",
    data: {
      labels: ["İstanbul", "Ankara", "Berlin", "Paris", "New York"],
      datasets: [{ label: "Ziyaretçi", data: [30, 12, 9, 7, 6], backgroundColor: "#654ff0" }]
    }
  });
  window.deviceChart = new Chart(document.getElementById("deviceChart"), {
    type: "pie",
    data: {
      labels: ["Mobil", "Masaüstü", "Tablet"],
      datasets: [{ data: [77, 21, 2], backgroundColor: ["#654ff0", "#1dd197", "#fd678a"] }]
    }
  });
  window.browserChart = new Chart(document.getElementById("browserChart"), {
    type: "doughnut",
    data: {
      labels: ["Chrome", "Safari", "Firefox", "Edge"],
      datasets: [{ data: [65, 22, 8, 5], backgroundColor: ["#654ff0", "#1dd197", "#fd678a", "#f0b90b"] }]
    }
  });
  window.osChart = new Chart(document.getElementById("osChart"), {
    type: "doughnut",
    data: {
      labels: ["Android", "iOS", "Windows", "MacOS"],
      datasets: [{ data: [46, 32, 14, 8], backgroundColor: ["#654ff0", "#1dd197", "#fd678a", "#f0b90b"] }]
    }
  });

  // --- TRAFİK & SAYFALAR (Dummy) --- //
  window.sourceChart = new Chart(document.getElementById("sourceChart"), {
    type: "pie",
    data: {
      labels: ["Google", "Direct", "Instagram", "Referrer"],
      datasets: [{ data: [62, 21, 10, 7], backgroundColor: ["#654ff0", "#1dd197", "#fd678a", "#f0b90b"] }]
    }
  });
  window.hourChart = new Chart(document.getElementById("hourChart"), {
    type: "bar",
    data: {
      labels: ["09:00", "11:00", "13:00", "15:00", "17:00", "20:00"],
      datasets: [{ label: "Trafik", data: [6, 14, 28, 20, 13, 18], backgroundColor: "#1dd197" }]
    }
  });
  // Sayfa tablosu
  document.getElementById("topPagesTable").innerHTML = `
    <table class="table table-bordered table-sm">
      <thead><tr><th>Sayfa</th><th>Görüntüleme</th><th>Ortalama Süre</th></tr></thead>
      <tbody>
        <tr><td>/</td><td>82</td><td>00:58</td></tr>
        <tr><td>/video</td><td>54</td><td>01:14</td></tr>
        <tr><td>/photo</td><td>42</td><td>00:41</td></tr>
        <tr><td>/reels</td><td>21</td><td>00:29</td></tr>
      </tbody>
    </table>
  `;

  // --- ARAMA & ANAHTAR KELİMELER (Dummy) --- //
  window.keywordChart = new Chart(document.getElementById("keywordChart"), {
    type: "bar",
    data: {
      labels: ["instagram video indir", "reels indir", "hikaye indir", "instavido", "mp4 indir"],
      datasets: [{ label: "Arama Hacmi", data: [21, 17, 14, 13, 10], backgroundColor: "#fd678a" }]
    }
  });
  window.platformChart = new Chart(document.getElementById("platformChart"), {
    type: "pie",
    data: {
      labels: ["Web", "iOS", "Android"],
      datasets: [{ data: [66, 18, 16], backgroundColor: ["#654ff0", "#1dd197", "#fd678a"] }]
    }
  });
  // Anahtar kelime tablosu
  document.getElementById("topKeywordsTable").innerHTML = `
    <table class="table table-bordered table-sm">
      <thead><tr><th>Anahtar Kelime</th><th>Arama Hacmi</th></tr></thead>
      <tbody>
        <tr><td>instagram video indir</td><td>21</td></tr>
        <tr><td>reels indir</td><td>17</td></tr>
        <tr><td>hikaye indir</td><td>14</td></tr>
        <tr><td>instavido</td><td>13</td></tr>
      </tbody>
    </table>
  `;
});
